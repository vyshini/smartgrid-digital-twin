"""
Production GBT pipeline — adds cooling/heating degree-day features and a
tuned LightGBM config, run across all 8 cities for both horizons. This
supersedes gbt_baseline.py as the model to report, since GBT already
demonstrated it beats the LSTM on next-day forecasts with no tuning at all.

Degree-day features:
    cooling_degree_days = max(0, temperature_c - 24)   -- AC load driver
    heating_degree_days = max(0, 18 - temperature_c)   -- heating load driver
Chosen thresholds are standard STLF convention (18-24C comfort band), not
tuned per-city -- a reasonable default given no city-specific comfort
data exists in this project.

Run:
    python gbt_full.py                 # all 8 cities, both horizons
    python gbt_full.py --city Kolkata  # single city
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from feature_engineering import DEFAULT_FEATURE_COLUMNS, add_lag_features, load_city_dataset
from data_preparation import CITY_TO_STATE

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15

# *** NEW: degree-day features added on top of DEFAULT_FEATURE_COLUMNS ***
GBT_FEATURE_COLUMNS = DEFAULT_FEATURE_COLUMNS + ["cooling_degree_days", "heating_degree_days"]


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    nonzero = np.abs(y_true) > 1e-6
    mape = float(np.mean(np.abs(errors[nonzero] / y_true[nonzero])) * 100) if nonzero.sum() else float("nan")
    return {"mae_mw": round(mae, 3), "rmse_mw": round(rmse, 3), "mape_pct": round(mape, 3)}


def build_flat_dataset(city: str, target_col: str = "total_demand_mw") -> pd.DataFrame:
    df = load_city_dataset(city)
    df = add_lag_features(df, target_col=target_col)

    # *** NEW: degree-day features ***
    df["cooling_degree_days"] = (df["temperature_c"] - 24.0).clip(lower=0)
    df["heating_degree_days"] = (18.0 - df["temperature_c"]).clip(lower=0)

    df = df.dropna(subset=GBT_FEATURE_COLUMNS + [target_col]).sort_index()

    anchor = df[target_col]
    df["y_next_day_delta"] = anchor.shift(-1) - anchor
    df["y_next_week_delta"] = anchor.shift(-7) - anchor
    df["anchor_mw"] = anchor
    df = df.dropna(subset=["y_next_day_delta", "y_next_week_delta"])
    return df


def chronological_split(df: pd.DataFrame) -> dict:
    n = len(df)
    train_end = int(n * TRAIN_FRAC)
    val_end = int(n * (TRAIN_FRAC + VAL_FRAC))
    if train_end == 0 or val_end == train_end or val_end == n:
        raise ValueError(f"Not enough rows ({n}) for a meaningful 70/15/15 split.")
    return {"train": df.iloc[:train_end], "val": df.iloc[train_end:val_end], "test": df.iloc[val_end:]}


def run_city(city: str, horizon: str, verbose: bool = True) -> dict:
    import lightgbm as lgb
    import joblib

    target_delta_col = f"y_{horizon}_delta"
    df = build_flat_dataset(city)
    splits = chronological_split(df)
    train, val, test = splits["train"], splits["val"], splits["test"]

    X_train, y_train = train[GBT_FEATURE_COLUMNS], train[target_delta_col]
    X_val, y_val = val[GBT_FEATURE_COLUMNS], val[target_delta_col]
    X_test, y_test = test[GBT_FEATURE_COLUMNS], test[target_delta_col]

    # *** TUNED: more estimators + lower LR (finer search), slightly
    # deeper leaves since we added 2 more features, stronger subsampling
    # to fight overfitting on ~1900-2600 train rows. ***
    model = lgb.LGBMRegressor(
        n_estimators=1500,
        learning_rate=0.015,
        num_leaves=20,
        min_child_samples=12,
        subsample=0.75,
        subsample_freq=1,
        colsample_bytree=0.75,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        verbosity=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="l1",
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )

    pred_delta = model.predict(X_test)
    anchors_test = test["anchor_mw"].to_numpy()
    y_true_abs = anchors_test + y_test.to_numpy()
    y_pred_abs = anchors_test + pred_delta

    gbt_metrics = compute_metrics(y_true_abs, y_pred_abs)
    persistence_metrics = compute_metrics(y_true_abs, anchors_test)

    result = {
        "city": city, "horizon": horizon,
        "n_train": len(train), "n_test": len(test),
        "gbt_mae_mw": gbt_metrics["mae_mw"],
        "gbt_rmse_mw": gbt_metrics["rmse_mw"],
        "gbt_mape_pct": gbt_metrics["mape_pct"],
        "persistence_mape_pct": persistence_metrics["mape_pct"],
        "beats_persistence": gbt_metrics["mape_pct"] < persistence_metrics["mape_pct"],
        "improvement_pct_pts": round(persistence_metrics["mape_pct"] - gbt_metrics["mape_pct"], 3),
    }
    gbt_dir = Path(__file__).parent.parent / "models_gbt" / city.lower()
    gbt_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, gbt_dir / f"{horizon}_model.joblib")
    joblib.dump(GBT_FEATURE_COLUMNS, gbt_dir / "feature_columns.joblib")
    if verbose:
        verdict = "BEATS" if result["beats_persistence"] else "does not beat"
        print(f"  {city:10s} {horizon:10s} -> MAPE={gbt_metrics['mape_pct']}%  "
              f"(persistence={persistence_metrics['mape_pct']}%, {verdict})")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", type=str, default=None)
    args = parser.parse_args()

    cities = [args.city] if args.city else list(CITY_TO_STATE.keys())
    all_results = []
    for city in cities:
        print(f"\n{city}:")
        for horizon in ("next_day", "next_week"):
            all_results.append(run_city(city, horizon))

    df = pd.DataFrame(all_results)
    out_path = Path(__file__).parent.parent / "results" / "gbt_summary.csv"
    df.to_csv(out_path, index=False)
    print(f"\n{'=' * 100}\nSaved -> {out_path}\n")
    print(df.to_string(index=False))
    print(f"\nAvg next-day MAPE:  {df[df.horizon=='next_day'].gbt_mape_pct.mean():.3f}%")
    print(f"Avg next-week MAPE: {df[df.horizon=='next_week'].gbt_mape_pct.mean():.3f}%")


if __name__ == "__main__":
    main()