"""
Request/response DTOs for /api/v1/forecast. Kept separate from
app.ml.interfaces.ForecastResult (a plain dataclass) deliberately: the ML
layer's types must not depend on Pydantic/FastAPI, and the API's response
shape is allowed to diverge from the internal one over time (e.g. adding
API-only fields like a warning message) without touching app.ml at all.
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ForecastHorizonSchema(str, Enum):
    NEXT_DAY = "next_day"
    NEXT_WEEK = "next_week"


class ForecastResponseSchema(BaseModel):
    city: str
    horizon: ForecastHorizonSchema
    predicted_mw: float = Field(..., description="Point forecast in megawatts.")
    as_of_date: date = Field(..., description="Most recent real data date the forecast is conditioned on.")
    target_date: date = Field(..., description="The date being predicted.")
    model_version: str = Field(..., description="Registry version of the model that produced this forecast.")
    confidence_interval_mw: tuple[float, float] | None = Field(
        None,
        description="Not currently available — this project reports point forecasts only, no calibrated uncertainty interval.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "city": "Delhi",
                "horizon": "next_day",
                "predicted_mw": 4231.7,
                "as_of_date": "2026-07-17",
                "target_date": "2026-07-18",
                "model_version": "20260718-064343",
                "confidence_interval_mw": None,
            }
        }


class ForecastErrorSchema(BaseModel):
    detail: str


class LossCurvePointSchema(BaseModel):
    epoch: int
    loss: float
    val_loss: float
    next_day_loss: float | None = None
    next_day_val_loss: float | None = None
    next_week_loss: float | None = None
    next_week_val_loss: float | None = None


class ActualVsPredictedPointSchema(BaseModel):
    date: date
    actual_mw: float
    predicted_mw: float