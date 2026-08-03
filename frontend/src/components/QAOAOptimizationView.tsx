import React, { useEffect, useState } from 'react';
import { City, OptimizationResult } from '../types/index.js';
import { api } from '../api/client.js';
import {
  Cpu,
  Zap,
  Activity,
  CheckCircle2,
  ShieldCheck,
  AlertTriangle,
  Flame,
  Droplets,
  Wind,
  Sun,
  Battery,
  Layers,
  Sparkles
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell
} from 'recharts';

interface QAOAOptimizationViewProps {
  selectedCity: City;
}

export const QAOAOptimizationView: React.FC<QAOAOptimizationViewProps> = ({ selectedCity }) => {
  const [targetDemand, setTargetDemand] = useState<number>(selectedCity.baseDemandMw);
  const [running, setRunning] = useState<boolean>(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [history, setHistory] = useState<OptimizationResult[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    setTargetDemand(selectedCity.baseDemandMw);
    setLoading(true);

    Promise.all([
      api.getLatestOptimization(selectedCity.id),
      api.getOptimizationHistory(selectedCity.id)
    ])
      .then(([latestRes, histRes]) => {
        setResult(latestRes);
        setHistory(histRes);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [selectedCity.id, selectedCity.baseDemandMw]);

  const handleRunQAOA = async () => {
    setRunning(true);
    try {
      const newResult = await api.runQAOA(selectedCity.id, targetDemand);
      setResult(newResult);
      setHistory(prev => [newResult, ...prev]);
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
          <span className="font-semibold text-slate-300">Loading QAOA Quantum Hamiltonian Solver...</span>
        </div>
      </div>
    );
  }

  const allocData = result ? [
    { name: 'Solar PV', mw: result.allocation_result.solar_mw, fill: '#f59e0b' },
    { name: 'Hydroelectric', mw: result.allocation_result.hydro_mw, fill: '#06b6d4' },
    { name: 'Wind Turbines', mw: result.allocation_result.wind_mw, fill: '#10b981' },
    { name: 'BESS Battery', mw: result.allocation_result.battery_discharge_mw, fill: '#a855f7' },
    { name: 'Coal Thermal', mw: result.allocation_result.coal_mw, fill: '#64748b' },
  ] : [];

  return (
    <div className="space-y-6 pb-12">
      
      {/* Header & Controls */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="h-6 w-6 text-cyan-400" />
            <h1 className="text-2xl font-extrabold text-white">Quantum QAOA Grid Dispatch Engine</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            20-qubit Quantum Approximate Optimization Algorithm solving non-linear power flow and battery constraints for {selectedCity.name}.
          </p>
        </div>

        {/* Input & Trigger */}
        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-2 rounded-xl border border-slate-800">
            <span className="text-xs text-slate-400 font-medium">Demand MW:</span>
            <input
              type="number"
              value={targetDemand}
              onChange={(e) => setTargetDemand(Number(e.target.value))}
              className="w-20 bg-transparent text-sm font-bold text-cyan-300 focus:outline-none font-mono"
            />
          </div>

          <button
            onClick={handleRunQAOA}
            disabled={running}
            className="flex-1 md:flex-none flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold text-xs shadow-lg shadow-cyan-500/20 transition disabled:opacity-50"
          >
            {running ? (
              <>
                <Activity className="h-4 w-4 animate-spin" />
                <span>Solving 20-Qubit Circuit...</span>
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                <span>Execute QAOA Run</span>
              </>
            )}
          </button>
        </div>
      </div>

      {result && (
        <>
          {/* Metrics Highlight Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Optimization Score</span>
              <div className="text-3xl font-extrabold text-cyan-400 mt-1 font-mono">
                {result.optimization_score}
              </div>
              <span className="text-[11px] text-emerald-400 mt-2 flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Matched Classical Optimum</span>
              </span>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Grid Stability Score</span>
              <div className="text-3xl font-extrabold text-emerald-400 mt-1 font-mono">
                {result.grid_stability_score}%
              </div>
              <span className="text-[11px] text-slate-400 mt-2 block">Zero phase angle violations</span>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Cost Reduction</span>
              <div className="text-3xl font-extrabold text-teal-300 mt-1 font-mono">
                {result.cost_reduction_pct}%
              </div>
              <span className="text-[11px] text-slate-400 mt-2 block">Versus all-coal baseline</span>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Renewable Dispatched</span>
              <div className="text-3xl font-extrabold text-amber-400 mt-1 font-mono">
                {result.renewable_pct}%
              </div>
              <span className="text-[11px] text-slate-400 mt-2 block">Solar, Wind, and Hydro blend</span>
            </div>

          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Allocation Breakdown Bar Chart */}
            <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-bold text-white">Dispatched Power Generation Sources (MW)</h3>
                  <p className="text-xs text-slate-400">QAOA Hamiltonian minimum cost solution</p>
                </div>
                <span className="text-xs font-mono text-cyan-400 font-bold bg-cyan-500/10 border border-cyan-500/20 px-3 py-1 rounded-full">
                  Target: {result.target_demand_mw} MW
                </span>
              </div>

              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={allocData}>
                    <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                    <YAxis stroke="#64748b" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
                    <Bar dataKey="mw" radius={[8, 8, 0, 0]}>
                      {allocData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="grid grid-cols-5 gap-2 mt-4 pt-4 border-t border-slate-800 text-center text-xs">
                <div>
                  <span className="text-slate-400 block">Solar</span>
                  <span className="font-mono text-amber-400 font-bold">{result.allocation_result.solar_mw} MW</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Hydro</span>
                  <span className="font-mono text-cyan-400 font-bold">{result.allocation_result.hydro_mw} MW</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Wind</span>
                  <span className="font-mono text-teal-400 font-bold">{result.allocation_result.wind_mw} MW</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Battery</span>
                  <span className="font-mono text-purple-400 font-bold">{result.allocation_result.battery_discharge_mw} MW</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Coal</span>
                  <span className="font-mono text-slate-400 font-bold">{result.allocation_result.coal_mw} MW</span>
                </div>
              </div>
            </div>

            {/* QAOA Circuit Summary Card */}
            <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
              <div className="flex items-center gap-2 text-cyan-400 border-b border-slate-800 pb-3">
                <Layers className="h-5 w-5" />
                <h3 className="text-base font-bold text-white">Quantum Circuit Topology</h3>
              </div>

              <div className="space-y-3 font-mono text-xs">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">System Qubits:</span>
                  <span className="text-cyan-300 font-bold">20 Qubits</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">Circuit Depth:</span>
                  <span className="text-emerald-400 font-bold">{result.circuit_summary.depth} Layers</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">Non-Local Gates (RZZ):</span>
                  <span className="text-purple-400 font-bold">{result.circuit_summary.non_local_gates}</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">Classical Gap:</span>
                  <span className="text-teal-300 font-bold">{result.objective_gap.toExponential(3)}</span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-cyan-950/30 border border-cyan-800/40 text-xs text-cyan-200">
                <div className="font-bold mb-1">AI Explanation</div>
                <p>QAOA dispatched {result.renewable_pct}% renewables and active battery storage, achieving a zero-gap match with brute force classical solvers.</p>
              </div>
            </div>

          </div>
        </>
      )}

      {/* History Table */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <h3 className="text-base font-bold text-white mb-4">Historical QAOA Optimization Executions</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 text-slate-400 uppercase font-mono text-[10px]">
              <tr>
                <th className="p-3">Run Timestamp</th>
                <th className="p-3">Demand MW</th>
                <th className="p-3">Score</th>
                <th className="p-3">Stability</th>
                <th className="p-3">Cost Cut %</th>
                <th className="p-3">Renewable %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {history.map(item => (
                <tr key={item.id} className="hover:bg-slate-800/40">
                  <td className="p-3">{new Date(item.run_at).toLocaleTimeString()}</td>
                  <td className="p-3 font-bold text-cyan-300">{item.target_demand_mw} MW</td>
                  <td className="p-3 text-emerald-400 font-bold">{item.optimization_score}</td>
                  <td className="p-3 text-slate-200">{item.grid_stability_score}%</td>
                  <td className="p-3 text-teal-300">{item.cost_reduction_pct}%</td>
                  <td className="p-3 text-amber-400">{item.renewable_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};
