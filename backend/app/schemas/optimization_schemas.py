from datetime import date, datetime

from pydantic import BaseModel, Field


class OptimizationRunRequest(BaseModel):
    target_demand_mw: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Target demand to dispatch against. If omitted, this is fetched "
            "automatically from the next-day LSTM forecast for this city."
        ),
    )
    forecast_as_of_date: date | None = Field(
        default=None,
        description=(
            "Only used when target_demand_mw is omitted. Most recent real data "
            "date to condition the forecast on. The static dataset currently ends "
            "2024-09-29 — omitting this defaults to 'yesterday' (today's real "
            "date) and WILL fail until a live ingestion pipeline exists."
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
    import_mw: float 
    battery_charge_mw: float
    battery_discharge_mw: float
    total_supply_mw: float
    target_demand_mw: float
    mismatch_mw: float
    battery_conflict: bool


class OptimizationResultOut(BaseModel):
    id: int
    city_id: int
    forecast_id: int | None
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