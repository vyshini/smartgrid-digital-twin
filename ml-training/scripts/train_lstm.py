"""
Trains the dual-head LSTM (model.py) for each city, using the real,
feature-engineered windows from feature_engineering.py.

SPLIT METHODOLOGY — chronological, not random:
    This is a time series. A random train/val/test split would let the
    model "see the future" during training (a window from March 2019 could
    end up in the training set while a window from January 2019 ends up in
    the test set), which silently inflates every metric below and produces
    a model that looks good offline but degrades in deployment. Instead we
    sort all windows by window_end_date and cut chronologically:

        [------------- train (70%) -------------][-- val (15%) --][-- test (15%) --]
        earliest dates                                                latest dates

    The test set is therefore genuinely held out in time — it simulates
    "how would this model, trained only on the past, have performed on
    dates it has never seen." No shuffling is applied before the split.
    (Shuffling *within* each split, e.g. for mini-batch order during
    training, is fine and is left to Keras' default `shuffle=True` in
    model.fit — that only reorders which already-in-train windows appear
    in which batch, not train/val/test membership.)

Run from ml-training/scripts/:
    python train_lstm.py                     # trains all 8 cities
    python train_lstm.py --city Delhi         # single city, e.g. for a smoke test
    python train_lstm.py --city Delhi --epochs 2   # fast sanity check

NOTE ON SANDBOX EXECUTION: written against TensorFlow/Keras 2.x; could not
be run in the sandbox this project was authored in (tensorflow not
installed, no network access to install it or to fetch a GPU runtime).
Same caveat as fetch_weather.py — validate on your own machine before
trusting the numbers, starting with a 1-2 epoch run on one city.
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
# remaining ~0.15 is TEST_FRAC, implied

SEED = 42


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def time_based_split(
    X: np.ndarray,
    y_day: np.ndarray,
    y_week: np.ndarray,
    dates: np.ndarray,
    train_frac: float = TRAIN_FRAC,
    val_frac: float = VAL_FRAC,
) -> dict:
    """
    Chronological split — see module docstring. `dates` (window_end_dates
    from build_supervised_windows) are assumed already sorted ascending,
    which build_supervised_windows guarantees since it iterates the
    already-sorted df in order. We assert that here rather than assume it
    silently, since a silent violation would defeat the whole point of
    this function.
    """
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
            f"at fractions {train_frac}/{val_frac}/{1 - train_frac - val_frac}. "
            f"Check that the demand+weather date ranges actually overlap."
        )

    return {
        "train": (X[:train_end], y_day[:train_end], y_week[:train_end], dates[:train_end]),
        "val": (X[train_end:val_end], y_day[train_end:val_end], y_week[train_end:val_end], dates[train_end:val_end]),
        "test": (X[val_end:], y_day[val_end:], y_week[val_end:], dates[val_end:]),
    }


# ---------------------------------------------------------------------------
# Scaling — fit on train only, applied to val/test (no leakage)
# ---------------------------------------------------------------------------

def fit_feature_scaler(X_train: np.ndarray) -> StandardScaler:
    """Fits a StandardScaler on the TRAIN split only. X is (n, lookback,
    n_features); flattened to (n*lookback, n_features) to fit per-feature
    mean/std, since sklearn scalers expect 2D input."""
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


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    MAE, RMSE, MAPE — all computed in real MW (post inverse-transform), not
    in scaled units, since scaled-unit error numbers are meaningless to a
    reader of the report. MAPE guards against division by ~0 demand rows
    (shouldn't occur for city-level total_demand_mw, which is never near
    zero, but guarded defensively rather than trusting that blindly).
    """
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


# ---------------------------------------------------------------------------
# Per-city training
# ---------------------------------------------------------------------------

