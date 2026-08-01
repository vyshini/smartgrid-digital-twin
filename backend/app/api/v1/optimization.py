"""
Optimization API router, per Phase 1's docs/api-design.md.

POST /run uses an async job pattern (202 + job_id, poll for status) since a
real QAOA run takes real wall-clock time. The background job function below
is intentionally thin: it opens/closes three short-lived DB sessions around
RunGridOptimizationUseCase's three phase methods, and owns only the
job-store bookkeeping (an infrastructure/API-layer concern) — all the
actual domain logic (demand resolution, capacity lookup, persistence)
lives in the use case now, not here. See run_grid_optimization_use_case.py
for why it's split into phases rather than one atomic execute().
"""
import asyncio
import time
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends

from app.api.deps import get_session
from app.api.deps_forecast import get_forecaster
from app.application.optimization.run_grid_optimization_use_case import (
    ForecastRequiredButUnavailableError,
    RunGridOptimizationUseCase,
)
from app.core.rbac import require_any_authenticated_role, require_grid_operator_or_above
from app.domain.exceptions import (
    CityNotFoundError,
    CityNotSupportedForOptimizationError,
    OptimizationJobNotFoundError,
    OptimizationRunNotFoundError,
)
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.jobs.job_store import job_store
from app.infrastructure.repositories.city_repository import CityRepository
from app.infrastructure.repositories.forecast_repository import ForecastRepository
from app.infrastructure.repositories.optimization_repository import OptimizationRepository
from app.quantum.qaoa_grid_optimizer import QAOAGridOptimizer
from pathlib import Path

from fastapi.responses import FileResponse

from app.quantum.circuit_visualizer import circuit_summary, save_circuit_diagram
from app.quantum.generation_capacity import CITY_GENERATION_CAPACITY
from app.quantum.hamiltonian_builder import DispatchProblem
from app.quantum.population_data import apportioned_city_capacity
from app.schemas.optimization_schemas import (
    OptimizationExplanation,
    OptimizationJobAccepted,
    OptimizationJobStatus,
    OptimizationResultOut,
    OptimizationRunRequest,
)

router = APIRouter(prefix="/optimization", tags=["optimization"])
CIRCUIT_OUTPUT_DIR = Path(__file__).parent.parent.parent / "quantum" / "circuit_output"

def _build_reference_problem(city_name: str) -> DispatchProblem:
    """
    The circuit's STRUCTURE (n_qubits, gate layout) depends only on
    DispatchProblem's constants (N_BLOCKS, N_BATTERY_BITS, N_IMPORT_BITS),
    not on target_demand_mw — see circuit_visualizer.py's module docstring.
    This builds a nominal reference problem purely to get a valid
    DispatchProblem object; the demand value itself is never used for
    anything the diagram or summary actually shows.
    """
    if city_name not in CITY_GENERATION_CAPACITY:
        raise CityNotSupportedForOptimizationError(
            f"No real generation capacity data for '{city_name}' — "
            f"circuit visualization currently supports only the 8 originally seeded cities."
        )
    capacity = apportioned_city_capacity(city_name)
    return DispatchProblem(capacity=capacity, target_demand_mw=1.0, battery_power_rating_mw=100.0)

async def _run_optimization_job(
    job_id: str,
    city_id: int,
    target_demand_mw: float | None,
    forecast_as_of_date: date | None,
    battery_power_rating_mw: float,
) -> None:
    start = time.time()
    try:
        # --- PHASE 1: resolve demand + build problem (short DB session) ---
        async with AsyncSessionLocal() as session:
            use_case = RunGridOptimizationUseCase(
                city_repository=CityRepository(session),
                optimization_repository=OptimizationRepository(session),
                optimizer=QAOAGridOptimizer(),
                forecaster=get_forecaster(),
                forecast_repository=ForecastRepository(session),
            )
            problem, forecast_id = await use_case.build_problem(  # NEW: unpack tuple
                city_id, target_demand_mw, forecast_as_of_date, battery_power_rating_mw
            )
            await session.commit()
        # <-- session #1 closes here.

        # --- PHASE 2: CPU-bound QAOA, no DB connection held ---
        raw_result = await asyncio.to_thread(use_case.optimize_sync, problem)

        # --- PHASE 3: persist (fresh short DB session) ---
        async with AsyncSessionLocal() as session:
            use_case = RunGridOptimizationUseCase(
                city_repository=CityRepository(session),
                optimization_repository=OptimizationRepository(session),
                optimizer=QAOAGridOptimizer(),
            )
            record = await use_case.persist_result(
                city_id, raw_result, int((time.time() - start) * 1000),forecast_id
            )
            await session.commit()
            job_store.mark_completed(job_id, OptimizationResultOut.model_validate(record))

    except (CityNotFoundError, CityNotSupportedForOptimizationError, ForecastRequiredButUnavailableError) as e:
        job_store.mark_failed(job_id, str(e))
    except Exception as e:  # noqa: BLE001 — background job, nothing left to raise to
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
        _run_optimization_job,
        job_id,
        city_id,
        payload.target_demand_mw,
        payload.forecast_as_of_date,
        payload.battery_power_rating_mw,
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
@router.get("/{city_id}/circuit-diagram")
async def get_circuit_diagram(
    city_id: int,
    reps: int = 1,
    session=Depends(get_session),
    _user=Depends(require_any_authenticated_role),
) -> FileResponse:
    repo = CityRepository(session)
    city = await repo.get_by_id(city_id)
    if city is None:
        raise CityNotFoundError(f"City with id {city_id} was not found")

    problem = _build_reference_problem(city.name)

    # Cached to a fixed path rather than a temp dir — the diagram is
    # demand-independent (see _build_reference_problem's docstring), so
    # it's safe and cheap to regenerate-and-overwrite rather than manage
    # temp-file lifetime across the async FileResponse boundary (which is
    # flaky on Windows specifically — the response streams the file AFTER
    # this function returns, so a temp dir's cleanup can race it).
    output_path = CIRCUIT_OUTPUT_DIR / f"{city.name.lower()}_qaoa_circuit_reps{reps}.png"
    save_circuit_diagram(problem, output_path, reps=reps, decompose_level=0)
    return FileResponse(output_path, media_type="image/png", filename=output_path.name)


@router.get("/{city_id}/circuit-summary")
async def get_circuit_summary(
    city_id: int,
    reps: int = 1,
    session=Depends(get_session),
    _user=Depends(require_any_authenticated_role),
) -> dict:
    repo = CityRepository(session)
    city = await repo.get_by_id(city_id)
    if city is None:
        raise CityNotFoundError(f"City with id {city_id} was not found")

    problem = _build_reference_problem(city.name)
    return circuit_summary(problem, reps=reps)