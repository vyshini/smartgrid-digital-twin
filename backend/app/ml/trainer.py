"""
Ports the training loop from ml-training/scripts/train_lstm.py, with one
real behavioral difference: this version does NOT overwrite the live
model just because a training run finished. It trains into a fresh
model_registry version directory, evaluates on the same chronological
test split as before, and only calls model_registry.promote() if the
candidate is not a regression against whatever is currently live —
otherwise the candidate stays on disk (inspectable, rollback-able) but
never gets served.

This matters here specifically because retraining is expected to run
periodically as new demand data comes in (the spec's "continuously
collect -> clean -> predict" loop) — an automated retrain that silently
degrades is worse than no retrain at all, since nothing else in the
system would notice.

Run from repo root (needs TensorFlow/Keras installed — see
ml-training/scripts/model.py's sandbox-execution caveat, same applies
here):
    python -m backend.app.ml.trainer --city Delhi --data-dir ml-training/data
    python -m backend.app.ml.trainer --data-dir ml-training/data   # all 8 cities
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
from tensorflow import keras

from . import evaluator as ev
from . import feature_engineering as fe
from . import model_registry
from .lstm_model import LSTMConfig, build_lstm_model, set_global_seed
from . import preprocessing as pp
from .model_registry import ModelNotFoundError

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
SEED = 42

# Cities this project models — kept here rather than re-importing
# ml-training/scripts/data_preparation.py, since that script lives outside
# the backend package. If you add a city, add it in both places (a small
# duplication that's more honest than a cross-package import reaching
# outside backend/).
CITY_TO_STATE: dict[str, str] = {
    "Delhi": "Delhi",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Bangalore": "Karnataka",
    "Hyderabad": "Telangana",
    "Chennai": "Tamil Nadu",
    "Kolkata": "West Bengal",
    "Ahmedabad": "Gujarat",
}

# How much worse (in MAPE percentage points, next_day) a candidate is
# allowed to be than the currently-live model and still get promoted.
# A candidate that's *better* always promotes; this tolerance exists so a
# noisy-but-not-actually-worse retrain (different random init, one bad
# batch) doesn't get stuck refusing to ever update the live model.
DEFAULT_REGRESSION_TOLERANCE_PCT = 1.0


def time_based_split(X, y_day, y_week, dates, train_frac=TRAIN_FRAC, val_frac=VAL_FRAC) -> dict:
    if not np.all(np.diff(dates).astype("timedelta64[D]").astype(int) >= 0):
        raise ValueError("window_end_dates are not sorted ascending.")

    n = len(X)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    if train_end == 0 or val_end == train_end or val_end == n:
        raise ValueError(f"Not enough windows ({n}) to form non-empty train/val/test splits.")

    return {
        "train": (X[:train_end], y_day[:train_end], y_week[:train_end], dates[:train_end]),
        "val": (X[train_end:val_end], y_day[train_end:val_end], y_week[train_end:val_end], dates[train_end:val_end]),
        "test": (X[val_end:], y_day[val_end:], y_week[val_end:], dates[val_end:]),
    }


def _should_promote(candidate_metrics: dict, city: str, tolerance_pct: float) -> tuple[bool, str]:
    """Returns (should_promote, reason). First-ever model for a city
    always promotes — there's nothing to regress against."""
    try:
        current_version = model_registry.current_version(city)
    except ModelNotFoundError:
        return True, "no currently-promoted model for this city — promoting first version"

    current_paths = model_registry.paths_for(city, current_version)
    if not current_paths.metrics_path.exists():
        return True, f"current version {current_version} has no saved metrics.json to compare against"

    current_metrics = json.loads(current_paths.metrics_path.read_text())
    current_mape = current_metrics["next_day"]["mape_pct"]
    candidate_mape = candidate_metrics["next_day"]["mape_pct"]

    if candidate_mape <= current_mape + tolerance_pct:
        return True, f"candidate next_day MAPE {candidate_mape}% vs current {current_mape}% (within tolerance)"
    return False, (
        f"candidate next_day MAPE {candidate_mape}% is worse than current {current_mape}% "
        f"by more than {tolerance_pct} points — NOT promoted, left as an inspectable candidate"
    )


