"""
GBTForecaster — a second, concrete implementation of the same `Forecaster`
ABC that LSTMForecaster implements (see interfaces.py). Exists because
compare_models.py's benchmark showed a LightGBM model beats the LSTM on
several city/horizon combinations (smoother, population-apportioned
cities especially) -- see ml-training/results/model_comparison.csv for
the evidence this routing decision is based on.

Mirrors LSTMForecaster's shape deliberately: same feature_data_provider
callable, same predict(request) -> ForecastResult contract, so
RoutingForecaster (routing_forecaster.py) can swap between the two
without either one knowing the other exists.

Artifact layout on disk, one dir per city:
    artifacts_gbt/<city>/
        next_day_model.joblib
        next_week_model.joblib
        feature_columns.joblib
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import joblib
import numpy as np
import pandas as pd

from .interfaces import Forecaster, ForecastHorizon, ForecastRequest, ForecastResult
from .model_registry import ModelNotFoundError

ARTIFACTS_DIR = Path(__file__).parent / "artifacts_gbt"


class GBTForecaster(Forecaster):
    """
    feature_data_provider(city) -> pd.DataFrame -- SAME contract as
    LSTMForecaster: a DataFrame with a DatetimeIndex, feature-engineered
    (load_city_dataset + add_lag_features), extending up to at least the
    requested as_of_date. GBT additionally needs cooling_degree_days /
    heating_degree_days columns (added in gbt_full.py's pipeline) -- if
    the provider doesn't compute these, GBTForecaster computes them
    itself from temperature_c so it never silently predicts on missing
    features.
    """

    def __init__(self, feature_data_provider: Callable[[str], pd.DataFrame]):
        self._feature_data_provider = feature_data_provider
        self._cache: dict[str, dict] = {}

    def _load(self, city: str) -> dict:
        if city in self._cache:
            return self._cache[city]

        city_dir = ARTIFACTS_DIR / city.lower()
        day_path = city_dir / "next_day_model.joblib"
        week_path = city_dir / "next_week_model.joblib"
        cols_path = city_dir / "feature_columns.joblib"

        missing = [p for p in (day_path, week_path, cols_path) if not p.exists()]
        if missing:
            raise ModelNotFoundError(
                f"No GBT artifacts for '{city}' -- missing {[str(p) for p in missing]}. "
                f"Run gbt_full.py and copy artifacts into {city_dir}, or route this "
                f"city to the LSTM instead (see model_routing.json)."
            )

        loaded = {
            "next_day_model": joblib.load(day_path),
            "next_week_model": joblib.load(week_path),
            "feature_cols": joblib.load(cols_path),
        }
        self._cache[city] = loaded
        return loaded

    def model_version(self, city: str) -> str:
        # GBT artifacts aren't versioned the way model_registry.py
        # versions LSTM checkpoints (no promote/rollback yet) -- flagged
        # honestly as a gap rather than a fabricated version string.
        return "gbt-unversioned"

    def _build_feature_row(self, df: pd.DataFrame, feature_cols: list[str], as_of_date: date) -> pd.DataFrame:
        as_of_ts = pd.Timestamp(as_of_date)
        if as_of_ts not in df.index:
            raise ValueError(
                f"No real data row for as_of_date={as_of_date}. "
                f"Most recent available date is {df.index.max().date()}."
            )

        row = df.loc[[as_of_ts]].copy()

        # Compute degree-days here if the provider hasn't already --
        # keeps GBTForecaster self-sufficient rather than silently
        # depending on caller-side feature engineering staying in sync.
        if "cooling_degree_days" not in row.columns:
            row["cooling_degree_days"] = (row["temperature_c"] - 24.0).clip(lower=0)
        if "heating_degree_days" not in row.columns:
            row["heating_degree_days"] = (18.0 - row["temperature_c"]).clip(lower=0)

        missing_cols = [c for c in feature_cols if c not in row.columns]
        if missing_cols:
            raise ValueError(f"Missing expected feature columns for GBT prediction: {missing_cols}")

        if row[feature_cols].isna().any().any():
            raise ValueError(f"NaN values in required features for as_of_date={as_of_date} -- cannot predict.")

        return row[feature_cols]

    def predict(self, request: ForecastRequest) -> ForecastResult:
        loaded = self._load(request.city)
        df = self._feature_data_provider(request.city)

        feature_row = self._build_feature_row(df, loaded["feature_cols"], request.as_of_date)
        anchor_mw = float(df.loc[pd.Timestamp(request.as_of_date), "total_demand_mw"])

        if request.horizon == ForecastHorizon.NEXT_DAY:
            model = loaded["next_day_model"]
            target_date = request.as_of_date + timedelta(days=1)
        elif request.horizon == ForecastHorizon.NEXT_WEEK:
            model = loaded["next_week_model"]
            target_date = request.as_of_date + timedelta(days=7)
        else:
            raise ValueError(f"Unsupported horizon: {request.horizon}")

        predicted_delta = float(model.predict(feature_row)[0])
        predicted_mw = anchor_mw + predicted_delta  # GBT also predicts deltas -- same reconstruction as the LSTM path

        return ForecastResult(
            city=request.city,
            horizon=request.horizon,
            predicted_mw=round(predicted_mw, 3),
            as_of_date=request.as_of_date,
            target_date=target_date,
            model_version=self.model_version(request.city),
            confidence_interval_mw=None,
        )