"""
Use case for "predict a city's load" — the only thing api/v1/forecast.py
should call for predictions. Deliberately thin: no business logic lives
here beyond input validation and exception translation, since the actual
work (loading a model, building a feature window, scaling, predicting)
belongs to the ml/ plugin layer behind the Forecaster interface.

Why translate ml/'s exceptions (ModelNotFoundError,
preprocessing.InsufficientHistoryError) into application/forecasting/
exceptions.py's versions rather than letting them bubble straight to the
API layer: it keeps api/v1/forecast.py's error handling decoupled from
knowing the current forecaster implementation is ml/ at all — if a future
Forecaster implementation (a different model family, a stub for tests)
raised different underlying exceptions, this use case is the one place
that needs updating, not the router.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.ml.interfaces import Forecaster, ForecastHorizon, ForecastRequest, ForecastResult
from app.ml.model_registry import ModelNotFoundError
from app.ml.preprocessing import InsufficientHistoryError

from .exceptions import ForecastUnavailableError, InsufficientForecastHistoryError, UnknownCityError

# Kept here rather than imported from ml/trainer.py (application/ should
# not depend on ml/'s training internals, only on interfaces.py) — if
# domain/entities/city.py already enumerates valid cities elsewhere in
# this project, prefer wiring that in as the source of truth instead of
# this duplicated list.
SUPPORTED_CITIES = {
    "Delhi", "Mumbai", "Pune", "Bangalore",
    "Hyderabad", "Chennai", "Kolkata", "Ahmedabad",
}


@dataclass(frozen=True)
class ForecastCityLoadInput:
    city: str
    horizon: ForecastHorizon
    as_of_date: date | None = None  # None -> defaults to yesterday, see execute()


class ForecastCityLoadUseCase:
    def __init__(self, forecaster: Forecaster):
        self._forecaster = forecaster

    def execute(self, request: ForecastCityLoadInput) -> ForecastResult:
        city = self._normalize_city(request.city)

        # Default as_of_date to yesterday, not today: "today" is still in
        # progress and its features (e.g. rolling averages, full-day
        # weather) won't be complete real data yet — predicting off an
        # incomplete "today" row would be predicting off partially
        # fabricated inputs, which this project's data-honesty stance
        # (see ml-training/scripts/data_preparation.py's docstring)
        # explicitly avoids elsewhere.
        as_of_date = request.as_of_date or (date.today() - timedelta(days=1))

        forecast_request = ForecastRequest(city=city, horizon=request.horizon, as_of_date=as_of_date)

        try:
            return self._forecaster.predict(forecast_request)
        except ModelNotFoundError as e:
            raise ForecastUnavailableError(
                f"No trained model available for '{city}' yet. {e}"
            ) from e
        except InsufficientHistoryError as e:
            raise InsufficientForecastHistoryError(str(e)) from e

    @staticmethod
    def _normalize_city(city: str) -> str:
        # Case-insensitive match against the supported set, but returns
        # the canonical-cased name the Forecaster/model_registry expect
        # (artifacts are stored under city.lower(), but ForecastRequest /
        # feature_data_provider callers use the display-cased name
        # throughout this project — e.g. "Delhi", not "delhi").
        matches = [c for c in SUPPORTED_CITIES if c.lower() == city.lower()]
        if not matches:
            raise UnknownCityError(
                f"'{city}' is not a supported city. Supported: {sorted(SUPPORTED_CITIES)}"
            )
        return matches[0]