def train_city(
    city: str,
    data_dir: Path,
    epochs: int = 100,
    batch_size: int = 32,
    lookback: int = fe.LOOKBACK_DAYS,
    patience: int = 15,
    verbose: int = 1,
    regression_tolerance_pct: float = DEFAULT_REGRESSION_TOLERANCE_PCT,
    force_promote: bool = False,
) -> dict:
    set_global_seed(SEED)
    print(f"\n{'=' * 60}\n{city}\n{'=' * 60}")

    df = fe.load_city_dataset(city, data_dir)
    df = fe.add_lag_features(df)
    X, y_day, y_week, dates = fe.build_supervised_windows(df, fe.DEFAULT_FEATURE_COLUMNS, lookback=lookback)

    if len(X) < 50:
        raise ValueError(f"{city}: only {len(X)} usable windows — too few to split meaningfully.")

    splits = time_based_split(X, y_day, y_week, dates)
    (X_tr, yday_tr, yweek_tr, dates_tr) = splits["train"]
    (X_val, yday_val, yweek_val, dates_val) = splits["val"]
    (X_te, yday_te, yweek_te, dates_te) = splits["test"]

    print(f"  windows: train={len(X_tr)}, val={len(X_val)}, test={len(X_te)} "
          f"(test: {str(dates_te.min())[:10]} to {str(dates_te.max())[:10]})")

    feature_scaler = pp.fit_feature_scaler(X_tr)
    X_tr_s = pp.apply_feature_scaler(feature_scaler, X_tr)
    X_val_s = pp.apply_feature_scaler(feature_scaler, X_val)
    X_te_s = pp.apply_feature_scaler(feature_scaler, X_te)

    day_scaler = pp.fit_target_scaler(yday_tr)
    week_scaler = pp.fit_target_scaler(yweek_tr)
    yday_tr_s = pp.apply_target_scaler(day_scaler, yday_tr)
    yday_val_s = pp.apply_target_scaler(day_scaler, yday_val)
    yweek_tr_s = pp.apply_target_scaler(week_scaler, yweek_tr)
    yweek_val_s = pp.apply_target_scaler(week_scaler, yweek_val)

    config = LSTMConfig(lookback=lookback, n_features=X_tr.shape[2])
    model = build_lstm_model(config)

    # Save into a NEW candidate version dir — never touches the currently
    # live version's files.
    candidate_paths = model_registry.begin_version(city)

    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=patience, restore_best_weights=True),
        keras.callbacks.ModelCheckpoint(str(candidate_paths.version_dir / "checkpoint.keras"), monitor="val_loss", save_best_only=True),
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

    preds = model.predict(X_te_s, verbose=0)
    yday_pred = pp.inverse_target_scaler(day_scaler, preds["next_day"])
    yweek_pred = pp.inverse_target_scaler(week_scaler, preds["next_week"])

    metrics = {
        "city": city,
        "state": CITY_TO_STATE[city],
        "version": candidate_paths.version_dir.name,
        "n_windows_total": int(len(X)),
        "n_train": int(len(X_tr)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_te)),
        "test_date_range": [str(dates_te.min())[:10], str(dates_te.max())[:10]],
        "epochs_run": len(history.history["loss"]),
        "train_seconds": train_seconds,
        "next_day": ev.compute_metrics(yday_te, yday_pred),
        "next_week": ev.compute_metrics(yweek_te, yweek_pred),
    }

    # Save candidate artifacts
    model.save(candidate_paths.model_path)
    joblib.dump(feature_scaler, candidate_paths.feature_scaler_path)
    joblib.dump(day_scaler, candidate_paths.next_day_scaler_path)
    joblib.dump(week_scaler, candidate_paths.next_week_scaler_path)
    joblib.dump(list(fe.DEFAULT_FEATURE_COLUMNS), candidate_paths.feature_columns_path)
    candidate_paths.metrics_path.write_text(json.dumps(metrics, indent=2))

    pd.DataFrame(history.history).to_csv(candidate_paths.version_dir / "training_history.csv", index_label="epoch")

    # --- Promotion gate ---
    if force_promote:
        should_promote, reason = True, "force_promote=True (manual override)"
    else:
        should_promote, reason = _should_promote(metrics, city, regression_tolerance_pct)

    metrics["promoted"] = should_promote
    metrics["promotion_reason"] = reason
    candidate_paths.metrics_path.write_text(json.dumps(metrics, indent=2))  # rewrite with promotion decision included

    if should_promote:
        model_registry.promote(city, candidate_paths.version_dir.name)

    print(f"  next_day  -> MAE={metrics['next_day']['mae_mw']} MW, RMSE={metrics['next_day']['rmse_mw']} MW, MAPE={metrics['next_day']['mape_pct']}%")
    print(f"  next_week -> MAE={metrics['next_week']['mae_mw']} MW, RMSE={metrics['next_week']['rmse_mw']} MW, MAPE={metrics['next_week']['mape_pct']}%")
    print(f"  version {metrics['version']} -> {'PROMOTED' if should_promote else 'NOT promoted'} ({reason})")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", type=str, default=None)
    parser.add_argument("--data-dir", type=str, required=True, help="Path to ml-training/data (contains raw/ and processed/).")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lookback", type=int, default=fe.LOOKBACK_DAYS)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--regression-tolerance-pct", type=float, default=DEFAULT_REGRESSION_TOLERANCE_PCT)
    parser.add_argument("--force-promote", action="store_true", help="Promote regardless of comparison to the current live model.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    cities = [args.city] if args.city else list(CITY_TO_STATE.keys())
    for c in cities:
        if c not in CITY_TO_STATE:
            raise ValueError(f"Unknown city '{c}'. Valid cities: {list(CITY_TO_STATE.keys())}")

    all_metrics, failures = [], []
    for city in cities:
        try:
            m = train_city(
                city, data_dir,
                epochs=args.epochs, batch_size=args.batch_size, lookback=args.lookback,
                patience=args.patience, verbose=0 if args.quiet else 1,
                regression_tolerance_pct=args.regression_tolerance_pct,
                force_promote=args.force_promote,
            )
            all_metrics.append(m)
        except Exception as e:  # noqa: BLE001 — one city's failure shouldn't abort a multi-city run
            print(f"  [FAILED] {city}: {e}")
            failures.append({"city": city, "error": str(e)})

    if all_metrics:
        summary = pd.DataFrame([{
            "city": m["city"], "version": m["version"], "promoted": m["promoted"],
            "next_day_mape_pct": m["next_day"]["mape_pct"], "next_week_mape_pct": m["next_week"]["mape_pct"],
        } for m in all_metrics])
        print(f"\n{'=' * 60}\n{summary.to_string(index=False)}\n{'=' * 60}")

    if failures:
        print(f"\n{len(failures)} failed:")
        for f in failures:
            print(f"  - {f['city']}: {f['error']}")


if __name__ == "__main__":
    main()