"""
Evaluation utilities used by:
  - trainer.py (compute_metrics — the same function, no longer duplicated
    inline as it was in the first version of trainer.py)
  - a future analytics/reports endpoint (get_loss_curve,
    get_actual_vs_predicted) — the spec's Analytics module asks for
    "Prediction Accuracy" and "Actual vs Predicted" charts, and a report
    endpoint needs the same underlying data, just formatted differently
    (JSON for the API, a table for the PDF/Excel/CSV generators in
    infrastructure/reports/).

get_actual_vs_predicted re-runs prediction over the TEST split only (the
same chronological holdout trainer.py evaluated on) — never over
train/val, which would show an artificially good-looking fit and
misrepresent the model's real accuracy on unseen dates. This mirrors why
trainer.py itself only reports metrics computed on the test split.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from tensorflow import keras

from . import feature_engineering as fe
from . import model_registry
from . import preprocessing as pp
from .interfaces import ForecastHorizon
from .model_registry import ModelNotFoundError

# Re-exported so callers don't need to import trainer.py just for the
# split boundaries — evaluator.py depending on trainer.py (rather than
# the reverse) would risk a circular import once trainer.py starts
# calling evaluator.compute_metrics instead of its own inline copy.
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15


# ---------------------------------------------------------------------------
# Metrics — the canonical version; trainer.py imports this instead of
# keeping its own copy.
# ---------------------------------------------------------------------------

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE, RMSE, MAPE in real MW (post inverse-transform). MAPE guards
    against near-zero actual-demand rows (defensive; city-level total
    demand is never realistically near zero, but never trust that
    blindly)."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    nonzero = np.abs(y_true) > 1e-6
    mape = float(np.mean(np.abs(errors[nonzero] / y_true[nonzero])) * 100) if nonzero.sum() else float("nan")
    return {"mae_mw": round(mae, 3), "rmse_mw": round(rmse, 3), "mape_pct": round(mape, 3)}


def _time_based_split_indices(n: int, train_frac: float = TRAIN_FRAC, val_frac: float = VAL_FRAC) -> tuple[int, int]:
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return train_end, val_end


# ---------------------------------------------------------------------------
# Loss curve — reads what trainer.py already saved, no retraining needed.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LossCurvePoint:
    epoch: int
    loss: float
    val_loss: float
    next_day_loss: float | None
    next_day_val_loss: float | None
    next_week_loss: float | None
    next_week_val_loss: float | None


def get_loss_curve(city: str, version: str | None = None) -> list[LossCurvePoint]:
    """
    Reads training_history.csv from the given version's artifact
    directory (or the currently-promoted version if none given). Returns
    one point per epoch — chart-ready, no retraining.
    """
    version = version or model_registry.current_version(city)
    history_path = model_registry.paths_for(city, version).version_dir / "training_history.csv"
    if not history_path.exists():
        raise FileNotFoundError(
            f"No training_history.csv for {city} version {version} — was this "
            f"version trained by trainer.py (not the offline ml-training script)?"
        )

    df = pd.read_csv(history_path, index_col="epoch")
    points = []
    for epoch, row in df.iterrows():
        points.append(LossCurvePoint(
            epoch=int(epoch),
            loss=float(row.get("loss", float("nan"))),
            val_loss=float(row.get("val_loss", float("nan"))),
            next_day_loss=float(row["next_day_loss"]) if "next_day_loss" in row else None,
            next_day_val_loss=float(row["val_next_day_loss"]) if "val_next_day_loss" in row else None,
            next_week_loss=float(row["next_week_loss"]) if "next_week_loss" in row else None,
            next_week_val_loss=float(row["val_next_week_loss"]) if "val_next_week_loss" in row else None,
        ))
    return points


# ---------------------------------------------------------------------------
# Actual vs. predicted — re-runs prediction over the TEST split only.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActualVsPredictedPoint:
    date: str  # target date (ISO), i.e. the date being predicted, not the window-end date
    actual_mw: float
    predicted_mw: float


def get_actual_vs_predicted(
    city: str,
    data_dir: Path,
    horizon: ForecastHorizon,
    version: str | None = None,
    lookback: int = fe.LOOKBACK_DAYS,
) -> list[ActualVsPredictedPoint]:
    """
    Rebuilds the same test-split windows trainer.py evaluated the model
    on, runs the promoted (or specified) model's predictions over them,
    and pairs each with its real actual value — for the "Actual vs
    Predicted" chart in the Analytics module.

    Deliberately does NOT reuse a cached in-memory model (unlike
    lstm_model.LSTMForecaster) — this is an occasional analytics/reporting
    call, not a hot prediction path, so simplicity here is worth more than
    the caching complexity that'd add.
    """
    version = version or model_registry.current_version(city)
    paths = model_registry.paths_for(city, version)

    df = fe.load_city_dataset(city, data_dir)
    df = fe.add_lag_features(df)
    feature_cols = list(joblib.load(paths.feature_columns_path))

    X, y_day, y_week, dates = fe.build_supervised_windows(df, feature_cols, lookback=lookback)
    if len(X) == 0:
        raise ValueError(f"No usable windows for {city} — cannot compute actual-vs-predicted.")

    train_end, val_end = _time_based_split_indices(len(X))
    X_te = X[val_end:]
    y_day_te = y_day[val_end:]
    y_week_te = y_week[val_end:]
    dates_te = dates[val_end:]  # these are WINDOW-END dates, not target dates

    model = keras.models.load_model(paths.model_path)
    feature_scaler = joblib.load(paths.feature_scaler_path)
    day_scaler = joblib.load(paths.next_day_scaler_path)
    week_scaler = joblib.load(paths.next_week_scaler_path)

    X_te_s = pp.apply_feature_scaler(feature_scaler, X_te)
    preds = model.predict(X_te_s, verbose=0)

    if horizon == ForecastHorizon.NEXT_DAY:
        y_actual = y_day_te
        y_pred = pp.inverse_target_scaler(day_scaler, preds["next_day"])
        offset_days = 1
    elif horizon == ForecastHorizon.NEXT_WEEK:
        y_actual = y_week_te
        y_pred = pp.inverse_target_scaler(week_scaler, preds["next_week"])
        offset_days = 7
    else:
        raise ValueError(f"Unsupported horizon: {horizon}")

    target_dates = pd.to_datetime(dates_te) + pd.Timedelta(days=offset_days)

    return [
        ActualVsPredictedPoint(
            date=target_dates[i].date().isoformat(),
            actual_mw=round(float(y_actual[i]), 3),
            predicted_mw=round(float(y_pred[i]), 3),
        )
        for i in range(len(y_actual))
    ]