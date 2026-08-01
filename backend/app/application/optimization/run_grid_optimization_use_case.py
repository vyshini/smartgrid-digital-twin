"""
Use case: run a grid dispatch optimization for a city.

Split into three phase methods (build_problem / optimize_sync / persist_result)
rather than one atomic execute(), because the API layer runs this as a
background job behind a 202+poll pattern (see api/v1/optimization.py) and
must NOT hold a single DB session open across the CPU-bound QAOA call.
Each phase method is given a short-lived session by its caller, used, and
returned; the CPU-bound phase (optimize_sync) touches no DB session at all.

Demand resolution: if target_demand_mw is supplied explicitly, that wins
outright — no forecast call is made, and forecast_id stays None (there's
nothing real to record). Otherwise, this use case pulls a real next-day
forecast via the injected Forecaster AND persists it to forecast_history,
so the returned forecast_id gives OptimizationHistory a real, followable
reference to exactly which forecast drove this optimization run.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import TYPE_CHECKING

from app.domain.exceptions import (
    CityNotFoundError,
    CityNotSupportedForOptimizationError,
    DomainError,
)
from app.ml.interfaces import Forecaster, ForecastHorizon, ForecastRequest
from app.ml.model_registry import ModelNotFoundError
from app.ml.preprocessing import InsufficientHistoryError
from app.quantum.generation_capacity import CITY_GENERATION_CAPACITY
from app.quantum.hamiltonian_builder import DispatchProblem
from app.quantum.interfaces import GridOptimizer
from app.quantum.population_data import apportioned_city_capacity

if TYPE_CHECKING:
    from app.infrastructure.db.models.optimization import OptimizationHistory
    from app.infrastructure.repositories.city_repository import CityRepository
    from app.infrastructure.repositories.forecast_repository import ForecastRepository
    from app.infrastructure.repositories.optimization_repository import OptimizationRepository

from app.quantum.grid_metrics import (
    compute_cost_reduction_pct,
    compute_grid_stability_score,
    compute_power_loss_reduction_pct,
)

class ForecastRequiredButUnavailableError(DomainError):
    """Raised when target_demand_mw is omitted but no Forecaster was
    injected, or the forecast itself fails (no model, insufficient
    history)."""

    code = "FORECAST_REQUIRED_BUT_UNAVAILABLE"


class RunGridOptimizationUseCase:
    def __init__(
        self,
        city_repository: "CityRepository",
        optimization_repository: "OptimizationRepository",
        optimizer: GridOptimizer,
        forecaster: Forecaster | None = None,
        forecast_repository: "ForecastRepository | None" = None,
    ):
        self._cities = city_repository
        self._optimizations = optimization_repository
        self._optimizer = optimizer
        self._forecaster = forecaster
        self._forecasts = forecast_repository

    # ------------------------------------------------------------------
    # Phase 1 — resolve demand (explicit or forecast) + build the problem.
    # Returns (problem, forecast_id). forecast_id is None whenever
    # target_demand_mw was supplied explicitly — no forecast, nothing to
    # reference.
    # ------------------------------------------------------------------
    async def build_problem(
        self,
        city_id: int,
        target_demand_mw: float | None,
        forecast_as_of_date: date | None,
        battery_power_rating_mw: float = 200.0,
    ) -> tuple[DispatchProblem, int | None]:
        city = await self._cities.get_by_id(city_id)
        if city is None:
            raise CityNotFoundError(f"City with id {city_id} was not found")
        if city.name not in CITY_GENERATION_CAPACITY:
            raise CityNotSupportedForOptimizationError(
                f"No real generation capacity data for '{city.name}' — "
                f"optimization currently supports only the 8 originally seeded cities."
            )

        resolved_demand, forecast_id = await self._resolve_target_demand(
            city_id, city.name, target_demand_mw, forecast_as_of_date
        )

        capacity = apportioned_city_capacity(city.name)
        problem = DispatchProblem(
            capacity=capacity,
            target_demand_mw=resolved_demand,
            battery_power_rating_mw=battery_power_rating_mw,
        )
        return problem, forecast_id

    async def _resolve_target_demand(
        self,
        city_id: int,
        city_name: str,
        target_demand_mw: float | None,
        forecast_as_of_date: date | None,
    ) -> tuple[float, int | None]:
        if target_demand_mw is not None:
            return target_demand_mw, None  # explicit override — no forecast to record

        if self._forecaster is None:
            raise ForecastRequiredButUnavailableError(
                "target_demand_mw was omitted but this use case was constructed "
                "without a Forecaster — supply target_demand_mw explicitly."
            )

        request = ForecastRequest(
            city=city_name,
            horizon=ForecastHorizon.NEXT_DAY,
            as_of_date=forecast_as_of_date or (date.today()),
        )
        try:
            result = await asyncio.to_thread(self._forecaster.predict, request)
        except ModelNotFoundError as e:
            raise ForecastRequiredButUnavailableError(
                f"No trained model available for '{city_name}'. {e}"
            ) from e
        except InsufficientHistoryError as e:
            raise ForecastRequiredButUnavailableError(
                f"{e} The static dataset currently ends 2024-09-29 — pass "
                f"forecast_as_of_date='2024-09-29' explicitly, or supply "
                f"target_demand_mw directly, until live ingestion exists."
            ) from e

        forecast_id = None
        if self._forecasts is not None:
            forecast_record = await self._forecasts.create(
                city_id=city_id,
                horizon=result.horizon.value,
                as_of_date=result.as_of_date,
                target_date=result.target_date,
                predicted_mw=result.predicted_mw,
                model_version=result.model_version,
            )
            forecast_id = forecast_record.id

        return result.predicted_mw, forecast_id

    # ------------------------------------------------------------------
    # Phase 2 — the CPU-bound call itself. Synchronous, DB-free.
    # ------------------------------------------------------------------
    def optimize_sync(self, problem: DispatchProblem) -> dict:
        return self._optimizer.optimize(problem)

    # ------------------------------------------------------------------
    # Phase 3 — persist. Now threads forecast_id through, when present.
    # ------------------------------------------------------------------
    async def persist_result(
        self,
        city_id: int,
        raw_result: dict,
        execution_time_ms: int,
        forecast_id: int | None = None,
    ) -> "OptimizationHistory":
        decoded = raw_result["qaoa"]["decoded"]

        record = await self._optimizations.create(
            city_id=city_id,
            forecast_id=forecast_id,
            algorithm="QAOA-COBYLA",
            run_at=datetime.utcnow(),
            iterations=raw_result["qaoa"]["cobyla_iterations"],
            optimization_score=raw_result["optimization_score"],
            quantum_circuit_depth=raw_result["qaoa"]["reps"],
            execution_time_ms=execution_time_ms,
            allocation_result=decoded,
            objective_gap=raw_result["objective_gap"],
            matched_classical_optimum=raw_result["qaoa_matches_classical_optimum"],
            cost_reduction_pct=compute_cost_reduction_pct(decoded),          # NEW
            power_loss_reduction_pct=compute_power_loss_reduction_pct(decoded),  # NEW
            grid_stability_score=compute_grid_stability_score(decoded),      # NEW
        )
        return record