"""
Scaling and windowing logic shared by trainer.py (training-time) and
lstm_model.py's Forecaster implementation (prediction-time).

This is a direct port of the scaling functions from
ml-training/scripts/train_lstm.py — same StandardScaler-fit-on-train-only
approach, same reshape-to-2D-to-fit trick — relocated here so both the
offline trainer and the online prediction path use IDENTICAL scaling code.
That identity matters: if trainer.py and the prediction path scaled
features even slightly differently, predictions would be silently wrong
in a way that's hard to detect (no error, just bad numbers).

`build_prediction_window` is new here (didn't exist in the training
script) — training builds thousands of sliding windows over history;
serving a live prediction needs exactly one window: the most recent
`lookback` days of real data as of `as_of_date`.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


class InsufficientHistoryError(Exception):
    """Raised when fewer than `lookback` real, contiguous daily rows exist
    ending at as_of_date — e.g. a new city with too little history yet, or
    a gap in ingested data. Never silently pad/fabricate missing days to
    make a window fit."""


# ---------------------------------------------------------------------------
# Fitting / applying scalers (training-time; ported unchanged from
# ml-training/scripts/train_lstm.py)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Single-window construction for live prediction (serving-time; new)
# ---------------------------------------------------------------------------

def build_prediction_window(
    df: pd.DataFrame,
    feature_cols: list[str],
    as_of_date: date,
    lookback: int,
) -> np.ndarray:
    """
    Builds ONE unscaled feature window of shape (lookback, n_features),
    covering the `lookback` real calendar days ending at `as_of_date`
    (inclusive), from an already feature-engineered DataFrame (i.e. the
    output of feature_engineering.load_city_dataset +
    feature_engineering.add_lag_features — same as what trainer.py feeds
    into build_supervised_windows).

    Raises InsufficientHistoryError rather than padding with zeros/NaNs or
    silently using a shorter window — a forecast built on a shorter,
    unrequested lookback would be a different (and unvalidated) model
    behavior than what was trained and evaluated.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("build_prediction_window expects a DataFrame indexed by date.")

    as_of_ts = pd.Timestamp(as_of_date)
    if as_of_ts not in df.index:
        raise InsufficientHistoryError(
            f"No real data row for as_of_date={as_of_date}. The most recent "
            f"available date is {df.index.max().date()}."
        )

    window_start = as_of_ts - pd.Timedelta(days=lookback - 1)
    window = df.loc[window_start:as_of_ts]

    if len(window) != lookback:
        raise InsufficientHistoryError(
            f"Need {lookback} contiguous real days ending {as_of_date}, "
            f"found {len(window)} (expected range {window_start.date()} to "
            f"{as_of_date}). Likely a gap in ingested data — see "
            f"data_preparation.report_coverage() for known gaps."
        )

    expected_dates = pd.date_range(window_start, as_of_ts, freq="D")
    if not window.index.equals(expected_dates):
        raise InsufficientHistoryError(
            f"Window for as_of_date={as_of_date} is not contiguous daily data "
            f"(gap inside the {lookback}-day lookback range) — refusing to "
            f"build a prediction window over a real gap."
        )

    missing_cols = [c for c in feature_cols if c not in window.columns]
    if missing_cols:
        raise ValueError(f"Missing expected feature columns: {missing_cols}")

    if window[feature_cols].isna().any().any():
        nan_cols = window[feature_cols].columns[window[feature_cols].isna().any()].tolist()
        raise InsufficientHistoryError(
            f"Window for as_of_date={as_of_date} has NaN values in columns "
            f"{nan_cols} (likely a lag/rolling feature falling too close to "
            f"the start of this city's real data)."
        )

    return window[feature_cols].to_numpy(dtype=np.float32)