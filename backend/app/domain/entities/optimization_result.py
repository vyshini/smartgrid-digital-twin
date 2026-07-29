"""
OptimizationResult domain entity — framework-free, mirrors the pattern set
by City/GridNode/Battery in Phase 2. Represents one QAOA dispatch run's
result for a city, matching optimization_history's schema from Phase 1's
docs/database-schema.sql.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class OptimizationResult:
    id: int | None
    city_id: int
    algorithm: str
    target_demand_mw: float
    dispatch_mw: dict  # {"coal_mw": ..., "hydro_mw": ..., "wind_mw": ..., "solar_mw": ...,
    #                     "battery_charge_mw": ..., "battery_discharge_mw": ..., "mismatch_mw": ...}
    optimization_score: float
    objective_gap: float
    matched_classical_optimum: bool
    n_qubits: int
    execution_time_ms: int
    run_at: datetime | None = None

    def __post_init__(self):
        if not 0.0 <= self.optimization_score <= 100.0:
            raise ValueError(f"optimization_score must be within [0, 100], got {self.optimization_score}")
        if self.target_demand_mw < 0:
            raise ValueError("target_demand_mw cannot be negative")