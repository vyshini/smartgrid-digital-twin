"""
LSTM model architecture for Phase 3 forecasting.

Single shared-encoder, dual-head network:
  - Input:  (lookback, n_features) window of real per-city features
            (see feature_engineering.py -> DEFAULT_FEATURE_COLUMNS)
  - Head 1: next_day  -> total_demand_mw at t+1  (point forecast)
  - Head 2: next_week -> total_demand_mw at t+7  (point forecast)

A shared encoder (rather than two independent models) is used because
next_day and next_week targets are strongly correlated (both are functions
of the same underlying demand trajectory) and share the same lookback
window; a shared trunk lets the two heads regularize each other and halves
the number of models to train/serve/version per city (8 models instead of
16). This is an architectural choice, not a claim that it's the only valid
one — two independent single-output LSTMs would also be defensible and are
noted as an alternative in the project report.

NOTE ON SANDBOX EXECUTION: this file (and train_lstm.py) was written
against TensorFlow/Keras 2.x but could not be imported or executed in the
sandbox this project was authored in (no `tensorflow` package installed,
no network access to pip-install it). Treat this the same way as
fetch_weather.py: validate on your own machine before trusting it — run
`python train_lstm.py --city Delhi --epochs 2` first as a smoke test
(cheap, fast) before a full run across all 8 cities.
"""
from __future__ import annotations

from dataclasses import dataclass

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


@dataclass
class LSTMConfig:
    """Hyperparameters for build_lstm_model. Defaults are reasonable
    starting points for a ~4000-6000 row daily series with ~19 features and
    a 14-day lookback (see feature_engineering.LOOKBACK_DAYS) — not tuned
    against a held-out validation set for any specific city. Treat as a
    starting point; tune per city if val loss plateaus early or overfits."""

    lookback: int = 14
    n_features: int = 19
    lstm_units_1: int = 128
    lstm_units_2: int = 64
    dense_units: int = 32
    dropout: float = 0.2
    recurrent_dropout: float = 0.0  # >0 disables cuDNN fused kernel; keep 0 unless overfitting persists
    l2_reg: float = 1e-5
    learning_rate: float = 1e-3
    loss_weights: dict | None = None  # e.g. {"next_day": 1.0, "next_week": 1.0}


def build_lstm_model(config: LSTMConfig) -> keras.Model:
    """
    Builds the shared-encoder, dual-head LSTM described in the module
    docstring. Returns a compiled keras.Model with two named outputs:
    'next_day' and 'next_week'.
    """
    reg = keras.regularizers.l2(config.l2_reg) if config.l2_reg > 0 else None

    inputs = keras.Input(shape=(config.lookback, config.n_features), name="feature_window")

    x = layers.LSTM(
        config.lstm_units_1,
        return_sequences=True,
        kernel_regularizer=reg,
        recurrent_dropout=config.recurrent_dropout,
        name="lstm_1",
    )(inputs)
    x = layers.Dropout(config.dropout, name="dropout_1")(x)

    x = layers.LSTM(
        config.lstm_units_2,
        return_sequences=False,
        kernel_regularizer=reg,
        recurrent_dropout=config.recurrent_dropout,
        name="lstm_2",
    )(x)
    x = layers.Dropout(config.dropout, name="dropout_2")(x)

    shared = layers.Dense(config.dense_units, activation="relu", kernel_regularizer=reg, name="shared_dense")(x)
    shared = layers.Dropout(config.dropout / 2, name="dropout_shared")(shared)

    # Head 1: next-day point forecast
    day_branch = layers.Dense(16, activation="relu", name="next_day_dense")(shared)
    next_day = layers.Dense(1, name="next_day")(day_branch)

    # Head 2: next-week point forecast — slightly larger branch since t+7
    # is a harder target (more compounding uncertainty over the horizon)
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
    """
    Sets seeds for reproducibility across numpy/tensorflow/python-random.
    NOTE: this reduces but does not eliminate run-to-run variance — cuDNN
    LSTM kernels on GPU are not bit-for-bit deterministic even with seeds
    fixed, unless TF_DETERMINISTIC_OPS is also set (which can slow
    training meaningfully). Don't over-trust a single run's exact numbers;
    treat metrics as approximate and re-run if a result looks surprising.
    """
    import os
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)