def train_city(
    city: str,
    epochs: int = 100,
    batch_size: int = 32,
    lookback: int = LOOKBACK_DAYS,
    patience: int = 15,
    verbose: int = 1,
) -> dict:
    """
    Loads city data -> builds supervised windows -> chronological split ->
    scales (fit on train only) -> trains -> evaluates on the held-out test
    split -> saves model + scalers + metrics to disk. Returns the metrics
    dict (also written to results/<city>_metrics.json).
    """
    set_global_seed(SEED)

    print(f"\n{'=' * 60}\n{city}\n{'=' * 60}")

    df = load_city_dataset(city)
    df = add_lag_features(df)
    X, y_day, y_week, dates = build_supervised_windows(df, DEFAULT_FEATURE_COLUMNS, lookback=lookback)

    if len(X) < 50:
        raise ValueError(
            f"{city}: only {len(X)} usable windows after dropping NaN-lag rows and "
            f"contiguity gaps — too few to train/val/test split meaningfully. "
            f"Check date-range overlap between demand and weather data for this city."
        )

    splits = time_based_split(X, y_day, y_week, dates)
    (X_tr, yday_tr, yweek_tr, dates_tr) = splits["train"]
    (X_val, yday_val, yweek_val, dates_val) = splits["val"]
    (X_te, yday_te, yweek_te, dates_te) = splits["test"]

    print(
        f"  windows: train={len(X_tr)} ({str(dates_tr.min())[:10]} to {str(dates_tr.max())[:10]}), "
        f"val={len(X_val)} ({str(dates_val.min())[:10]} to {str(dates_val.max())[:10]}), "
        f"test={len(X_te)} ({str(dates_te.min())[:10]} to {str(dates_te.max())[:10]})"
    )

    # Scale features: fit on TRAIN ONLY, apply to all three splits.
    feature_scaler = fit_feature_scaler(X_tr)
    X_tr_s = apply_feature_scaler(feature_scaler, X_tr)
    X_val_s = apply_feature_scaler(feature_scaler, X_val)
    X_te_s = apply_feature_scaler(feature_scaler, X_te)

    # Scale targets: separate scalers per horizon, fit on TRAIN ONLY.
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

    # --- Evaluate on the held-out, chronologically-later TEST split ---
    preds = model.predict(X_te_s, verbose=0)
    yday_pred = inverse_target_scaler(day_scaler, preds["next_day"])
    yweek_pred = inverse_target_scaler(week_scaler, preds["next_week"])

    metrics = {
        "city": city,
        "state": CITY_TO_STATE[city],
        "n_windows_total": int(len(X)),
        "n_train": int(len(X_tr)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_te)),
        "test_date_range": [str(dates_te.min())[:10], str(dates_te.max())[:10]],
        "epochs_run": len(history.history["loss"]),
        "train_seconds": train_seconds,
        "next_day": compute_metrics(yday_te, yday_pred),
        "next_week": compute_metrics(yweek_te, yweek_pred),
    }

    # --- Save artifacts ---
    model.save(city_dir / "model.keras")
    joblib.dump(feature_scaler, city_dir / "feature_scaler.joblib")
    joblib.dump(day_scaler, city_dir / "next_day_target_scaler.joblib")
    joblib.dump(week_scaler, city_dir / "next_week_target_scaler.joblib")
    joblib.dump(list(DEFAULT_FEATURE_COLUMNS), city_dir / "feature_columns.joblib")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{city.lower()}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Save the raw loss history too, for later diagnostic plotting — not
    # plotted here to avoid a hard matplotlib dependency in the training path.
    hist_df = pd.DataFrame(history.history)
    hist_df.to_csv(city_dir / "training_history.csv", index_label="epoch")

    print(
        f"  next_day  -> MAE={metrics['next_day']['mae_mw']} MW, "
        f"RMSE={metrics['next_day']['rmse_mw']} MW, MAPE={metrics['next_day']['mape_pct']}%"
    )
    print(
        f"  next_week -> MAE={metrics['next_week']['mae_mw']} MW, "
        f"RMSE={metrics['next_week']['rmse_mw']} MW, MAPE={metrics['next_week']['mape_pct']}%"
    )
    print(f"  saved -> {city_dir}")

    return metrics


# ---------------------------------------------------------------------------
# CLI / orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", type=str, default=None, help="Train a single city (e.g. Delhi). Default: all 8.")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lookback", type=int, default=LOOKBACK_DAYS)
    parser.add_argument("--patience", type=int, default=15, help="EarlyStopping patience on val_loss.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-epoch Keras logs.")
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
        except Exception as e:  # noqa: BLE001 — deliberately broad: one city's
            # failure (e.g. missing weather file) should not abort the whole
            # multi-city run; it's collected and reported at the end instead.
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
                "next_week_mae_mw": m["next_week"]["mae_mw"],
                "next_week_rmse_mw": m["next_week"]["rmse_mw"],
                "next_week_mape_pct": m["next_week"]["mape_pct"],
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