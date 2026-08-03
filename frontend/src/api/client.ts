import {
  City,
  CityDetail,
  NationalOverview,
  ForecastResponse,
  LossCurvePoint,
  ActualVsPredictedPoint,
  OptimizationResult,
  OptimizationExplanation,
  CircuitSummary,
  Scenario,
  WeatherScenarioResult,
  GenerationScenarioResult,
  WeatherReading,
  User
} from '../types/index.js';

const API_BASE = '/api/v1';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

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
    throw new ApiError(res.status, `API Error [${res.status}]: ${errorText}`);
  }

  // 204 No Content has no body to parse.
  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return res.json();
}

/**
 * Fetches an auth-protected binary resource (e.g. the QAOA circuit diagram
 * PNG) and returns a blob object URL. A plain <img src="..."> can't attach
 * an Authorization header, so this fetches manually and hands back a URL
 * the browser can render. Caller is responsible for revoking the URL
 * (URL.revokeObjectURL) when it's no longer needed, to avoid leaking memory.
 */
async function requestBlobUrl(endpoint: string): Promise<string> {
  const token = localStorage.getItem('smartgrid_token');
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${endpoint}`, { headers });
  if (!res.ok) {
    throw new ApiError(res.status, `API Error [${res.status}] fetching ${endpoint}`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export const api = {
  // ---------------------------------------------------------------------
  // Auth — backend/app/api/v1/auth.py
  // ---------------------------------------------------------------------
  login: async (username: string, password: string) => {
    const data = await request<{ access_token: string; refresh_token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    localStorage.setItem('smartgrid_token', data.access_token);
    localStorage.setItem('smartgrid_refresh_token', data.refresh_token);
    return data;
  },
  logout: () => {
    localStorage.removeItem('smartgrid_token');
    localStorage.removeItem('smartgrid_refresh_token');
  },
  getMe: () => request<User>('/auth/me'),

  // ---------------------------------------------------------------------
  // Dashboard — backend/app/api/v1/dashboard.py
  // ---------------------------------------------------------------------
  getNationalOverview: () => request<NationalOverview>('/dashboard/overview'),

  // ---------------------------------------------------------------------
  // Cities — backend/app/api/v1/cities.py
  // ---------------------------------------------------------------------
  getCities: () => request<City[]>('/cities'),
  getCityDetail: (cityId: number) => request<CityDetail>(`/cities/${cityId}`),

  // ---------------------------------------------------------------------
  // Forecasting — backend/app/api/v1/forecast.py
  // ---------------------------------------------------------------------
  getLatestAvailableDate: (city: string) =>
    request<{ city: string; latest_available_date: string }>(`/forecast/${city}/latest-available-date`),
  getForecast: (city: string, horizon: 'next_day' | 'next_week', asOfDate?: string) =>
    request<ForecastResponse>(`/forecast/${city}/${horizon}${asOfDate ? `?as_of_date=${asOfDate}` : ''}`),
  getLossCurve: (city: string) => request<LossCurvePoint[]>(`/forecast/${city}/loss-curve`),
  getActualVsPredicted: (city: string, horizon: 'next_day' | 'next_week' = 'next_day') =>
    request<ActualVsPredictedPoint[]>(`/forecast/${city}/actual-vs-predicted?horizon=${horizon}`),

  // ---------------------------------------------------------------------
  // QAOA Optimization — backend/app/api/v1/optimization.py
  // POST /run is an async job (202 + job_id); this polls until completion,
  // matching the real backend's documented job-poll pattern.
  // ---------------------------------------------------------------------
  runQAOA: async (
    cityId: number,
    opts: { targetDemandMw?: number; forecastAsOfDate?: string; batteryPowerRatingMw?: number } = {}
  ) => {
    const accepted = await request<{ job_id: string; status: string }>(`/optimization/${cityId}/run`, {
      method: 'POST',
      body: JSON.stringify({
        target_demand_mw: opts.targetDemandMw,
        forecast_as_of_date: opts.forecastAsOfDate,
        battery_power_rating_mw: opts.batteryPowerRatingMw ?? 100
      })
    });

    let attempts = 0;
    const maxAttempts = 60; // ~60s at 1s intervals — real QAOA runs take real wall-clock time
    while (attempts < maxAttempts) {
      await new Promise(r => setTimeout(r, 1000));
      const job = await request<{ job_id: string; status: string; result?: OptimizationResult; error?: string }>(
        `/optimization/jobs/${accepted.job_id}`
      );
      if (job.status === 'completed' && job.result) {
        return job.result;
      }
      if (job.status === 'failed') {
        throw new Error(job.error || 'QAOA optimization job failed');
      }
      attempts++;
    }
    throw new Error('QAOA optimization job timed out waiting for a result');
  },
  getLatestOptimization: (cityId: number) => request<OptimizationResult>(`/optimization/${cityId}/latest`),
  getOptimizationHistory: (cityId: number) => request<OptimizationResult[]>(`/optimization/${cityId}/history`),
  getOptimizationExplanation: (runId: number) =>
    request<OptimizationExplanation>(`/optimization/runs/${runId}/explanation`),
  getCircuitSummary: (cityId: number, reps: number = 1) =>
    request<CircuitSummary>(`/optimization/${cityId}/circuit-summary?reps=${reps}`),
  getCircuitDiagramUrl: (cityId: number, reps: number = 1) =>
    requestBlobUrl(`/optimization/${cityId}/circuit-diagram?reps=${reps}`),

  // ---------------------------------------------------------------------
  // Scenarios & Simulations — backend/app/api/v1/simulation.py + optimization.py
  // ---------------------------------------------------------------------
  getWeatherScenarios: () => request<Scenario[]>('/simulation/weather-scenarios'),
  runWeatherScenario: (scenarioKey: string, asOfDate: string) =>
    request<WeatherScenarioResult>(`/simulation/weather-scenarios/${scenarioKey}/run?as_of_date=${asOfDate}`),
  getGenerationScenarios: (cityId: number) => request<Scenario[]>(`/optimization/${cityId}/generation-scenarios`),
  runGenerationScenario: (cityId: number, scenarioKey: string, forecastAsOfDate?: string) =>
    request<GenerationScenarioResult>(
      `/optimization/${cityId}/generation-scenarios/${scenarioKey}/run${forecastAsOfDate ? `?forecast_as_of_date=${forecastAsOfDate}` : ''}`,
      { method: 'POST' }
    ),
  getSimulationHistory: (cityId: number) => request<any[]>(`/simulation/${cityId}/history`),

  // ---------------------------------------------------------------------
  // Weather Telemetry — backend/app/api/v1/weather.py
  // ---------------------------------------------------------------------
  getCurrentWeather: (city: string) => request<WeatherReading>(`/weather/${city}/current`),
  getWeatherHistory: (city: string, days: number = 14) =>
    request<WeatherReading[]>(`/weather/${city}/history?days=${days}`)
};

export { ApiError };
