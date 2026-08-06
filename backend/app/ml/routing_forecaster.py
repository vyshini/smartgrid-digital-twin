"""
RoutingForecaster -- a THIRD implementation of the Forecaster ABC that
wraps the other two (LSTMForecaster, GBTForecaster) and delegates to
whichever one ml-training/results/model_routing.json says won the
benchmark for a given (city, horizon). This is the champion-challenger
selection from compare_models.py, made live.

If routing.json says "persistence" for a (city, horizon) -- meaning
neither trained model beat naive persistence there (see
model_comparison.csv) -- this returns a genuine persistence forecast
(predicted_mw = today's real anchor value) rather than silently serving
whichever model happens to be wired up. Reports this via model_version
so a caller can see plainly that no trained model backs that number.

This is the ONLY Forecaster implementation application/forecasting/
forecast_city_load_use_case.py needs to import -- LSTMForecaster and
GBTForecaster stay implementation details behind it, per this project's
existing plugin-boundary pattern (see interfaces.py's docstring).
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from .gbt_model import GBTForecaster
from .interfaces import Forecaster, ForecastHorizon, ForecastRequest, ForecastResult
from .lstm_model import LSTMForecaster

DEFAULT_ROUTING_PATH = Path(__file__).parent.parent.parent.parent / "ml-training" / "results" / "model_routing.json"


class RoutingForecaster(Forecaster):
    def __init__(
        self,
        feature_data_provider: Callable[[str], pd.DataFrame],
        routing_path: Path = DEFAULT_ROUTING_PATH,
        lookback: int = 14,
    ):
        self._feature_data_provider = feature_data_provider
        self._lstm = LSTMForecaster(feature_data_provider=feature_data_provider, lookback=lookback)
        self._gbt = GBTForecaster(feature_data_provider=feature_data_provider)
        self._routing = self._load_routing(routing_path)

    @staticmethod
    def _load_routing(routing_path: Path) -> dict:
        if not routing_path.exists():
            raise FileNotFoundError(
                f"No model_routing.json at {routing_path} -- run "
                f"ml-training/scripts/compare_models.py first to generate it."
            )
        return json.loads(routing_path.read_text())

    def _route_for(self, city: str, horizon: ForecastHorizon) -> str:
        city_routing = self._routing.get(city)
        if city_routing is None:
            raise ValueError(
                f"No routing entry for '{city}' in model_routing.json -- "
                f"was this city included in the compare_models.py run?"
            )
        model_type = city_routing.get(horizon.value)
        if model_type is None:
            raise ValueError(f"No routing entry for '{city}'/{horizon.value} in model_routing.json")
        return model_type

    def model_version(self, city: str) -> str:
        # Ambiguous for a routing forecaster -- next_day and next_week can
        # route to different models. Callers needing a specific model's
        # version should inspect predict()'s returned ForecastResult
        # instead, which is always correct for that specific horizon.
        day_route = self._route_for(city, ForecastHorizon.NEXT_DAY)
        week_route = self._route_for(city, ForecastHorizon.NEXT_WEEK)
        return f"routed(next_day={day_route}, next_week={week_route})"

    def predict(self, request: ForecastRequest) -> ForecastResult:
        model_type = self._route_for(request.city, request.horizon)

        if model_type == "lstm":
            result = self._lstm.predict(request)
            return result.__class__(
                **{**result.__dict__, "model_version": f"lstm/{result.model_version}"}
            )

        if model_type == "gbt":
            result = self._gbt.predict(request)
            return result.__class__(
                **{**result.__dict__, "model_version": f"gbt/{result.model_version}"}
            )

        if model_type == "persistence":
            # Real, honest persistence forecast -- not a placeholder.
            df = self._feature_data_provider(request.city)
            anchor_ts = pd.Timestamp(request.as_of_date)
            if anchor_ts not in df.index:
                raise ValueError(f"No real data row for as_of_date={request.as_of_date}.")
            anchor_mw = float(df.loc[anchor_ts, "total_demand_mw"])
            target_date = request.as_of_date + (
                timedelta(days=1) if request.horizon == ForecastHorizon.NEXT_DAY else timedelta(days=7)
            )
            return ForecastResult(
                city=request.city,
                horizon=request.horizon,
                predicted_mw=round(anchor_mw, 3),
                as_of_date=request.as_of_date,
                target_date=target_date,
                model_version="persistence/no-trained-model-beat-baseline",
                confidence_interval_mw=None,
            )

        raise ValueError(f"Unknown routed model_type '{model_type}' for {request.city}/{request.horizon.value}")