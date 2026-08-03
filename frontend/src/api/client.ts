import {
  City,
  NationalOverview,
  ForecastResponse,
  LossCurvePoint,
  ActualVsPredictedPoint,
  OptimizationResult,
  Scenario,
  GridNode,
  TransmissionLine,
  User
} from '../types/index.js';

const API_BASE = '/api/v1';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('smartgrid_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API Error [${res.status}]: ${errorText}`);
  }

  return res.json();
}

export const api = {
  // Auth
 login: async (username?: string, password?: string) => {
  const data = await request<{ access_token: string; refresh_token: string; user: User }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
  localStorage.setItem('smartgrid_token', data.access_token);
  localStorage.setItem('smartgrid_refresh_token', data.refresh_token);
  return data;
},
  getMe: () => request<User>('/auth/me'),

  // Dashboard
  getNationalOverview: () => request<NationalOverview>('/dashboard/overview'),

  // Cities
  getCities: () => request<City[]>('/cities'),
  getCityDetail: (cityId: number) => request<{ city: City; grid_nodes: GridNode[]; transmission_lines: TransmissionLine[] }>(`/cities/${cityId}`),
  getCityNodes: (cityId: number) => request<GridNode[]>(`/cities/${cityId}/nodes`),

  // Forecasting
  getForecast: (city: string, horizon: 'next_day' | 'next_week') =>
    request<ForecastResponse>(`/forecast/${city}/${horizon}`),
  getLossCurve: (city: string) => request<LossCurvePoint[]>(`/forecast/${city}/loss-curve`),
  getActualVsPredicted: (city: string, horizon: string = 'next_day') =>
    request<ActualVsPredictedPoint[]>(`/forecast/${city}/actual-vs-predicted?horizon=${horizon}`),

  // QAOA Optimization
  runQAOA: async (cityId: number, targetDemandMw?: number) => {
    const accepted = await request<{ job_id: string; status: string }>(`/optimization/${cityId}/run`, {
      method: 'POST',
      body: JSON.stringify({ target_demand_mw: targetDemandMw, battery_power_rating_mw: 100 })
    });

    // Poll job status
    let attempts = 0;
    while (attempts < 20) {
      await new Promise(r => setTimeout(r, 300));
      const job = await request<{ job_id: string; status: string; result?: OptimizationResult }>(`/optimization/jobs/${accepted.job_id}`);
      if (job.status === 'completed' && job.result) {
        return job.result;
      }
      attempts++;
    }
    throw new Error('QAOA Optimization job timed out');
  },
  getLatestOptimization: (cityId: number) => request<OptimizationResult>(`/optimization/${cityId}/latest`),
  getOptimizationHistory: (cityId: number) => request<OptimizationResult[]>(`/optimization/${cityId}/history`),
  getOptimizationExplanation: (runId: number) => request<{ summary: string; risk_level: string; expected_savings: string }>(`/optimization/runs/${runId}/explanation`),
  getCircuitSummary: (cityId: number) => request<any>(`/optimization/${cityId}/circuit-summary`),

  // Scenarios & Simulations
  getWeatherScenarios: () => request<Scenario[]>('/simulation/weather-scenarios'),
  runWeatherScenario: (scenarioKey: string, asOfDate: string = '2026-08-01') =>
    request<any>(`/simulation/weather-scenarios/${scenarioKey}/run?as_of_date=${asOfDate}`),
  getGenerationScenarios: (cityId: number) => request<Scenario[]>(`/optimization/${cityId}/generation-scenarios`),
  runGenerationScenario: (cityId: number, scenarioKey: string) =>
    request<any>(`/optimization/${cityId}/generation-scenarios/${scenarioKey}/run`, { method: 'POST' }),

  // Weather Telemetry
  getCurrentWeather: (city: string) => request<any>(`/weather/${city}/current`),
  getWeatherHistory: (city: string, days: number = 14) => request<any[]>(`/weather/${city}/history?days=${days}`)
};
