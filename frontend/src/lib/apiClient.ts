import axios, { AxiosError } from 'axios';
import { clearSessionStorage, readSession, writeSession } from '../core/tokenStorage';
import type {
  ActualVsPredictedPoint,
  City,
  CityDetail,
  ForecastResponse,
  Horizon,
  LossCurvePoint,
  NationalOverview,
  OptimizationExplanation,
  OptimizationJobAccepted,
  OptimizationJobStatus,
  OptimizationResult,
  Scenario,
  SimulationHistoryRecord,
  TokenResponse,
  WeatherReading,
} from '../core/types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise;
  }
  const session = readSession();
  if (!session?.refreshToken) {
    throw new Error('No refresh token available');
  }

  refreshPromise = axios
    .post<{ access_token: string; expires_in: number }>(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: session.refreshToken,
    })
    .then((response) => {
      writeSession({
        accessToken: response.data.access_token,
        refreshToken: session.refreshToken,
        user: session.user,
      });
      return response.data.access_token;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

api.interceptors.request.use((config) => {
  const session = readSession();
  if (session?.accessToken) {
    config.headers.Authorization = `Bearer ${session.accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const originalRequest = error.config;
    if (status !== 401 || !originalRequest) {
      return Promise.reject(error);
    }

    const isAuthCall = (originalRequest.url ?? '').includes('/auth/');
    const hasRetried = Boolean((originalRequest as { _retry?: boolean })._retry);
    if (isAuthCall || hasRetried) {
      clearSessionStorage();
      return Promise.reject(error);
    }

    try {
      (originalRequest as { _retry?: boolean })._retry = true;
      const newToken = await refreshAccessToken();
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return api.request(originalRequest);
    } catch (refreshError) {
      clearSessionStorage();
      return Promise.reject(refreshError);
    }
  },
);

export const apiClient = {
  async login(username: string, password: string): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/auth/login', { username, password });
    return response.data;
  },
  async getMe() {
    const response = await api.get('/auth/me');
    return response.data;
  },
  async listCities() {
    const response = await api.get<City[]>('/cities');
    return response.data;
  },
  async getCity(cityId: number) {
    const response = await api.get<CityDetail>(`/cities/${cityId}`);
    return response.data;
  },
  async getNationalOverview() {
    const response = await api.get<NationalOverview>('/dashboard/overview');
    return response.data;
  },
  async predictLoad(city: string, horizon: Horizon, asOfDate?: string) {
    const response = await api.get<ForecastResponse>(`/forecast/${city}/${horizon}`, {
      params: asOfDate ? { as_of_date: asOfDate } : {},
    });
    return response.data;
  },
  async getLossCurve(city: string) {
    const response = await api.get<LossCurvePoint[]>(`/forecast/${city}/loss-curve`);
    return response.data;
  },
  async getActualVsPredicted(city: string, horizon: Horizon) {
    const response = await api.get<ActualVsPredictedPoint[]>(`/forecast/${city}/actual-vs-predicted`, {
      params: { horizon },
    });
    return response.data;
  },
  async runOptimization(cityId: number, payload: { target_demand_mw?: number; forecast_as_of_date?: string }) {
    const response = await api.post<OptimizationJobAccepted>(`/optimization/${cityId}/run`, payload);
    return response.data;
  },
  async getOptimizationJob(jobId: string) {
    const response = await api.get<OptimizationJobStatus>(`/optimization/jobs/${jobId}`);
    return response.data;
  },
  async getLatestOptimization(cityId: number) {
    const response = await api.get<OptimizationResult>(`/optimization/${cityId}/latest`);
    return response.data;
  },
  async getOptimizationHistory(cityId: number) {
    const response = await api.get<OptimizationResult[]>(`/optimization/${cityId}/history`);
    return response.data;
  },
  async getOptimizationExplanation(runId: number) {
    const response = await api.get<OptimizationExplanation>(`/optimization/runs/${runId}/explanation`);
    return response.data;
  },
  async getWeatherCurrent(city: string) {
    const response = await api.get<WeatherReading>(`/weather/${city}/current`);
    return response.data;
  },
  async getWeatherHistory(city: string, days = 14) {
    const response = await api.get<WeatherReading[]>(`/weather/${city}/history`, { params: { days } });
    return response.data;
  },
  async listWeatherScenarios() {
    const response = await api.get<Scenario[]>('/simulation/weather-scenarios');
    return response.data;
  },
  async runWeatherScenario(key: string, asOfDate: string) {
    const response = await api.get<Record<string, unknown>>(`/simulation/weather-scenarios/${key}/run`, {
      params: { as_of_date: asOfDate },
    });
    return response.data;
  },
  async listGenerationScenarios(cityId: number) {
    const response = await api.get<Scenario[]>(`/optimization/${cityId}/generation-scenarios`);
    return response.data;
  },
  async runGenerationScenario(cityId: number, key: string, asOfDate: string) {
    const response = await api.post<Record<string, unknown>>(
      `/optimization/${cityId}/generation-scenarios/${key}/run`,
      null,
      { params: { forecast_as_of_date: asOfDate } },
    );
    return response.data;
  },
  async getSimulationHistory(cityId: number) {
    const response = await api.get<SimulationHistoryRecord[]>(`/simulation/${cityId}/history`);
    return response.data;
  },
};
