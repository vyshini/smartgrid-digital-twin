"""
The `Forecaster` interface is the one thing the rest of the backend is
allowed to depend on for load prediction. `application/forecasting/
forecast_city_load_use_case.py` calls THIS, never `lstm_model.py` or
`model_registry.py` directly — that's what makes it possible to swap in a
different model family later (e.g. a Transformer, or an ensemble) without
touching the use-case, the API router, or the dashboard.

This mirrors the `quantum/interfaces.py` `GridOptimizer` ABC pattern from
the same architecture: both ML and Quantum are "plugins" behind a domain
port, per the project's Clean Architecture requirement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum


class ForecastHorizon(str, Enum):
    NEXT_DAY = "next_day"
    NEXT_WEEK = "next_week"


@dataclass(frozen=True)
class ForecastRequest:
    city: str
    horizon: ForecastHorizon
    as_of_date: date  # the most recent date of real data the forecast is conditioned on


@dataclass(frozen=True)
class ForecastResult:
    """
    Mirrors domain/entities/forecast_result.py — this is the ML layer's
    output shape, which the use case maps into the domain entity. Kept
    deliberately plain (no keras/numpy types) so nothing downstream needs
    to import TensorFlow.
    """
    city: str
    horizon: ForecastHorizon
    predicted_mw: float
    as_of_date: date
    target_date: date
    model_version: str
    # Point forecast only (see feature_engineering.py docstring — this
    # project does not claim calibrated uncertainty intervals). Exposed as
    # None rather than a fabricated number so the API/dashboard can render
    # "not available" honestly instead of a fake confidence band.
    confidence_interval_mw: tuple[float, float] | None = None


class Forecaster(ABC):
    """Implemented by lstm_model.py's wrapper (see trainer.py /
    model_registry.py). Anything satisfying this contract — a different
    architecture, a stub for tests, a classical baseline — is a valid
    drop-in Forecaster."""

    @abstractmethod
    def predict(self, request: ForecastRequest) -> ForecastResult:
        """Raises ForecastUnavailableError (domain/exceptions.py) if no
        trained model exists for the requested city, or ValueError if
        `as_of_date` doesn't have enough trailing history (lookback days)
        available to build a feature window."""
        raise NotImplementedError

    @abstractmethod
    def model_version(self, city: str) -> str:
        """Returns the version identifier of the model currently loaded
        for `city` (see model_registry.py) — surfaced in API responses and
        reports so a prediction is always traceable to the exact model
        that produced it."""
        raise NotImplementedError