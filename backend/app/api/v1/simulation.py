"""
Simulation API router. Scoped for now to weather-driven scenarios (see
project scoping discussion: weather scenarios re-run the real trained
LSTM on perturbed inputs; generation/infrastructure scenarios are a
separate mechanism — QAOA capacity override, not LSTM re-forecast — and
get their own module as a follow-up).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_forecast import get_data_provider, get_forecaster
from app.application.forecasting.exceptions import (
    ForecastUnavailableError,
    InsufficientForecastHistoryError,
    UnknownCityError,
)
from app.application.forecasting.forecast_city_load_use_case import (
    ForecastCityLoadInput,
    ForecastCityLoadUseCase,
)
from app.core.rbac import require_any_authenticated_role
from app.ml.interfaces import ForecastHorizon
from app.simulation.scenarios import WEATHER_SCENARIOS
from app.simulation.weather_scenario_forecaster import forecast_under_scenario

from app.api.deps import get_session
from app.infrastructure.repositories.city_repository import CityRepository
from app.infrastructure.repositories.simulation_repository import SimulationRepository
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/weather-scenarios")
async def list_weather_scenarios(_user=Depends(require_any_authenticated_role)) -> list[dict]:
    return [
        {"key": s.key, "name": s.name, "city": s.city, "description": s.description}
        for s in WEATHER_SCENARIOS.values()
    ]

@router.get("/weather-scenarios/{scenario_key}/run")
async def run_weather_scenario(
    scenario_key: str,
    as_of_date: date,
    session: AsyncSession = Depends(get_session),  # NEW
    _user=Depends(require_any_authenticated_role),
) -> dict:
    scenario = WEATHER_SCENARIOS.get(scenario_key)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{scenario_key}'")

    try:
        baseline_use_case = ForecastCityLoadUseCase(forecaster=get_forecaster())
        baseline = baseline_use_case.execute(
            ForecastCityLoadInput(city=scenario.city, horizon=ForecastHorizon.NEXT_DAY, as_of_date=as_of_date)
        )
        scenario_result = forecast_under_scenario(
            base_feature_provider=get_data_provider(),
            city=scenario.city,
            perturbation=scenario.perturbation,
            as_of_date=as_of_date,
        )
    except UnknownCityError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForecastUnavailableError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InsufficientForecastHistoryError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    delta_mw = round(scenario_result.predicted_mw - baseline.predicted_mw, 2)
    result_dict = {
        "scenario": scenario.name,
        "city": scenario.city,
        "as_of_date": str(as_of_date),
        "baseline_predicted_mw": baseline.predicted_mw,
        "scenario_predicted_mw": scenario_result.predicted_mw,
        "delta_mw": delta_mw,
        "delta_pct": round(100 * delta_mw / baseline.predicted_mw, 2),
    }

    # NEW — persist
    city_repo = CityRepository(session)
    city_record = await city_repo.get_by_name(scenario.city)
    if city_record is not None:
        sim_repo = SimulationRepository(session)
        await sim_repo.create(
            city_id=city_record.id,
            scenario_type="weather",
            scenario_key=scenario.key,
            scenario_name=scenario.name,
            as_of_date=str(as_of_date),
            result=result_dict,
        )
        await session.commit()

    return result_dict


@router.get("/{city_id}/history")
async def get_simulation_history(
    city_id: int,
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_any_authenticated_role),
) -> list[dict]:
    repo = SimulationRepository(session)
    records = await repo.get_history_for_city(city_id)
    return [
        {
            "id": r.id,
            "scenario_type": r.scenario_type,
            "scenario_key": r.scenario_key,
            "scenario_name": r.scenario_name,
            "as_of_date": r.as_of_date,
            "run_at": r.run_at.isoformat(),
            "result": r.result,
        }
        for r in records
    ]