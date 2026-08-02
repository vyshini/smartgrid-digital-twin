export type UserRole = 'admin' | 'grid_operator' | 'engineer' | 'researcher';
export type Horizon = 'next_day' | 'next_week';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
}

export interface City {
  id: number;
  name: string;
  state: string;
  latitude: number;
  longitude: number;
  population: number;
  timezone: string;
}

export interface GridNode {
  id: number;
  city_id: number;
  node_code: string;
  transmission_capacity_mw: number;
  status: 'healthy' | 'degraded' | 'critical' | 'offline';
}

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

export interface ForecastResponse {
  city: string;
  horizon: Horizon;
  predicted_mw: number;
  as_of_date: string;
  target_date: string;
  model_version: string;
  confidence_interval_mw: [number, number] | null;
}

export interface LossCurvePoint {
  epoch: number;
  loss: number;
  val_loss: number;
  next_day_loss?: number;
  next_day_val_loss?: number;
  next_week_loss?: number;
  next_week_val_loss?: number;
}

export interface ActualVsPredictedPoint {
  date: string;
  actual_mw: number;
  predicted_mw: number;
}

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

export interface OptimizationJobAccepted {
  job_id: string;
  status: string;
}

export interface OptimizationJobStatus {
  job_id: string;
  status: 'running' | 'completed' | 'failed';
  result: OptimizationResult | null;
  error: string | null;
}

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

export interface WeatherReading {
  city?: string;
  date: string;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_kmph: number;
  solar_irradiance: number;
  precipitation_mm: number;
}

export interface Scenario {
  key: string;
  name: string;
  city: string;
  description: string;
}

export interface SimulationHistoryRecord {
  id: number;
  scenario_type: string;
  scenario_key: string;
  scenario_name: string;
  as_of_date: string | null;
  run_at: string;
  result: Record<string, unknown>;
}
