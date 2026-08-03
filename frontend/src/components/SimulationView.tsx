import React, { useEffect, useState } from 'react';
import { City, Scenario, WeatherScenarioResult, GenerationScenarioResult } from '../types/index.js';
import { api } from '../api/client.js';
import {
  Sliders,
  CloudRain,
  Activity,
  AlertOctagon,
  ArrowRight
} from 'lucide-react';

interface SimulationViewProps {
  selectedCity: City;
}

export const SimulationView: React.FC<SimulationViewProps> = ({ selectedCity }) => {
  const [weatherScenarios, setWeatherScenarios] = useState<Scenario[]>([]);
  const [genScenarios, setGenScenarios] = useState<Scenario[]>([]);
  const [activeWeatherScenario, setActiveWeatherScenario] = useState<string>('');
  const [activeGenScenario, setActiveGenScenario] = useState<string>('');
  const [latestDate, setLatestDate] = useState<string>('');

  const [weatherResult, setWeatherResult] = useState<WeatherScenarioResult | null>(null);
  const [genResult, setGenResult] = useState<GenerationScenarioResult | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setWeatherResult(null);
    setGenResult(null);

    Promise.allSettled([
      api.getWeatherScenarios(),
      api.getGenerationScenarios(selectedCity.id),
      api.getLatestAvailableDate(selectedCity.name),
    ]).then(([wRes, gRes, dRes]) => {
      if (!isMounted) return;

      // Scenarios are city-scoped on the real backend (e.g. only Delhi has
      // heatwave_delhi/solar_failure_delhi today) — filter to this city
      // rather than assuming every scenario key applies everywhere.
      const w = wRes.status === 'fulfilled' ? wRes.value.filter(s => s.city === selectedCity.name) : [];
      const g = gRes.status === 'fulfilled' ? gRes.value.filter(s => s.city === selectedCity.name) : [];
      setWeatherScenarios(w);
      setGenScenarios(g);
      setActiveWeatherScenario(w[0]?.key ?? '');
      setActiveGenScenario(g[0]?.key ?? '');
      if (dRes.status === 'fulfilled') setLatestDate(dRes.value.latest_available_date);
      setLoading(false);
    });

    return () => { isMounted = false; };
  }, [selectedCity.id, selectedCity.name]);

  const handleRunWeatherScenario = async (key: string) => {
    if (!latestDate) return;
    setRunning(true);
    setActiveWeatherScenario(key);
    try {
      const res = await api.runWeatherScenario(key, latestDate);
      setWeatherResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  const handleRunGenScenario = async (key: string) => {
    setRunning(true);
    setActiveGenScenario(key);
    try {
      const res = await api.runGenerationScenario(selectedCity.id, key, latestDate || undefined);
      setGenResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <Activity className="h-6 w-6 animate-spin" />
          <span className="font-semibold text-slate-300">Loading Grid Scenario Sandbox...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">

      {/* Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800">
        <div className="flex items-center gap-2">
          <Sliders className="h-6 w-6 text-cyan-400" />
          <h1 className="text-2xl font-extrabold text-white">Grid Scenario Simulation Sandbox</h1>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          Stress-test {selectedCity.name}'s power grid under extreme weather anomalies and sudden generation outages.
        </p>
      </div>

      {/* Weather Scenarios Section */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <CloudRain className="h-5 w-5 text-cyan-400" />
          <span>Weather Anomaly Scenarios (LSTM Re-forecast)</span>
        </h2>

        {weatherScenarios.length === 0 ? (
          <p className="text-xs text-slate-500">No weather scenarios defined for {selectedCity.name} yet.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {weatherScenarios.map(sc => (
              <button
                key={sc.key}
                onClick={() => handleRunWeatherScenario(sc.key)}
                disabled={running}
                className={`p-4 rounded-xl border text-left transition-all disabled:opacity-50 ${
                  activeWeatherScenario === sc.key
                    ? 'bg-slate-800 border-cyan-400 shadow-lg shadow-cyan-500/10'
                    : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                }`}
              >
                <h3 className="font-bold text-xs text-white mb-1">{sc.name}</h3>
                <p className="text-[11px] text-slate-400">{sc.description}</p>
                <div className="mt-3 text-xs font-bold text-cyan-400 flex items-center gap-1">
                  <span>Run Weather Test</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </button>
            ))}
          </div>
        )}

        {weatherResult && (
          <div className="p-5 rounded-xl bg-slate-950 border border-cyan-500/30 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Simulation Outcome Telemetry</span>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 font-mono text-xs">
              <div>
                <span className="text-slate-400 block">Baseline Demand</span>
                <span className="text-slate-200 font-bold text-sm">{weatherResult.baseline_predicted_mw} MW</span>
              </div>
              <div>
                <span className="text-slate-400 block">Scenario Demand</span>
                <span className="text-amber-400 font-bold text-sm">{weatherResult.scenario_predicted_mw} MW</span>
              </div>
              <div>
                <span className="text-slate-400 block">Load Delta</span>
                <span className={`font-bold text-sm ${weatherResult.delta_mw >= 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {weatherResult.delta_mw >= 0 ? `+${weatherResult.delta_mw}` : weatherResult.delta_mw} MW
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Percentage Shift</span>
                <span className={`font-bold text-sm ${weatherResult.delta_pct >= 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {weatherResult.delta_pct >= 0 ? `+${weatherResult.delta_pct}%` : `${weatherResult.delta_pct}%`}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Generation Scenarios Section */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <AlertOctagon className="h-5 w-5 text-amber-400" />
          <span>Generation Capacity Disruptions (QAOA Re-dispatch)</span>
        </h2>

        {genScenarios.length === 0 ? (
          <p className="text-xs text-slate-500">No generation scenarios defined for {selectedCity.name} yet.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {genScenarios.map(sc => (
              <button
                key={sc.key}
                onClick={() => handleRunGenScenario(sc.key)}
                disabled={running}
                className={`p-4 rounded-xl border text-left transition-all disabled:opacity-50 ${
                  activeGenScenario === sc.key
                    ? 'bg-slate-800 border-amber-400 shadow-lg shadow-amber-500/10'
                    : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                }`}
              >
                <h3 className="font-bold text-xs text-white mb-1">{sc.name}</h3>
                <p className="text-[11px] text-slate-400">{sc.description}</p>
                <div className="mt-3 text-xs font-bold text-amber-400 flex items-center gap-1">
                  <span>Test QAOA Response</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </button>
            ))}
          </div>
        )}

        {genResult && (
          <div className="p-5 rounded-xl bg-slate-950 border border-amber-500/30 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-amber-400">QAOA Emergency Re-dispatch Strategy</span>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-400 block">Coal Thermal</span>
                <span className="text-slate-200 font-bold">{genResult.scenario_allocation.coal_mw} MW</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-400 block">Solar PV</span>
                <span className="text-amber-400 font-bold">{genResult.scenario_allocation.solar_mw} MW</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-400 block">Hydro Dam</span>
                <span className="text-cyan-400 font-bold">{genResult.scenario_allocation.hydro_mw} MW</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-400 block">Wind Turbines</span>
                <span className="text-teal-400 font-bold">{genResult.scenario_allocation.wind_mw} MW</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-400 block">Battery Discharged</span>
                <span className="text-purple-400 font-bold">{genResult.scenario_allocation.battery_discharge_mw} MW</span>
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};
