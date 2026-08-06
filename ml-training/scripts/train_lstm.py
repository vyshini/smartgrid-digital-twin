"""
Trains the dual-head LSTM (model.py) for each city.

*** CHANGE (delta-target fix) ***
The model's two heads now predict DELTAS (change from the anchor day),
not absolute MW levels — see feature_engineering.py's module docstring.
Critically: METRICS (MAE/RMSE/MAPE) are still computed in ABSOLUTE MW,
by adding the anchor back to both the true delta and the predicted delta
before scoring. This keeps your reported metrics comparable to the old
absolute-level model's metrics, while the model itself trains on the
easier, better-behaved delta target.

SPLIT METHODOLOGY — chronological, unchanged from the original version.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from tensorflow import keras

sys.path.insert(0, str(Path(__file__).parent))
from feature_engineering import (
    DEFAULT_FEATURE_COLUMNS,
    LOOKBACK_DAYS,
    add_lag_features,
    build_supervised_windows,
    load_city_dataset,
)
from data_preparation import CITY_TO_STATE
from model import LSTMConfig, build_lstm_model, set_global_seed

MODELS_DIR = Path(__file__).parent.parent / "models"
RESULTS_DIR = Path(__file__).parent.parent / "results"

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
SEED = 42


def time_based_split(
    X: np.ndarray,
    y_day: np.ndarray,
    y_week: np.ndarray,
    anchors: np.ndarray,          # *** NEW ***
    dates: np.ndarray,
    train_frac: float = TRAIN_FRAC,
    val_frac: float = VAL_FRAC,
) -> dict:
    if not np.all(np.diff(dates).astype("timedelta64[D]").astype(int) >= 0):
        raise ValueError(
            "window_end_dates are not sorted ascending — time_based_split "
            "requires chronological order to produce a valid holdout."
        )

    n = len(X)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    if train_end == 0 or val_end == train_end or val_end == n:
        raise ValueError(
            f"Not enough windows ({n}) to form non-empty train/val/test splits "
            f"at fractions {train_frac}/{val_frac}/{1 - train_frac - val_frac}."
        )

    return {
        "train": (X[:train_end], y_day[:train_end], y_week[:train_end], anchors[:train_end], dates[:train_end]),
        "val": (X[train_end:val_end], y_day[train_end:val_end], y_week[train_end:val_end],
                anchors[train_end:val_end], dates[train_end:val_end]),
        "test": (X[val_end:], y_day[val_end:], y_week[val_end:], anchors[val_end:], dates[val_end:]),
    }


def fit_feature_scaler(X_train: np.ndarray) -> StandardScaler:
    n, lookback, n_features = X_train.shape
    scaler = StandardScaler()
    scaler.fit(X_train.reshape(-1, n_features))
    return scaler


def apply_feature_scaler(scaler: StandardScaler, X: np.ndarray) -> np.ndarray:
    n, lookback, n_features = X.shape
    return scaler.transform(X.reshape(-1, n_features)).reshape(n, lookback, n_features).astype(np.float32)


def fit_target_scaler(y_train: np.ndarray) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(y_train.reshape(-1, 1))
    return scaler


def apply_target_scaler(scaler: StandardScaler, y: np.ndarray) -> np.ndarray:
    return scaler.transform(y.reshape(-1, 1)).astype(np.float32).ravel()


def inverse_target_scaler(scaler: StandardScaler, y_scaled: np.ndarray) -> np.ndarray:
    return scaler.inverse_transform(np.asarray(y_scaled).reshape(-1, 1)).ravel()


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Unchanged — still computed in real MW. Callers must pass ABSOLUTE
    MW values (anchor + delta), not raw deltas — see train_city()."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    nonzero = np.abs(y_true) > 1e-6
    if nonzero.sum() == 0:
        mape = float("nan")
    else:
        mape = float(np.mean(np.abs(errors[nonzero] / y_true[nonzero])) * 100)

    return {"mae_mw": round(mae, 3), "rmse_mw": round(rmse, 3), "mape_pct": round(mape, 3)}


def compute_persistence_baseline(y_true_absolute: np.ndarray, anchors: np.ndarray) -> dict:
    """
    *** NEW *** — the persistence-baseline check flagged as missing.
    "Naive forecast" = tomorrow's demand will equal the anchor day's
    demand, i.e. predicted delta = 0. Run this on the SAME test split as
    the real model so the two numbers are directly comparable. If your
    trained model's MAPE isn't clearly better than this, it hasn't
    learned anything the naive baseline didn't already know.
    """
    return compute_metrics(y_true_absolute, anchors)


def train_city(
    city: str,
    epochs: int = 100,
    batch_size: int = 32,
    lookback: int = LOOKBACK_DAYS,
    patience: int = 15,
    verbose: int = 1,
) -> dict:
    set_global_seed(SEED)
    print(f"\n{'=' * 60}\n{city}\n{'=' * 60}")

    df = load_city_dataset(city)
    df = add_lag_features(df)
    X, y_day_delta, y_week_delta, anchors, dates = build_supervised_windows(
        df, DEFAULT_FEATURE_COLUMNS, lookback=lookback
    )

    if len(X) < 50:
        raise ValueError(
            f"{city}: only {len(X)} usable windows after dropping NaN-lag rows and "
            f"contiguity gaps — too few to train/val/test split meaningfully."
        )

    splits = time_based_split(X, y_day_delta, y_week_delta, anchors, dates)
    (X_tr, yday_tr, yweek_tr, anchors_tr, dates_tr) = splits["train"]
    (X_val, yday_val, yweek_val, anchors_val, dates_val) = splits["val"]
    (X_te, yday_te, yweek_te, anchors_te, dates_te) = splits["test"]

    print(
        f"  windows: train={len(X_tr)} ({str(dates_tr.min())[:10]} to {str(dates_tr.max())[:10]}), "
        f"val={len(X_val)} ({str(dates_val.min())[:10]} to {str(dates_val.max())[:10]}), "
        f"test={len(X_te)} ({str(dates_te.min())[:10]} to {str(dates_te.max())[:10]})"
    )

    feature_scaler = fit_feature_scaler(X_tr)
    X_tr_s = apply_feature_scaler(feature_scaler, X_tr)
    X_val_s = apply_feature_scaler(feature_scaler, X_val)
    X_te_s = apply_feature_scaler(feature_scaler, X_te)

    # Scalers now fit on DELTAS, not absolute levels.
    day_scaler = fit_target_scaler(yday_tr)
    week_scaler = fit_target_scaler(yweek_tr)

    yday_tr_s = apply_target_scaler(day_scaler, yday_tr)
    yday_val_s = apply_target_scaler(day_scaler, yday_val)
    yweek_tr_s = apply_target_scaler(week_scaler, yweek_tr)
    yweek_val_s = apply_target_scaler(week_scaler, yweek_val)

    config = LSTMConfig(lookback=lookback, n_features=X_tr.shape[2])
    model = build_lstm_model(config)

    city_dir = MODELS_DIR / city.lower()
    city_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = city_dir / "checkpoint.keras"

    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=patience, restore_best_weights=True),
        keras.callbacks.ModelCheckpoint(str(checkpoint_path), monitor="val_loss", save_best_only=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=max(3, patience // 3), min_lr=1e-6),
    ]

    start = time.time()
    history = model.fit(
        X_tr_s,
        {"next_day": yday_tr_s, "next_week": yweek_tr_s},
        validation_data=(X_val_s, {"next_day": yday_val_s, "next_week": yweek_val_s}),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=verbose,
    )
    train_seconds = round(time.time() - start, 1)

    # --- Predict deltas on TEST, then reconstruct ABSOLUTE MW before scoring ---
    preds = model.predict(X_te_s, verbose=0)
    yday_pred_delta = inverse_target_scaler(day_scaler, preds["next_day"])
    yweek_pred_delta = inverse_target_scaler(week_scaler, preds["next_week"])

    # Absolute reconstruction: anchor + delta
    yday_true_abs = anchors_te + yday_te
    yday_pred_abs = anchors_te + yday_pred_delta
    yweek_true_abs = anchors_te + yweek_te
    yweek_pred_abs = anchors_te + yweek_pred_delta

    next_day_metrics = compute_metrics(yday_true_abs, yday_pred_abs)
    next_week_metrics = compute_metrics(yweek_true_abs, yweek_pred_abs)

    # *** NEW: persistence baseline on the identical test split ***
    next_day_persistence = compute_persistence_baseline(yday_true_abs, anchors_te)
    next_week_persistence = compute_persistence_baseline(yweek_true_abs, anchors_te)

    metrics = {
        "city": city,
        "state": CITY_TO_STATE[city],
        "target_type": "delta_from_anchor",  # *** NEW ***
        "n_windows_total": int(len(X)),
        "n_train": int(len(X_tr)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_te)),
        "test_date_range": [str(dates_te.min())[:10], str(dates_te.max())[:10]],
        "epochs_run": len(history.history["loss"]),
        "train_seconds": train_seconds,
        "next_day": next_day_metrics,
        "next_week": next_week_metrics,
        "next_day_persistence_baseline": next_day_persistence,     # *** NEW ***
        "next_week_persistence_baseline": next_week_persistence,   # *** NEW ***
        "next_day_beats_persistence": next_day_metrics["mape_pct"] < next_day_persistence["mape_pct"],   # *** NEW ***
        "next_week_beats_persistence": next_week_metrics["mape_pct"] < next_week_persistence["mape_pct"], # *** NEW ***
    }

    # --- Save artifacts ---
    model.save(city_dir / "model.keras")
    joblib.dump(feature_scaler, city_dir / "feature_scaler.joblib")
    joblib.dump(day_scaler, city_dir / "next_day_delta_target_scaler.joblib")   # *** RENAMED ***
    joblib.dump(week_scaler, city_dir / "next_week_delta_target_scaler.joblib") # *** RENAMED ***
    joblib.dump(list(DEFAULT_FEATURE_COLUMNS), city_dir / "feature_columns.joblib")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{city.lower()}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    hist_df = pd.DataFrame(history.history)
    hist_df.to_csv(city_dir / "training_history.csv", index_label="epoch")

    print(
        f"  next_day  -> MAE={metrics['next_day']['mae_mw']} MW, RMSE={metrics['next_day']['rmse_mw']} MW, "
        f"MAPE={metrics['next_day']['mape_pct']}%  |  persistence MAPE={next_day_persistence['mape_pct']}% "
        f"-> {'BEATS' if metrics['next_day_beats_persistence'] else 'DOES NOT BEAT'} persistence"
    )
    print(
        f"  next_week -> MAE={metrics['next_week']['mae_mw']} MW, RMSE={metrics['next_week']['rmse_mw']} MW, "
        f"MAPE={metrics['next_week']['mape_pct']}%  |  persistence MAPE={next_week_persistence['mape_pct']}% "
        f"-> {'BEATS' if metrics['next_week_beats_persistence'] else 'DOES NOT BEAT'} persistence"
    )
    print(f"  saved -> {city_dir}")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", type=str, default=None)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lookback", type=int, default=LOOKBACK_DAYS)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    cities = [args.city] if args.city else list(CITY_TO_STATE.keys())
    for c in cities:
        if c not in CITY_TO_STATE:
            raise ValueError(f"Unknown city '{c}'. Valid cities: {list(CITY_TO_STATE.keys())}")

    all_metrics = []
    failures = []
    for city in cities:
        try:
            m = train_city(
                city,
                epochs=args.epochs,
                batch_size=args.batch_size,
                lookback=args.lookback,
                patience=args.patience,
                verbose=0 if args.quiet else 1,
            )
            all_metrics.append(m)
        except Exception as e:  # noqa: BLE001
            print(f"  [FAILED] {city}: {e}")
            failures.append({"city": city, "error": str(e)})

    if all_metrics:
        summary_rows = [
            {
                "city": m["city"],
                "state": m["state"],
                "n_train": m["n_train"],
                "n_val": m["n_val"],
                "n_test": m["n_test"],
                "test_start": m["test_date_range"][0],
                "test_end": m["test_date_range"][1],
                "epochs_run": m["epochs_run"],
                "next_day_mae_mw": m["next_day"]["mae_mw"],
                "next_day_rmse_mw": m["next_day"]["rmse_mw"],
                "next_day_mape_pct": m["next_day"]["mape_pct"],
                "next_day_persistence_mape_pct": m["next_day_persistence_baseline"]["mape_pct"],  # *** NEW ***
                "next_day_beats_persistence": m["next_day_beats_persistence"],                     # *** NEW ***
                "next_week_mae_mw": m["next_week"]["mae_mw"],
                "next_week_rmse_mw": m["next_week"]["rmse_mw"],
                "next_week_mape_pct": m["next_week"]["mape_pct"],
                "next_week_persistence_mape_pct": m["next_week_persistence_baseline"]["mape_pct"], # *** NEW ***
                "next_week_beats_persistence": m["next_week_beats_persistence"],                    # *** NEW ***
            }
            for m in all_metrics
        ]
        summary_df = pd.DataFrame(summary_rows)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        summary_path = RESULTS_DIR / "training_summary.csv"
        summary_df.to_csv(summary_path, index=False)
        print(f"\n{'=' * 60}\nSummary written to {summary_path}\n{'=' * 60}")
        print(summary_df.to_string(index=False))

    if failures:
        print(f"\n{len(failures)} cit{'y' if len(failures) == 1 else 'ies'} failed:")
        for f in failures:
            print(f"  - {f['city']}: {f['error']}")


if __name__ == "__main__":
    main()