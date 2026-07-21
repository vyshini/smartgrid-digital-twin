"""
A `feature_data_provider` callable for `LSTMForecaster` (see
app/ml/lstm_model.py), backed directly by the CSVs in ml-training/data/
instead of a database.

This exists so the forecast API can be tested end-to-end TODAY, before
infrastructure/repositories/ has a real Postgres-backed source for
per-city demand+weather+calendar history. It implements the exact same
callable shape (`city: str -> pd.DataFrame`) that a future
`PostgresForecastDataProvider` would — swapping one for the other is a
one-line change at composition time (api/deps.py), nothing in
app/ml/lstm_model.py or the use case needs to change.

CACHING NOTE: loads + feature-engineers a city's full history once, then
serves it from memory for the rest of the process's lifetime. This is
fine for a dev/demo deployment where the data is static CSVs that don't
change underneath the running process. It is NOT fine as-is for
production, where new daily demand/weather rows should be arriving
continuously (see the spec's "continuously collect -> clean -> predict"
requirement) — a real DB-backed provider should not cache indefinitely,
or should invalidate/refresh on new data arrival. Flagging this rather
than silently shipping a caching strategy that would quietly go stale in
production.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.ml import feature_engineering as fe


class CSVForecastDataProvider:
    """Callable: instance(city) -> pd.DataFrame, matching the
    feature_data_provider shape LSTMForecaster expects."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._cache: dict[str, pd.DataFrame] = {}

    def __call__(self, city: str) -> pd.DataFrame:
        if city not in self._cache:
            df = fe.load_city_dataset(city, self._data_dir)
            df = fe.add_lag_features(df)
            self._cache[city] = df
        return self._cache[city]

    def refresh(self, city: str | None = None) -> None:
        """Drops cached data so the next call re-reads from disk. Call
        this after ml-training/scripts/build_training_dataset.py or
        fetch_weather.py produce new data — there is no automatic
        invalidation here, see the module docstring's caching note."""
        if city is None:
            self._cache.clear()
        else:
            self._cache.pop(city, None)