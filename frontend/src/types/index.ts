// ---------------------------------------------------------------------------
// These types are written to match the REAL FastAPI backend's Pydantic
// schemas exactly (backend/app/schemas/*.py) — not an idealized/richer shape.
// Where the backend genuinely returns `null` for "no data yet" (rather than
// fabricating a placeholder), the type says so explicitly with `| null`, so
// components are forced to handle the honest "not available" case instead
// of silently rendering `undefined`.
// ---------------------------------------------------------------------------

// Matches backend/app/schemas/city_schemas.py::CityOut
export interface City {
  id: number;
  name: string;
  state: string;
  latitude: number;
  longitude: number;
  population: number;
  timezone: string;
}

// Matches backend/app/schemas/city_schemas.py::GridNodeOut
// NOTE: the real backend's grid nodes are generic substations — there is no
// generation "type" (thermal/hydro/wind/solar) and no live "current output"
// measurement. Only a static transmission capacity and a health status.
export interface GridNode {
  id: number;
  city_id: number;
  node_code: string;
  transmission_capacity_mw: number;
  status: 'healthy' | 'degraded' | 'critical' | 'offline';
}

// Matches backend/app/schemas/city_schemas.py::TransmissionLineOut
export interface TransmissionLine {
  id: number;
  from_node_id: number;
  to_node_id: number;
  capacity_mw: number;
  current_load_mw: number;
  length_km: number;
  loss_pct: number;
  status: 'active' | 'degraded' | 'failed' | 'maintenance';
  utilization_pct: number;
}

export interface CityDetail {
  city: City;
  grid_nodes: GridNode[];
  transmission_lines: TransmissionLine[];
}

// Matches backend/app/schemas/dashboard_schemas.py::CityOverview
// All metric fields are genuinely nullable on the backend — a city with no
// forecast/optimization run yet returns null, not a fabricated number.
export interface CityOverview {
  city_id: number;
  city_name: string;
  latest_forecast_mw: number | null;
  latest_optimization_score: number | null;
  grid_stability_score: number | null;
  cost_reduction_pct: number | null;
  power_loss_reduction_pct: number | null;
  co2_reduction_pct: number | null;
  renewable_pct: number | null;
  has_optimization_data: boolean;
  has_forecast_data: boolean;
}

// Matches backend/app/schemas/dashboard_schemas.py::NationalOverview
export interface NationalOverview {
  total_cities: number;
  cities_with_data: number;
  national_forecast_demand_mw: number | null;
  avg_optimization_score: number | null;
  avg_grid_stability_score: number | null;
  avg_cost_reduction_pct: number | null;
  avg_power_loss_reduction_pct: number | null;
  avg_co2_reduction_pct: number | null;
  avg_renewable_pct: number | null;
  system_alerts: string[];
  cities: CityOverview[];
}

// Matches backend/app/schemas/forecast_schemas.py::ForecastResponseSchema
// confidence_interval_mw is ALWAYS null on this backend by design — it
// reports point forecasts only, no calibrated uncertainty interval (see
// backend/app/ml/interfaces.py's ForecastResult docstring). Never render
// this as if it were a real tuple without checking for null first.
export interface ForecastResponse {
  city: string;
  horizon: 'next_day' | 'next_week';
  predicted_mw: number;
  as_of_date: string;
  target_date: string;
  model_version: string;
  confidence_interval_mw: [number, number] | null;
}

// Matches backend/app/schemas/forecast_schemas.py::LossCurvePointSchema
export interface LossCurvePoint {
  epoch: number;
  loss: number;
  val_loss: number;
  next_day_loss: number | null;
  next_day_val_loss: number | null;
  next_week_loss: number | null;
  next_week_val_loss: number | null;
}

// Matches backend/app/schemas/forecast_schemas.py::ActualVsPredictedPointSchema
export interface ActualVsPredictedPoint {
  date: string;
  actual_mw: number;
  predicted_mw: number;
}

// Matches backend/app/schemas/optimization_schemas.py::DispatchAllocation
export interface DispatchAllocation {
  coal_mw: number;
  hydro_mw: number;
  wind_mw: number;
  solar_mw: number;
  import_mw: number;
  battery_charge_mw: number;
  battery_discharge_mw: number;
  total_supply_mw: number;
  target_demand_mw: number;
  mismatch_mw: number;
  battery_conflict: boolean;
}

// Matches backend/app/schemas/optimization_schemas.py::OptimizationResultOut
// NOTE: there is no `renewable_pct` or `co2_reduction_pct` field on an
// individual optimization run in the real backend — those are only computed
// at the dashboard/report aggregation layer. If you need a renewable share
// for one specific run, derive it client-side from `allocation_result`.
export interface OptimizationResult {
  id: number;
  city_id: number;
  forecast_id: number | null;
  algorithm: string;
  run_at: string;
  iterations: number;
  optimization_score: number;
  cost_reduction_pct: number | null;
  power_loss_reduction_pct: number | null;
  grid_stability_score: number | null;
  quantum_circuit_depth: number | null;
  execution_time_ms: number;
  objective_gap: number;
  matched_classical_optimum: boolean;
  allocation_result: DispatchAllocation;
}

// Matches backend/app/schemas/optimization_schemas.py::OptimizationExplanation
export interface OptimizationExplanation {
  run_id: number;
  summary: string;
  optimization_score: number;
  matched_classical_optimum: boolean;
  renewable_dispatched_mw: number;
  battery_action: string;
  expected_savings: string;
  risk_level: 'low' | 'medium' | 'high';
}

// Matches backend/app/quantum/circuit_visualizer.py::circuit_summary()
// returned by GET /optimization/{city_id}/circuit-summary — genuinely
// per-city (a city with wind_mw=0 will show fewer effective qubits/gates).
export interface CircuitSummary {
  n_qubits: number;
  reps: number;
  circuit_depth: number;
  total_gates: number;
  gate_counts: Record<string, number>;
}

// Matches app/simulation/scenarios.py::WeatherScenario and
// app/simulation/generation_scenarios.py::GenerationScenario
export interface Scenario {
  key: string;
  name: string;
  city: string;
  description: string;
}

// Response shape of GET /simulation/weather-scenarios/{key}/run
export interface WeatherScenarioResult {
  scenario: string;
  city: string;
  as_of_date: string;
  baseline_predicted_mw: number;
  scenario_predicted_mw: number;
  delta_mw: number;
  delta_pct: number;
}

// Response shape of POST /optimization/{city_id}/generation-scenarios/{key}/run
export interface GenerationScenarioResult {
  scenario: string;
  target_demand_mw: number;
  forecast_id: number | null;
  baseline_allocation: DispatchAllocation;
  scenario_allocation: DispatchAllocation;
}

// Matches backend/app/api/v1/weather.py's response shapes
export interface WeatherReading {
  city?: string;
  date: string;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_kmph: number;
  solar_irradiance: number;
  precipitation_mm: number;
}

// Matches backend/app/schemas/auth_schemas.py::UserOut (id is a UUID string)
export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: 'admin' | 'grid_operator' | 'engineer' | 'researcher';
  is_active: boolean;
}
