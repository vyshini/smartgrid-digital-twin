"""
Application-layer exceptions for forecasting. Kept here rather than
assumed to already exist in domain/exceptions.py, since this project's
domain layer was built in an earlier session I don't have visibility
into. If domain/exceptions.py already defines equivalent exceptions,
prefer consolidating there — the important thing is that core/exceptions.py's
domain-exception -> HTTP mapping handles whatever ends up being raised.

Suggested mapping to add in core/exceptions.py:
    ForecastUnavailableError          -> 404 Not Found
    InsufficientForecastHistoryError  -> 422 Unprocessable Entity
    UnknownCityError                  -> 404 Not Found
"""
from __future__ import annotations


class ForecastUnavailableError(Exception):
    """No trained/promoted model exists for the requested city yet."""


class InsufficientForecastHistoryError(Exception):
    """Not enough contiguous real data ending at as_of_date to build the
    model's required lookback window."""


class UnknownCityError(Exception):
    """Requested city isn't one this system models."""