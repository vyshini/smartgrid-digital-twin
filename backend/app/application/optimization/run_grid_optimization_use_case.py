"""
Use case: run a grid dispatch optimization for a city. Orchestrates:
city lookup -> real apportioned capacity -> DispatchProblem -> GridOptimizer
(QAOA) -> persist OptimizationHistory.

IMPORTANT SCOPE NOTE: `target_demand_mw` is accepted as an explicit
parameter here, not fetched from a real forecast automatically. Phase 3's
trained LSTM models exist as files in ml-training/, but the Forecaster
interface + ML layer that would load them INTO this backend (per Phase 1's
planned app/ml/) hasn't been built yet — that's real follow-up work, not
something to fake here. Once that layer exists, this use case's
`target_demand_mw` parameter becomes populated by calling a Forecaster
instead of being supplied by the caller.

CRITICAL: self._optimizer.optimize(problem) is CPU-bound synchronous code
(QAOA's COBYLA loop, each iteration running a real statevector simulation).
Calling it directly inside this async method would block Python's entire
event loop for the whole computation — meaning the server couldn't process
ANY other request, including a client polling GET /jobs/{job_id} for
status, until the optimization finished. This surfaced in practice as "the
job_id doesn't work" when tested through the real API for the first time:
polling requests weren't actually failing, they just couldn't get
processed until the blocked event loop freed up. Running it via
asyncio.to_thread offloads the CPU-bound work to a separate thread,
keeping the event loop free to handle other requests (like status polls)
while the optimization runs in the background.
"""
import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.exceptions import CityNotFoundError, CityNotSupportedForOptimizationError
from app.quantum.generation_capacity import CITY_GENERATION_CAPACITY
from app.quantum.hamiltonian_builder import DispatchProblem
from app.quantum.interfaces import GridOptimizer
from app.quantum.population_data import apportioned_city_capacity

if TYPE_CHECKING:
    # Only needed for type hints below — importing these at runtime would
    # pull in SQLAlchemy even for callers using duck-typed fakes/mocks
    # (e.g. in tests), which is both unnecessary coupling and made this use
    # case harder to unit-test than it needs to be.
    from app.infrastructure.repositories.city_repository import CityRepository
    from app.infrastructure.repositories.optimization_repository import OptimizationRepository


class RunGridOptimizationUseCase:
    def __init__(
        self,
        city_repository: "CityRepository",
        optimization_repository: "OptimizationRepository",
        optimizer: GridOptimizer,
    ):
        self._cities = city_repository
        self._optimizations = optimization_repository
        self._optimizer = optimizer

    async def execute(
        self,
        city_id: int,
        target_demand_mw: float,
        battery_power_rating_mw: float = 200.0,
    ) -> dict:
        city = await self._cities.get_by_id(city_id)
        if city is None:
            raise CityNotFoundError(f"City with id {city_id} was not found")
        if city.name not in CITY_GENERATION_CAPACITY:
            raise CityNotSupportedForOptimizationError(
                f"No real generation capacity data for '{city.name}' — "
                f"optimization currently supports only the 8 originally seeded cities."
            )

        capacity = apportioned_city_capacity(city.name)
        problem = DispatchProblem(
            capacity=capacity,
            target_demand_mw=target_demand_mw,
            battery_power_rating_mw=battery_power_rating_mw,
        )

        # Offload the CPU-bound QAOA computation to a thread — see module
        # docstring's CRITICAL note for why this matters.
        result = await asyncio.to_thread(self._optimizer.optimize, problem)

        record = await self._optimizations.create(
            city_id=city_id,
            algorithm="QAOA-COBYLA",
            run_at=datetime.utcnow(),
            iterations=result["qaoa"]["cobyla_iterations"],
            optimization_score=result["optimization_score"],
            quantum_circuit_depth=result["qaoa"]["reps"],
            execution_time_ms=0,  # populated by the API layer, which times the full call
            allocation_result=result["qaoa"]["decoded"],
            objective_gap=result["objective_gap"],
            matched_classical_optimum=result["qaoa_matches_classical_optimum"],
        )
        return {"record": record, "raw_result": result}