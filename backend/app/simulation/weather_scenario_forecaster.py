"""
Applies a WeatherPerturbation to the real feature window, then runs the
SAME LSTMForecaster.predict() path the live forecast API uses — a
scenario forecast is genuinely produced by the trained model reacting to
altered inputs, not a separately faked calculation.

Only real weather columns are perturbed (temperature_c, humidity_pct,
wind_speed_kmph, solar_irradiance, precipitation_mm), only within the
lookback window ending at as_of_date. Demand-lag features and calendar
features are deliberately left untouched — see module docstring reasoning
in scenarios.py.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

import pandas as pd

from app.ml.feature_engineering import LOOKBACK_DAYS
from app.ml.interfaces import ForecastHorizon, ForecastRequest, ForecastResult
from app.ml.lstm_model import LSTMForecaster
from app.simulation.scenarios import WeatherPerturbation


def apply_perturbation(
    df: pd.DataFrame,
    perturbation: WeatherPerturbation,
    as_of_date: date,
    lookback: int = LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Returns a COPY with weather columns altered across the lookback
    window ending at as_of_date. Never mutates the input — the real
    cached data (see CSVForecastDataProvider) must stay untouched for
    every other caller sharing that cache."""
    perturbed = df.copy(deep=True)

    as_of_ts = pd.Timestamp(as_of_date)
    window_start = as_of_ts - pd.Timedelta(days=lookback - 1)
    mask = (perturbed.index >= window_start) & (perturbed.index <= as_of_ts)

    perturbed.loc[mask, "temperature_c"] += perturbation.temperature_c_delta
    perturbed.loc[mask, "humidity_pct"] = (
        perturbed.loc[mask, "humidity_pct"] + perturbation.humidity_pct_delta
    ).clip(lower=0, upper=100)
    perturbed.loc[mask, "wind_speed_kmph"] = (
        perturbed.loc[mask, "wind_speed_kmph"] + perturbation.wind_speed_kmph_delta
    ).clip(lower=0)
    perturbed.loc[mask, "solar_irradiance"] = (
        perturbed.loc[mask, "solar_irradiance"] * perturbation.solar_irradiance_multiplier
    ).clip(lower=0)
    perturbed.loc[mask, "precipitation_mm"] = (
        perturbed.loc[mask, "precipitation_mm"] + perturbation.precipitation_mm_delta
    ).clip(lower=0)

    return perturbed


def forecast_under_scenario(
    base_feature_provider: Callable[[str], pd.DataFrame],
    city: str,
    perturbation: WeatherPerturbation,
    as_of_date: date,
    horizon: ForecastHorizon = ForecastHorizon.NEXT_DAY,
    lookback: int = LOOKBACK_DAYS,
) -> ForecastResult:
    """
    Produces a forecast under a hypothetical weather perturbation, using
    the same trained model/scalers the live API uses — only the input
    window differs.

    PERFORMANCE NOTE: constructs a fresh LSTMForecaster (reloading the
    Keras model + scalers from disk) rather than reusing an already-warm
    cached instance, since LSTMForecaster's cache is keyed by city and
    doesn't distinguish "real data" from "perturbed data" for the same
    city — reusing the live cached instance risks accidentally serving a
    perturbed prediction to a normal, non-scenario forecast call
    afterward. This costs a few extra seconds per scenario run; acceptable
    for an occasional simulation call, not something to optimize
    prematurely.
    """
    base_df = base_feature_provider(city)
    perturbed_df = apply_perturbation(base_df, perturbation, as_of_date, lookback)

    def _scenario_provider(requested_city: str) -> pd.DataFrame:
        if requested_city != city:
            raise ValueError(f"This scenario forecaster is scoped to '{city}', not '{requested_city}'.")
        return perturbed_df

    scenario_forecaster = LSTMForecaster(feature_data_provider=_scenario_provider, lookback=lookback)
    return scenario_forecaster.predict(ForecastRequest(city=city, horizon=horizon, as_of_date=as_of_date))