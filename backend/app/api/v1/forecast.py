"""
Thin presentation layer per the Clean Architecture requirement — routers
here do argument parsing, call a use case (or, for the two read-only
analytics endpoints below, evaluator.py directly, since there's no
meaningful "business logic" between a stored CSV and a JSON response),
and map results/exceptions to HTTP. No prediction logic lives in this
file.

Mount in main.py:
    from app.api.v1 import forecast as forecast_router
    app.include_router(forecast_router.router, prefix="/api/v1/forecast", tags=["forecast"])
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps_forecast import get_forecast_use_case
from app.application.forecasting.exceptions import (
    ForecastUnavailableError,
    InsufficientForecastHistoryError,
    UnknownCityError,
)
from app.application.forecasting.forecast_city_load_use_case import (
    ForecastCityLoadInput,
    ForecastCityLoadUseCase,
)
from app.ml import evaluator
from app.ml.interfaces import ForecastHorizon
from app.ml import feature_engineering as fe
from app.ml.model_registry import ModelNotFoundError
from app.schemas.forecast_schemas import (
    ActualVsPredictedPointSchema,
    ForecastHorizonSchema,
    ForecastResponseSchema,
    LossCurvePointSchema,
)
from app.api.deps import get_session
from app.infrastructure.repositories.forecast_repository import ForecastRepository
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from app.core.config import get_settings

router = APIRouter()

@router.get("/{city}/latest-available-date")
def get_latest_available_date(city: str) -> dict:
    """Reports the most recent real date this city's data supports a full
    lookback window for — the frontend uses this to default its date
    pickers, instead of the API silently 422ing against 'today' when the
    static dataset ends well in the past."""
    from app.api.deps_forecast import get_data_provider

    provider = get_data_provider()
    df = provider(city)
    latest = df.dropna(subset=fe.DEFAULT_FEATURE_COLUMNS).index.max()
    return {"city": city, "latest_available_date": str(latest.date())}


@router.get("/{city}/{horizon}", response_model=ForecastResponseSchema, summary="Predict a city's load for the given horizon.")
async def predict_city_load(
    city: str,
    horizon: ForecastHorizonSchema,
    as_of_date: date | None = Query(None, description="..."),
    use_case: ForecastCityLoadUseCase = Depends(get_forecast_use_case),
    session: AsyncSession = Depends(get_session),  # NEW
) -> ForecastResponseSchema:
    try:
        result = use_case.execute(
            ForecastCityLoadInput(city=city, horizon=ForecastHorizon(horizon.value), as_of_date=as_of_date)
        )
    except UnknownCityError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForecastUnavailableError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InsufficientForecastHistoryError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # NEW — persist so the dashboard reflects plain forecast calls too,
    # not only forecasts made as a side-effect of an optimization run.
    from app.infrastructure.repositories.city_repository import CityRepository
    city_repo = CityRepository(session)
    city_record = await city_repo.get_by_name(result.city)
    if city_record is not None:
        forecast_repo = ForecastRepository(session)
        await forecast_repo.create(
            city_id=city_record.id,
            horizon=result.horizon.value,
            as_of_date=result.as_of_date,
            target_date=result.target_date,
            predicted_mw=result.predicted_mw,
            model_version=result.model_version,
        )
        await session.commit()

    return ForecastResponseSchema(
        city=result.city,
        horizon=ForecastHorizonSchema(result.horizon.value),
        predicted_mw=result.predicted_mw,
        as_of_date=result.as_of_date,
        target_date=result.target_date,
        model_version=result.model_version,
        confidence_interval_mw=result.confidence_interval_mw,
    )


@router.get(
    "/{city}/loss-curve",
    response_model=list[LossCurvePointSchema],
    summary="Training loss/val_loss per epoch for the currently-live model (Analytics module).",
)
def get_loss_curve(city: str) -> list[LossCurvePointSchema]:
    try:
        points = evaluator.get_loss_curve(city)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return [
        LossCurvePointSchema(
            epoch=p.epoch, loss=p.loss, val_loss=p.val_loss,
            next_day_loss=p.next_day_loss, next_day_val_loss=p.next_day_val_loss,
            next_week_loss=p.next_week_loss, next_week_val_loss=p.next_week_val_loss,
        )
        for p in points
    ]


@router.get(
    "/{city}/actual-vs-predicted",
    response_model=list[ActualVsPredictedPointSchema],
    summary="Actual vs. predicted demand over the held-out test period, for the currently-live model (Analytics module).",
)
def get_actual_vs_predicted(
    city: str,
    horizon: ForecastHorizonSchema = ForecastHorizonSchema.NEXT_DAY,
) -> list[ActualVsPredictedPointSchema]:
    data_dir = Path(get_settings().ML_DATA_DIR)
    try:
        points = evaluator.get_actual_vs_predicted(
            city, data_dir, ForecastHorizon(horizon.value)
        )
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return [
        ActualVsPredictedPointSchema(date=p.date, actual_mw=p.actual_mw, predicted_mw=p.predicted_mw)
        for p in points
    ]