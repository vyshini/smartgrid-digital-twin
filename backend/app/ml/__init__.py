"""
Public surface of the ML plugin layer. `application/forecasting/
forecast_city_load_use_case.py` should import from here (or directly from
`interfaces`) — not reach into `lstm_model`, `trainer`, or
`model_registry` internals directly, so the use case stays decoupled from
the fact that the current implementation happens to be an LSTM.
"""
from .evaluator import compute_metrics, get_actual_vs_predicted, get_loss_curve
from .interfaces import Forecaster, ForecastHorizon, ForecastRequest, ForecastResult
from .model_registry import ModelNotFoundError

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