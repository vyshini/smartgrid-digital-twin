export interface City {
  id: number;
  name: string;
  state: string;
  region: string;
  lat: number;
  lng: number;
  population: number;
  baseDemandMw: number;
  peakDemandMw: number;
  gridHealthScore: number;
}

export interface GridNode {
  id: number;
  city_id: number;
  name: string;
  node_type: 'thermal' | 'hydro' | 'wind' | 'solar' | 'battery' | 'substation' | 'industrial' | 'residential';
  capacity_mw: number;
  current_output_mw: number;
  status: 'online' | 'degraded' | 'maintenance' | 'offline';
  latitude: number;
  longitude: number;
}

export interface TransmissionLine {
  id: number;
  from_node_id: number;
  to_node_id: number;
  capacity_mw: number;
  current_load_mw: number;
  length_km: number;
  loss_pct: number;
  status: 'normal' | 'congested' | 'maintenance';
  utilization_pct: number;
}

export interface NationalOverview {
  total_cities: number;
  cities_with_data: number;
  national_forecast_demand_mw: number;
  avg_optimization_score: number;
  avg_grid_stability_score: number;
  avg_cost_reduction_pct: number;
  avg_power_loss_reduction_pct: number;
  avg_co2_reduction_pct: number;
  avg_renewable_pct: number;
  system_alerts: string[];
  cities: {
    city_id: number;
    city_name: string;
    latest_forecast_mw: number;
    latest_optimization_score: number;
    grid_stability_score: number;
    cost_reduction_pct: number;
    power_loss_reduction_pct: number;
    co2_reduction_pct: number;
    renewable_pct: number;
    has_optimization_data: boolean;
    has_forecast_data: boolean;
  }[];
}

export interface ForecastResponse {
  city: string;
  horizon: 'next_day' | 'next_week';
  predicted_mw: number;
  as_of_date: string;
  target_date: string;
  model_version: string;
  confidence_interval_mw: [number, number];
}

export interface LossCurvePoint {
  epoch: number;
  loss: number;
  val_loss: number;
  next_day_loss: number;
  next_day_val_loss: number;
  next_week_loss: number;
  next_week_val_loss: number;
}

export interface ActualVsPredictedPoint {
  date: string;
  actual_mw: number;
  predicted_mw: number;
}

export interface OptimizationResult {
  id: number;
  city_id: number;
  city_name: string;
  run_at: string;
  target_demand_mw: number;
  optimization_score: number;
  grid_stability_score: number;
  cost_reduction_pct: number;
  power_loss_reduction_pct: number;
  co2_reduction_pct: number;
  renewable_pct: number;
  matched_classical_optimum: boolean;
  objective_gap: number;
  allocation_result: {
    coal_mw: number;
    hydro_mw: number;
    wind_mw: number;
    solar_mw: number;
    battery_charge_mw: number;
    battery_discharge_mw: number;
    total_supply_mw: number;
    mismatch_mw: number;
    battery_conflict: boolean;
  };
  qubit_count: number;
  reps: number;
  circuit_summary: {
    num_qubits: number;
    depth: number;
    non_local_gates: number;
    total_gates: number;
    gate_counts: Record<string, number>;
  };
}

export interface Scenario {
  key: string;
  name: string;
  city: string;
  description: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}
