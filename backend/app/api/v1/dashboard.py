"""
Dashboard aggregation endpoint — per spec's National Overview module.
Deliberately read-only and cheap: aggregates the LATEST already-persisted
OptimizationHistory + ForecastHistory row per city, no new optimization or
forecast runs triggered here. A city with no runs yet is reported
honestly (has_optimization_data/has_forecast_data: false) rather than
silently defaulted to zero, which would misrepresent "no data" as "zero
demand."
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.rbac import require_any_authenticated_role
from app.infrastructure.repositories.city_repository import CityRepository
from app.infrastructure.repositories.forecast_repository import ForecastRepository
from app.infrastructure.repositories.optimization_repository import OptimizationRepository
from app.quantum.hamiltonian_builder import SOURCES
from app.quantum.grid_metrics import compute_co2_reduction_pct
from app.schemas.dashboard_schemas import CityOverview, NationalOverview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _renewable_pct(decoded: dict) -> float:
    renewable = decoded.get("hydro_mw", 0) + decoded.get("wind_mw", 0) + decoded.get("solar_mw", 0)
    total = decoded.get("total_supply_mw", 0)
    if total <= 0:
        return 0.0
    return round(100 * renewable / total, 2)


def _build_alerts(city_name: str, opt_record, forecast_record) -> list[str]:
    alerts = []
    if opt_record is None:
        alerts.append(f"{city_name}: no optimization run yet")
        return alerts

    alloc = opt_record.allocation_result
    target = alloc.get("target_demand_mw", 0)
    mismatch = abs(alloc.get("mismatch_mw", 0))
    if target > 0 and (100 * mismatch / target) > 10:
        alerts.append(f"{city_name}: high supply-demand mismatch ({mismatch:.0f} MW unmet)")
    if alloc.get("battery_conflict"):
        alerts.append(f"{city_name}: battery charge/discharge conflict detected")
    if opt_record.grid_stability_score is not None and float(opt_record.grid_stability_score) < 70:
        alerts.append(f"{city_name}: low grid stability score ({float(opt_record.grid_stability_score):.1f})")
    if forecast_record is None:
        alerts.append(f"{city_name}: no forecast on record")
    return alerts


@router.get("/overview", response_model=NationalOverview)
async def get_national_overview(
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_any_authenticated_role),
) -> NationalOverview:
    city_repo = CityRepository(session)
    opt_repo = OptimizationRepository(session)
    forecast_repo = ForecastRepository(session)

    cities = await city_repo.list_all()
    city_overviews: list[CityOverview] = []
    all_alerts: list[str] = []

    forecast_sum, opt_score_sum, stability_sum = 0.0, 0.0, 0.0
    cost_sum, loss_sum, co2_sum, renewable_sum = 0.0, 0.0, 0.0, 0.0
    cities_with_opt = 0
    stability_count, cost_count, loss_count = 0, 0, 0

    for city in cities:
        opt_record = await opt_repo.get_latest_for_city(city.id)
        forecast_record = await forecast_repo.get_latest_for_city(city.id)

        latest_forecast_mw = float(forecast_record.predicted_mw) if forecast_record else None
        if latest_forecast_mw is not None:
            forecast_sum += latest_forecast_mw

        optimization_score = None
        stability = None
        cost_pct = None
        loss_pct = None
        co2_pct = None
        renewable_pct = None

        if opt_record is not None:
            alloc = opt_record.allocation_result
            optimization_score = float(opt_record.optimization_score)
            stability = float(opt_record.grid_stability_score) if opt_record.grid_stability_score is not None else None
            cost_pct = float(opt_record.cost_reduction_pct) if opt_record.cost_reduction_pct is not None else None
            loss_pct = float(opt_record.power_loss_reduction_pct) if opt_record.power_loss_reduction_pct is not None else None
            co2_pct = compute_co2_reduction_pct(alloc)
            renewable_pct = _renewable_pct(alloc)

            opt_score_sum += optimization_score
            if stability is not None:
                stability_sum += stability
                stability_count += 1
            if cost_pct is not None:
                cost_sum += cost_pct
                cost_count += 1
            if loss_pct is not None:
                loss_sum += loss_pct
                loss_count += 1
            co2_sum += co2_pct
            renewable_sum += renewable_pct
            cities_with_opt += 1

        city_overviews.append(CityOverview(
            city_id=city.id,
            city_name=city.name,
            latest_forecast_mw=latest_forecast_mw,
            latest_optimization_score=optimization_score,
            grid_stability_score=stability,
            cost_reduction_pct=cost_pct,
            power_loss_reduction_pct=loss_pct,
            co2_reduction_pct=co2_pct,
            renewable_pct=renewable_pct,
            has_optimization_data=opt_record is not None,
            has_forecast_data=forecast_record is not None,
        ))
        all_alerts.extend(_build_alerts(city.name, opt_record, forecast_record))

    def _avg(total: float, count: int) -> float | None:
        return round(total / count, 2) if count > 0 else None

    return NationalOverview(
        total_cities=len(cities),
        cities_with_data=cities_with_opt,
        national_forecast_demand_mw=round(forecast_sum, 2) if forecast_sum > 0 else None,
        avg_optimization_score=_avg(opt_score_sum, cities_with_opt),
        avg_grid_stability_score=_avg(stability_sum, stability_count),
        avg_cost_reduction_pct=_avg(cost_sum, cost_count),
        avg_power_loss_reduction_pct=_avg(loss_sum, loss_count),
        avg_co2_reduction_pct=_avg(co2_sum, cities_with_opt),
        avg_renewable_pct=_avg(renewable_sum, cities_with_opt),
        system_alerts=all_alerts,
        cities=city_overviews,
    )
  