"""
Public surface of the ML plugin layer. `application/forecasting/
forecast_city_load_use_case.py` should import from here (or directly from
`interfaces`) — not reach into `lstm_model`, `trainer`, or
`model_registry` internals directly, so the use case stays decoupled from
the fact that the current implementation happens to be an LSTM.

TensorFlow-dependent helpers (evaluator) are lazy-loaded so importing
`app.ml.interfaces` or other lightweight submodules does not require a
working TensorFlow install — needed for auth/cities/optimization tests.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .interfaces import Forecaster, ForecastHorizon, ForecastRequest, ForecastResult
from .model_registry import ModelNotFoundError

if TYPE_CHECKING:
    from .evaluator import ActualVsPredictedPoint, LossCurvePoint

__all__ = [
    "Forecaster",
    "ForecastHorizon",
    "ForecastRequest",
    "ForecastResult",
    "ModelNotFoundError",
    "compute_metrics",
    "get_actual_vs_predicted",
    "get_loss_curve",
]


def __getattr__(name: str):
    if name in ("compute_metrics", "get_actual_vs_predicted", "get_loss_curve"):
        from . import evaluator

        return getattr(evaluator, name)
    if name in ("ActualVsPredictedPoint", "LossCurvePoint"):
        from .evaluator import ActualVsPredictedPoint, LossCurvePoint

        return ActualVsPredictedPoint if name == "ActualVsPredictedPoint" else LossCurvePoint
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")