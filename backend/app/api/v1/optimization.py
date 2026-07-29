"""
Optimization API router, per Phase 1's docs/api-design.md.

POST /run uses an async job pattern (202 + job_id, poll for status) since a
real QAOA run takes real wall-clock time (COBYLA iterations, each a
simulator call) — not something to block an HTTP request on. See
app/infrastructure/jobs/job_store.py for the (deliberately simple,
in-process) job tracking this uses.
"""
import time

from fastapi import APIRouter, BackgroundTasks, Depends

from app.api.deps import get_session
from app.application.optimization.run_grid_optimization_use_case import RunGridOptimizationUseCase
from app.core.rbac import require_any_authenticated_role, require_grid_operator_or_above
from app.domain.exceptions import DomainError, OptimizationJobNotFoundError, OptimizationRunNotFoundError
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.jobs.job_store import job_store
from app.infrastructure.repositories.city_repository import CityRepository
from app.infrastructure.repositories.optimization_repository import OptimizationRepository
from app.quantum.qaoa_grid_optimizer import QAOAGridOptimizer
from app.schemas.optimization_schemas import (
    OptimizationExplanation,
    OptimizationJobAccepted,
    OptimizationJobStatus,
    OptimizationResultOut,
    OptimizationRunRequest,
)
import asyncio

router = APIRouter(prefix="/optimization", tags=["optimization"])


async def _run_optimization_job(
    job_id: str, city_id: int, target_demand_mw: float, battery_power_rating_mw: float
) -> None:
    """
    Runs in the background, AFTER the 202 response has already been sent —
    must open its own DB session rather than reuse the request's (which is
    closed by then). Any failure here is captured into the job store rather
    than raised, since there's no HTTP request left to raise it to.
    """
    start = time.time()
    try:
        # -------------------------------------------------------------
        # PHASE 1: READ DATA (Short DB Session)
        # -------------------------------------------------------------
        async with AsyncSessionLocal() as session:
            city_repo = CityRepository(session)
            city = await city_repo.get_by_id(city_id)
            if not city:
                raise DomainError(f"City {city_id} not found")
            # Create your DispatchProblem here based on the city data
            from app.quantum.hamiltonian_builder import DispatchProblem
            from app.quantum.population_data import apportioned_city_capacity
            capacity = apportioned_city_capacity(city.name)
            problem = DispatchProblem(
                capacity = capacity,
                target_demand_mw=target_demand_mw,
                battery_power_rating_mw=battery_power_rating_mw,
                # Add any other required parameters from your city record
            )
        # <-- DB Session #1 CLOSES HERE. PostgreSQL is safe from timeouts!

        # -------------------------------------------------------------
        # PHASE 2: RUN QAOA IN A THREAD (No DB Connection)
        # -------------------------------------------------------------
        optimizer = QAOAGridOptimizer()
        # asyncio.to_thread prevents the 10-minute math from freezing FastAPI
        raw_results = await asyncio.to_thread(optimizer.optimize, problem)

        # -------------------------------------------------------------
        # PHASE 3: SAVE RESULTS (Short DB Session)
        # -------------------------------------------------------------
        async with AsyncSessionLocal() as session:
            opt_repo = OptimizationRepository(session)

            qaoa_iterations = raw_results["qaoa"].get("cobyla_iterations", 1)

            # Save the record to the database
            record = await opt_repo.create(
               city_id=city_id,
                algorithm="QAOA-COBYLA", 
                iterations=qaoa_iterations,  # <-- THIS FIXES THE DB ERROR
                optimization_score=raw_results["optimization_score"],
                objective_gap=raw_results["objective_gap"],
                matched_classical_optimum=raw_results["qaoa_matches_classical_optimum"],
                allocation_result=raw_results["qaoa"]["decoded"],
                execution_time_ms=int((time.time() - start) * 1000)
            )
            
            await session.commit()
            
            job_store.mark_completed(job_id, OptimizationResultOut.model_validate(record))

    except Exception as e:
        # If it fails at ANY point, capture it in the job store
        print(f"Background job failed: {e}")
        job_store.mark_failed(job_id, str(e))
           


