from pydantic import BaseModel


class CityOverview(BaseModel):
    city_id: int
    city_name: str
    latest_forecast_mw: float | None
    latest_optimization_score: float | None
    grid_stability_score: float | None
    cost_reduction_pct: float | None
    power_loss_reduction_pct: float | None
    co2_reduction_pct: float | None
    renewable_pct: float | None
    has_optimization_data: bool
    has_forecast_data: bool


class NationalOverview(BaseModel):
    total_cities: int
    cities_with_data: int
    national_forecast_demand_mw: float | None
    avg_optimization_score: float | None
    avg_grid_stability_score: float | None
    avg_cost_reduction_pct: float | None
    avg_power_loss_reduction_pct: float | None
    avg_co2_reduction_pct: float | None
    avg_renewable_pct: float | None
    system_alerts: list[str]
    cities: list[CityOverview]