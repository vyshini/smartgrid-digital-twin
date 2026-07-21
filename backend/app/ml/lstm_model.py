"""
Two things live here, per the project tree's comment ("lstm_model.py #
Keras model definition"):

1. The architecture itself (LSTMConfig, build_lstm_model) — a direct port
   of ml-training/scripts/model.py, unchanged, so a model trained offline
   with that script and one built here are structurally identical. This
   is what trainer.py imports to build a fresh model for a training run.

2. `LSTMForecaster` — the concrete implementation of the `Forecaster` ABC
   (interfaces.py) that application/forecasting/forecast_city_load_use_case.py
   actually calls. This is the boundary between "we have a trained model
   on disk" and "the rest of the backend can ask for a forecast."

Deliberate dependency direction: LSTMForecaster does NOT import anything
from infrastructure/ (no DB session, no repository class) — it takes a
`feature_data_provider` callable in its constructor instead. Wiring which
concrete provider it gets (a real DB-backed repository in production, a
CSV-backed one in dev/tests) happens at composition time in main.py /
api/deps.py, not here. This keeps the ML layer honestly a "plugin," as
the architecture requires — it depends on interfaces.py and
preprocessing.py, not on infrastructure.

NOTE ON SANDBOX EXECUTION: same caveat as ml-training/scripts/model.py —
written against TensorFlow/Keras 2.x, not executable in the authoring
sandbox (no tensorflow installed). preprocessing.py and model_registry.py
were fully unit-tested there since they don't need TensorFlow; this file
needs a real environment to import-check.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from . import model_registry, preprocessing
from .interfaces import Forecaster, ForecastHorizon, ForecastRequest, ForecastResult
from .model_registry import ModelNotFoundError


# ---------------------------------------------------------------------------
# 1. Architecture — ported from ml-training/scripts/model.py
# ---------------------------------------------------------------------------

@dataclass
class LSTMConfig:
    lookback: int = 14
    n_features: int = 19
    lstm_units_1: int = 128
    lstm_units_2: int = 64
    dense_units: int = 32
    dropout: float = 0.2
    recurrent_dropout: float = 0.0
    l2_reg: float = 1e-5
    learning_rate: float = 1e-3
    loss_weights: dict | None = None


def build_lstm_model(config: LSTMConfig) -> keras.Model:
    reg = keras.regularizers.l2(config.l2_reg) if config.l2_reg > 0 else None

    inputs = keras.Input(shape=(config.lookback, config.n_features), name="feature_window")

    x = layers.LSTM(
        config.lstm_units_1, return_sequences=True, kernel_regularizer=reg,
        recurrent_dropout=config.recurrent_dropout, name="lstm_1",
    )(inputs)
    x = layers.Dropout(config.dropout, name="dropout_1")(x)

    x = layers.LSTM(
        config.lstm_units_2, return_sequences=False, kernel_regularizer=reg,
        recurrent_dropout=config.recurrent_dropout, name="lstm_2",
    )(x)
    x = layers.Dropout(config.dropout, name="dropout_2")(x)

    shared = layers.Dense(config.dense_units, activation="relu", kernel_regularizer=reg, name="shared_dense")(x)
    shared = layers.Dropout(config.dropout / 2, name="dropout_shared")(shared)

    day_branch = layers.Dense(16, activation="relu", name="next_day_dense")(shared)
    next_day = layers.Dense(1, name="next_day")(day_branch)

    week_branch = layers.Dense(24, activation="relu", name="next_week_dense")(shared)
    week_branch = layers.Dropout(config.dropout / 2, name="dropout_week")(week_branch)
    next_week = layers.Dense(1, name="next_week")(week_branch)

    model = keras.Model(inputs=inputs, outputs={"next_day": next_day, "next_week": next_week}, name="lstm_demand_forecaster")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=config.learning_rate),
        loss={"next_day": "mse", "next_week": "mse"},
        loss_weights=config.loss_weights or {"next_day": 1.0, "next_week": 1.0},
        metrics={"next_day": ["mae"], "next_week": ["mae"]},
    )
    return model


def set_global_seed(seed: int = 42) -> None:
    import os
    import random
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


# ---------------------------------------------------------------------------
# 2. Forecaster implementation — the thing the use case actually calls
# ---------------------------------------------------------------------------

@dataclass
class _LoadedCity:
    version: str
    model: keras.Model
    feature_scaler: object
    day_scaler: object
    week_scaler: object
    feature_cols: list[str]


class LSTMForecaster(Forecaster):
    """
    feature_data_provider(city) -> pd.DataFrame must return the SAME shape
    of feature-engineered data trainer.py trained on (i.e. the output of
    feature_engineering.load_city_dataset + add_lag_features): a
    DatetimeIndex, with at least all columns in the saved feature_cols
    list, extending up to (at least) the requested as_of_date.

    Caches one loaded (model, scalers) set per city in memory, keyed by
    registry version — if model_registry.promote() points `latest` at a
    new version between calls, the next predict() for that city will
    detect the version mismatch and reload rather than silently keep
    serving the old promoted model from cache.
    """

    def __init__(self, feature_data_provider: Callable[[str], pd.DataFrame], lookback: int = 14):
        self._feature_data_provider = feature_data_provider
        self._lookback = lookback
        self._cache: dict[str, _LoadedCity] = {}

    def _load(self, city: str) -> _LoadedCity:
        current = model_registry.current_version(city)  # raises ModelNotFoundError if none promoted
        cached = self._cache.get(city)
        if cached is not None and cached.version == current:
            return cached

        paths = model_registry.latest_paths(city)
        loaded = _LoadedCity(
            version=current,
            model=keras.models.load_model(paths.model_path),
            feature_scaler=joblib.load(paths.feature_scaler_path),
            day_scaler=joblib.load(paths.next_day_scaler_path),
            week_scaler=joblib.load(paths.next_week_scaler_path),
            feature_cols=joblib.load(paths.feature_columns_path),
        )
        self._cache[city] = loaded
        return loaded

    def model_version(self, city: str) -> str:
        return model_registry.current_version(city)

    def predict(self, request: ForecastRequest) -> ForecastResult:
        loaded = self._load(request.city)

        df = self._feature_data_provider(request.city)
        window = preprocessing.build_prediction_window(
            df, loaded.feature_cols, request.as_of_date, self._lookback
        )
        window_batch = window[np.newaxis, ...]  # (1, lookback, n_features)
        window_scaled = preprocessing.apply_feature_scaler(loaded.feature_scaler, window_batch)

        raw = loaded.model.predict(window_scaled, verbose=0)

        if request.horizon == ForecastHorizon.NEXT_DAY:
            predicted_mw = float(preprocessing.inverse_target_scaler(loaded.day_scaler, raw["next_day"])[0])
            target_date = request.as_of_date + timedelta(days=1)
        elif request.horizon == ForecastHorizon.NEXT_WEEK:
            predicted_mw = float(preprocessing.inverse_target_scaler(loaded.week_scaler, raw["next_week"])[0])
            target_date = request.as_of_date + timedelta(days=7)
        else:
            raise ValueError(f"Unsupported horizon: {request.horizon}")

        return ForecastResult(
            city=request.city,
            horizon=request.horizon,
            predicted_mw=round(predicted_mw, 3),
            as_of_date=request.as_of_date,
            target_date=target_date,
            model_version=loaded.version,
            confidence_interval_mw=None,  # honest: no calibrated interval, see interfaces.py
        )