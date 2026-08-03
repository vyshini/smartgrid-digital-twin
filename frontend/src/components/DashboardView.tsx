import React from 'react';
import { NationalOverview, City } from '../types/index.js';
import {
  Zap,
  ShieldCheck,
  TrendingUp,
  Leaf,
  AlertTriangle,
  ArrowUpRight,
  Activity,
  Cpu,
  BarChart2
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';

interface DashboardViewProps {
  overview: NationalOverview | null;
  cities: City[];
  onSelectCity: (city: City) => void;
  onNavigateTab: (tab: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  overview,
  cities,
  onSelectCity,
  onNavigateTab
}) => {
  if (!overview) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <Activity className="h-6 w-6 animate-spin" />
          <span className="font-semibold text-slate-300">Syncing National Grid Telemetry...</span>
        </div>
      </div>
    );
  }

  // National generation mix — derived from REAL avg_renewable_pct, not
  // fabricated. A full per-source (coal/hydro/wind/solar) breakdown would
  // require fetching each city's /optimization/{id}/latest allocation_result
  // and summing it — a reasonable v2 feature once more cities have real
  // optimization runs (see the advisories banner below for current coverage).
  const hasRenewableData = overview.avg_renewable_pct != null;
  const renewablePct = overview.avg_renewable_pct ?? 0;
  const genMixData = hasRenewableData
    ? [
        { name: 'Renewable (Hydro+Wind+Solar)', value: renewablePct, color: '#10b981' },
        { name: 'Non-Renewable (Coal+Import)', value: 100 - renewablePct, color: '#64748b' },
      ]
    : [];

  const cityBarData = overview.cities
    .filter(c => c.latest_forecast_mw != null) // honest: only plot cities with real forecasts
    .map(c => ({
      name: c.city_name,
      demand: c.latest_forecast_mw as number,
    }));

  return (
    <div className="space-y-6 pb-12">

      {/* Banner / Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800 shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span className="text-xs font-bold text-emerald-400 tracking-wider uppercase">Live Telemetry Synchronized</span>
          </div>
          <h1 className="text-2xl font-extrabold text-white mt-1">National Smart Grid Digital Twin</h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time monitoring across {overview.total_cities} Indian urban power hubs
            ({overview.cities_with_data} with optimization data) integrated with Quantum QAOA optimization.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigateTab('qaoa')}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs shadow-lg shadow-cyan-500/20 transition"
          >
            <Cpu className="h-4 w-4" />
            <span>Run QAOA Optimization</span>
          </button>
        </div>
      </div>

      {/* Primary Telemetry Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">National Demand</span>
            <Zap className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-extrabold text-white">
            {overview.national_forecast_demand_mw != null
              ? `${overview.national_forecast_demand_mw.toLocaleString()} MW`
              : '— no forecasts yet'}
          </div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
            <ArrowUpRight className="h-3.5 w-3.5 text-amber-400" />
            <span>Sum of latest per-city forecasts</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Grid Stability</span>
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-extrabold text-emerald-400">
            {overview.avg_grid_stability_score != null ? `${overview.avg_grid_stability_score}%` : '—'}
          </div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
            <span>Avg. across {overview.cities_with_data} optimized {overview.cities_with_data === 1 ? 'city' : 'cities'}</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">QAOA Score</span>
            <Cpu className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-extrabold text-cyan-400">
            {overview.avg_optimization_score != null ? overview.avg_optimization_score : '—'}
          </div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
            <span>vs. classical brute-force baseline</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Renewable Share</span>
            <Leaf className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-extrabold text-white">
            {overview.avg_renewable_pct != null ? `${overview.avg_renewable_pct}%` : '—'}
          </div>
          <div className="text-xs text-emerald-400 mt-2">
            Hydro + Wind + Solar of dispatched supply
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">CO2 Abatement</span>
            <TrendingUp className="h-4 w-4 text-teal-400" />
          </div>
          <div className="text-2xl font-extrabold text-teal-300">
            {overview.avg_co2_reduction_pct != null ? `${overview.avg_co2_reduction_pct}%` : '—'}
          </div>
          <div className="text-xs text-slate-400 mt-2">
            vs. an unoptimized all-coal baseline
          </div>
        </div>

      </div>

      {/* System Alerts Banner */}
      {overview.system_alerts && overview.system_alerts.length > 0 && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            <span className="font-bold text-xs uppercase tracking-wider">Active Grid Telemetry Advisories ({overview.system_alerts.length})</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {overview.system_alerts.map((alert, idx) => (
              <div key={idx} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-300 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400"></span>
                <span>{alert}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* National Visualizations Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* City Demand Breakdown */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <BarChart2 className="h-5 w-5 text-cyan-400" />
                <span>Metropolitan City Power Demand (MW)</span>
              </h3>
              <p className="text-xs text-slate-400">
                {cityBarData.length > 0
                  ? 'Latest real LSTM forecasts, per city'
                  : 'No cities have a forecast on record yet — run one from the LSTM Load Forecast tab'}
              </p>
            </div>
            <button
              onClick={() => onNavigateTab('forecast')}
              className="text-xs text-cyan-400 hover:underline font-semibold"
            >
              LSTM Analytics →
            </button>
          </div>

          <div className="h-64">
            {cityBarData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cityBarData}>
                  <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', color: '#f8fafc' }}
                  />
                  <Bar dataKey="demand" fill="#06b6d4" radius={[6, 6, 0, 0]} name="Demand MW" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500">
                No real forecast data to display yet.
              </div>
            )}
          </div>
        </div>

        {/* National Clean Energy Mix */}
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="mb-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Leaf className="h-5 w-5 text-emerald-400" />
              <span>Renewable vs Non-Renewable Mix</span>
            </h3>
            <p className="text-xs text-slate-400">Average across cities with a completed QAOA run</p>
          </div>

          <div className="h-52">
            {hasRenewableData ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={genMixData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {genMixData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  />
                  <Legend formatter={(value) => <span className="text-xs text-slate-300 font-medium">{value}</span>} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-500 text-center px-4">
                No optimization runs yet — run QAOA for at least one city to see a real generation mix.
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Cities Overview Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-white">Urban Grid Nodes ({cities.length})</h2>
            <p className="text-xs text-slate-400">Select any city to inspect its local transmission network, nodes, and load profile.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {cities.map(city => {
            const cityData = overview.cities.find(c => c.city_id === city.id);
            return (
              <div
                key={city.id}
                onClick={() => {
                  onSelectCity(city);
                  onNavigateTab('explorer');
                }}
                className="p-5 rounded-2xl bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-cyan-500/50 shadow-lg cursor-pointer transition-all duration-200 group"
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="font-extrabold text-base text-white group-hover:text-cyan-300 transition">
                      {city.name}
                    </h3>
                    <span className="text-xs text-slate-400">{city.state} • {city.timezone}</span>
                  </div>
                  <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 text-xs font-bold border border-slate-700">
                    Pop. {(city.population / 1_000_000).toFixed(1)}M
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex justify-between text-slate-400">
                    <span>Latest Forecast:</span>
                    <span className="font-mono text-slate-200 font-semibold">
                      {cityData?.latest_forecast_mw != null ? `${cityData.latest_forecast_mw.toLocaleString()} MW` : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>QAOA Renewable Share:</span>
                    <span className="font-mono text-emerald-400 font-semibold">
                      {cityData?.renewable_pct != null ? `${cityData.renewable_pct}%` : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Cost Reduction:</span>
                    <span className="font-mono text-cyan-400 font-semibold">
                      {cityData?.cost_reduction_pct != null ? `${cityData.cost_reduction_pct}%` : '—'}
                    </span>
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs text-cyan-400 font-semibold group-hover:translate-x-1 transition-transform">
                  <span>Open Digital Twin</span>
                  <ArrowUpRight className="h-4 w-4" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
};
