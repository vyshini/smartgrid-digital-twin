from datetime import datetime

from pydantic import BaseModel, Field


class OptimizationRunRequest(BaseModel):
    target_demand_mw: float = Field(
        gt=0,
        description=(
            "Target demand to dispatch against. TEMPORARY: until a real "
            "Forecaster/ML layer is wired into this backend (Phase 3's "
            "trained models currently only exist as files in ml-training/), "
            "this must be supplied by the caller rather than fetched automatically."
        ),
    )
    battery_power_rating_mw: float = Field(default=200.0, gt=0)


class OptimizationJobAccepted(BaseModel):
    job_id: str
    status: str = "running"


class DispatchAllocation(BaseModel):
    coal_mw: float
    hydro_mw: float
    wind_mw: float
    solar_mw: float
    battery_charge_mw: float
    battery_discharge_mw: float
    total_supply_mw: float
    target_demand_mw: float
    mismatch_mw: float
    battery_conflict: bool


class OptimizationResultOut(BaseModel):
    id: int
    city_id: int
    algorithm: str
    run_at: datetime
    iterations: int
    optimization_score: float
    quantum_circuit_depth: int | None
    execution_time_ms: int
    objective_gap: float
    matched_classical_optimum: bool
    allocation_result: DispatchAllocation

    model_config = {"from_attributes": True}


class OptimizationJobStatus(BaseModel):
    job_id: str
    status: str  # "running" | "completed" | "failed"
    result: OptimizationResultOut | None = None
    error: str | None = None


class OptimizationExplanation(BaseModel):
    run_id: int
    summary: str
    optimization_score: float
    matched_classical_optimum: bool
    renewable_dispatched_mw: float
    battery_action: str