"""
Dependency providers for forecasting. Kept in a separate module rather
than assumed to merge cleanly into an existing api/deps.py (built in an
earlier session this one doesn't have visibility into) — copy the
`get_forecast_use_case` provider into your existing deps.py if you'd
rather have one shared file, the logic doesn't care where it lives.

Wiring point for swapping the data source later: `_build_data_provider()`
is the ONLY function that needs to change to move from CSV-backed dev
data to a real Postgres-backed infrastructure/repositories/ source —
everything downstream (LSTMForecaster, the use case, the router) depends
on the feature_data_provider callable shape, not on where the data
actually comes from.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.application.forecasting.forecast_city_load_use_case import ForecastCityLoadUseCase
from app.core.config import get_settings
from app.infrastructure.repositories.csv_forecast_data_provider import CSVForecastDataProvider
from app.ml.feature_engineering import LOOKBACK_DAYS
from app.ml.interfaces import Forecaster
from app.ml.lstm_model import LSTMForecaster


def _build_data_provider() -> CSVForecastDataProvider:
    """
    Dev-mode data source, path sourced from Settings.ML_DATA_DIR (see
    core/config.py — add this field there if it isn't present yet, same
    pattern as PROJECT_NAME / API_V1_PREFIX).

    TODO(production): replace with a Postgres-backed provider reading
    from infrastructure/db once the ForecastHistory / Weather tables
    (see docs/database-schema.sql) are being populated by a real
    ingestion pipeline, not static CSVs.
    """
    settings = get_settings()
    data_dir = Path(settings.ML_DATA_DIR)
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Settings.ML_DATA_DIR resolved to '{data_dir.resolve()}', which doesn't "
            f"exist. Check your .env / ML_DATA_DIR setting, or run this process from "
            f"the repo root where ml-training/data/ lives."
        )
    return CSVForecastDataProvider(data_dir)


@lru_cache(maxsize=1)
def get_forecaster() -> Forecaster:
    """
    Singleton for the process lifetime — LSTMForecaster caches loaded
    Keras models per city internally (see lstm_model.py), so constructing
    it once and reusing it avoids reloading every model from disk on
    every request.
    """
    provider = _build_data_provider()
    return LSTMForecaster(feature_data_provider=provider, lookback=LOOKBACK_DAYS)


def get_forecast_use_case() -> ForecastCityLoadUseCase:
    """FastAPI dependency — use with `Depends(get_forecast_use_case)` in
    api/v1/forecast.py."""
    return ForecastCityLoadUseCase(forecaster=get_forecaster())

@lru_cache(maxsize=1)
def get_data_provider() -> CSVForecastDataProvider:
    """Public accessor for the shared CSV-backed feature provider — used
    directly by simulation scenarios, which need the raw feature
    DataFrame (to perturb) rather than a finished ForecastResult."""
    return _build_data_provider()