@router.post("/{city_id}/run", response_model=OptimizationJobAccepted, status_code=202)
async def run_optimization(
    city_id: int,
    payload: OptimizationRunRequest,
    background_tasks: BackgroundTasks,
    _user=Depends(require_grid_operator_or_above),
) -> OptimizationJobAccepted:
    job_id = job_store.create()
    background_tasks.add_task(
        _run_optimization_job, job_id, city_id, payload.target_demand_mw, payload.battery_power_rating_mw
    )
    return OptimizationJobAccepted(job_id=job_id, status="running")


@router.get("/jobs/{job_id}", response_model=OptimizationJobStatus)
async def get_job_status(
    job_id: str, _user=Depends(require_any_authenticated_role)
) -> OptimizationJobStatus:
    job = job_store.get(job_id)
    if job is None:
        raise OptimizationJobNotFoundError(f"No job found with id {job_id}")
    return OptimizationJobStatus(job_id=job.job_id, status=job.status, result=job.result, error=job.error)


@router.get("/{city_id}/latest", response_model=OptimizationResultOut)
async def get_latest_optimization(
    city_id: int,
    session=Depends(get_session),
    _user=Depends(require_any_authenticated_role),
) -> OptimizationResultOut:
    repo = OptimizationRepository(session)
    record = await repo.get_latest_for_city(city_id)
    if record is None:
        raise OptimizationRunNotFoundError(f"No optimization runs found for city {city_id}")
    return OptimizationResultOut.model_validate(record)


@router.get("/{city_id}/history", response_model=list[OptimizationResultOut])
async def get_optimization_history(
    city_id: int,
    session=Depends(get_session),
    _user=Depends(require_any_authenticated_role),
) -> list[OptimizationResultOut]:
    repo = OptimizationRepository(session)
    records = await repo.get_history_for_city(city_id)
    return [OptimizationResultOut.model_validate(r) for r in records]


@router.get("/runs/{run_id}/explanation", response_model=OptimizationExplanation)
async def get_optimization_explanation(
    run_id: int,
    session=Depends(get_session),
    _user=Depends(require_any_authenticated_role),
) -> OptimizationExplanation:
    """Decision-support endpoint, per Phase 1's spec: explains WHY QAOA
    selected this allocation, in plain terms — not just raw numbers."""
    repo = OptimizationRepository(session)
    record = await repo.get_by_id(run_id)
    if record is None:
        raise OptimizationRunNotFoundError(f"No optimization run found with id {run_id}")

    alloc = record.allocation_result
    renewable_mw = alloc.get("hydro_mw", 0) + alloc.get("wind_mw", 0) + alloc.get("solar_mw", 0)
    if alloc.get("battery_charge_mw", 0) > 0:
        battery_action = "charging"
    elif alloc.get("battery_discharge_mw", 0) > 0:
        battery_action = "discharging"
    else:
        battery_action = "idle"

    match_note = (
        "matches the mathematically optimal classical solution exactly"
        if record.matched_classical_optimum
        else f"is within an objective gap of {float(record.objective_gap):.2f} of the classical optimum"
    )
    summary = (
        f"For a target demand of {alloc.get('target_demand_mw', 0):.1f} MW, QAOA dispatched "
        f"{renewable_mw:.1f} MW from renewables (hydro/wind/solar) and "
        f"{alloc.get('coal_mw', 0):.1f} MW from coal, with the battery {battery_action}. "
        f"This allocation {match_note}."
    )

    return OptimizationExplanation(
        run_id=record.id,
        summary=summary,
        optimization_score=float(record.optimization_score),
        matched_classical_optimum=record.matched_classical_optimum,
        renewable_dispatched_mw=round(renewable_mw, 2),
        battery_action=battery_action,
    )