import React, { useEffect, useState } from 'react';
import { City, OptimizationResult, OptimizationExplanation, CircuitSummary } from '../types/index.js';
import { api } from '../api/client.js';
import {
  Cpu,
  Zap,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Battery,
  Image as ImageIcon
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend
} from 'recharts';

interface QAOAOptimizationViewProps {
  selectedCity: City;
}

const ALLOCATION_COLORS: Record<string, string> = {
  Coal: '#64748b',
  Hydro: '#06b6d4',
  Wind: '#14b8a6',
  Solar: '#facc15',
  Import: '#a78bfa',
};

export const QAOAOptimizationView: React.FC<QAOAOptimizationViewProps> = ({ selectedCity }) => {
  const [targetDemand, setTargetDemand] = useState<string>('');
  const [suggestedDemand, setSuggestedDemand] = useState<number | null>(null);
  const [latestDate, setLatestDate] = useState<string>('');
  const [running, setRunning] = useState<boolean>(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [history, setHistory] = useState<OptimizationResult[]>([]);
  const [explanation, setExplanation] = useState<OptimizationExplanation | null>(null);
  const [circuitSummary, setCircuitSummary] = useState<CircuitSummary | null>(null);
  const [circuitDiagramUrl, setCircuitDiagramUrl] = useState<string | null>(null);
  const [error, setError] = useState<string>('');
  const [loadingInitial, setLoadingInitial] = useState<boolean>(true);

  // Seed a sensible default from a REAL forecast, but the backend genuinely
  // supports omitting target_demand_mw entirely and auto-deriving it from a
  // fresh LSTM forecast server-side — so this is a suggestion, not a
  // required value. See run_grid_optimization_use_case.py's demand
  // resolution logic.
  useEffect(() => {
    let isMounted = true;
    setLoadingInitial(true);
    setResult(null);
    setExplanation(null);
    setCircuitSummary(null);
    if (circuitDiagramUrl) URL.revokeObjectURL(circuitDiagramUrl);
    setCircuitDiagramUrl(null);

    Promise.allSettled([
      api.getLatestAvailableDate(selectedCity.name),
      api.getLatestOptimization(selectedCity.id),
      api.getOptimizationHistory(selectedCity.id),
      api.getCircuitSummary(selectedCity.id),
    ]).then(([dateRes, latestRes, historyRes, circuitRes]) => {
      if (!isMounted) return;

      if (dateRes.status === 'fulfilled') {
        setLatestDate(dateRes.value.latest_available_date);
      }
      if (latestRes.status === 'fulfilled') {
        setResult(latestRes.value);
        setSuggestedDemand(latestRes.value.allocation_result.target_demand_mw);
      }
      if (historyRes.status === 'fulfilled') {
        setHistory(historyRes.value);
      }
      if (circuitRes.status === 'fulfilled') {
        setCircuitSummary(circuitRes.value);
      }
      setLoadingInitial(false);
    });

    return () => { isMounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCity.id, selectedCity.name]);

  useEffect(() => {
    if (result) {
      api.getOptimizationExplanation(result.id)
        .then(setExplanation)
        .catch(err => console.warn('No explanation available for this run:', err));
    }
  }, [result]);

  const handleRunQAOA = async () => {
    setRunning(true);
    setError('');
    try {
      const parsed = targetDemand.trim() === '' ? undefined : parseFloat(targetDemand);
      const runResult = await api.runQAOA(selectedCity.id, {
        targetDemandMw: parsed,
        forecastAsOfDate: parsed === undefined ? latestDate : undefined,
      });
      setResult(runResult);
      setSuggestedDemand(runResult.allocation_result.target_demand_mw);

      const [historyRes, circuitRes] = await Promise.allSettled([
        api.getOptimizationHistory(selectedCity.id),
        api.getCircuitSummary(selectedCity.id),
      ]);
      if (historyRes.status === 'fulfilled') setHistory(historyRes.value);
      if (circuitRes.status === 'fulfilled') setCircuitSummary(circuitRes.value);
    } catch (err: any) {
      setError(err.message || 'QAOA optimization run failed');
    } finally {
      setRunning(false);
    }
  };

  const handleLoadCircuitDiagram = async () => {
    try {
      const url = await api.getCircuitDiagramUrl(selectedCity.id);
      if (circuitDiagramUrl) URL.revokeObjectURL(circuitDiagramUrl);
      setCircuitDiagramUrl(url);
    } catch (err: any) {
      setError(err.message || 'Failed to load circuit diagram');
    }
  };

  useEffect(() => {
    // Revoke any blob URL on unmount to avoid leaking memory.
    return () => {
      if (circuitDiagramUrl) URL.revokeObjectURL(circuitDiagramUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loadingInitial) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <Activity className="h-6 w-6 animate-spin" />
          <span className="font-semibold text-slate-300">Loading QAOA Optimization State...</span>
        </div>
      </div>
    );
  }

  const allocation = result?.allocation_result;
  const renewablePct = allocation
    ? Math.round(
        (100 * (allocation.hydro_mw + allocation.wind_mw + allocation.solar_mw)) /
          Math.max(allocation.total_supply_mw, 1)
      )
    : null;

  const pieData = allocation
    ? [
        { name: 'Coal', value: allocation.coal_mw },
        { name: 'Hydro', value: allocation.hydro_mw },
        { name: 'Wind', value: allocation.wind_mw },
        { name: 'Solar', value: allocation.solar_mw },
        { name: 'Import', value: allocation.import_mw },
      ].filter(d => d.value > 0)
    : [];

  return (
    <div className="space-y-6 pb-12">

      {/* Header & Run Controls */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800">
        <div className="flex items-center gap-2 mb-1">
          <Cpu className="h-5 w-5 text-cyan-400" />
          <h1 className="text-2xl font-extrabold text-white">{selectedCity.name} QAOA Dispatch Engine</h1>
        </div>
        <p className="text-xs text-slate-400 mb-4">
          Real QUBO/Ising-formulated generation dispatch, solved via Qiskit's StatevectorSampler + COBYLA,
          checked against an exact classical brute-force optimum on every run.
        </p>

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-2 rounded-xl border border-slate-800 flex-1">
            <span className="text-xs text-slate-400 whitespace-nowrap">Target Demand (MW):</span>
            <input
              type="number"
              value={targetDemand}
              onChange={(e) => setTargetDemand(e.target.value)}
              placeholder={suggestedDemand != null ? `Suggested: ${suggestedDemand.toLocaleString()}` : 'Leave blank to auto-forecast'}
              className="bg-transparent text-sm font-semibold text-cyan-300 focus:outline-none flex-1 min-w-0"
            />
          </div>
          <button
            onClick={handleRunQAOA}
            disabled={running}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold text-xs shadow-lg shadow-cyan-500/20 transition whitespace-nowrap"
          >
            {running ? (
              <>
                <Activity className="h-4 w-4 animate-spin" />
                <span>Running QAOA (COBYLA)...</span>
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" />
                <span>Run Optimization</span>
              </>
            )}
          </button>
        </div>
        <p className="text-[11px] text-slate-500 mt-2">
          Leaving the demand field blank lets the backend derive it from a fresh next-day LSTM forecast automatically.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      {!result ? (
        <div className="p-10 rounded-2xl bg-slate-900/90 border border-slate-800 text-center text-sm text-slate-400">
          No optimization run on record for {selectedCity.name} yet. Run one above to see a real dispatch result.
        </div>
      ) : (
        <>
          {/* Result Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Optimization Score</span>
              <div className="text-2xl font-extrabold text-cyan-400 mt-1">{result.optimization_score}</div>
              <div className="flex items-center gap-1 mt-2 text-xs">
                {result.matched_classical_optimum ? (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-emerald-400 font-semibold">Exact classical match</span>
                  </>
                ) : (
                  <span className="text-amber-400 font-semibold">
                    Gap: {result.objective_gap.toExponential(2)}
                  </span>
                )}
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Grid Stability</span>
              <div className="text-2xl font-extrabold text-emerald-400 mt-1">
                {result.grid_stability_score != null ? `${result.grid_stability_score}%` : '—'}
              </div>
              <span className="text-xs text-slate-400 mt-2 block">Mismatch & battery-conflict penalty</span>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Cost Reduction</span>
              <div className="text-2xl font-extrabold text-white mt-1">
                {result.cost_reduction_pct != null ? `${result.cost_reduction_pct}%` : '—'}
              </div>
              <span className="text-xs text-slate-400 mt-2 block">vs. unoptimized all-coal baseline</span>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Renewable Share</span>
              <div className="text-2xl font-extrabold text-teal-300 mt-1">
                {renewablePct != null ? `${renewablePct}%` : '—'}
              </div>
              <span className="text-xs text-slate-400 mt-2 block">Hydro + Wind + Solar of dispatch</span>
            </div>
          </div>

          {/* Dispatch Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800">
              <h3 className="text-base font-bold text-white mb-4">Dispatched Generation Mix</h3>
              <div className="h-56">
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={78} paddingAngle={4} dataKey="value">
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={ALLOCATION_COLORS[entry.name] ?? '#94a3b8'} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                      <Legend formatter={(value) => <span className="text-xs text-slate-300">{value}</span>} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-slate-500">No dispatched sources.</div>
                )}
              </div>
            </div>

            <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3">
              <h3 className="text-base font-bold text-white mb-2">Dispatch Ledger</h3>
              {allocation && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                    <span className="text-slate-400">Target Demand:</span>
                    <span className="text-white font-semibold">{allocation.target_demand_mw.toLocaleString()} MW</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                    <span className="text-slate-400">Total Supply:</span>
                    <span className="text-white font-semibold">{allocation.total_supply_mw.toLocaleString()} MW</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                    <span className="text-slate-400">Mismatch:</span>
                    <span className={`font-semibold ${Math.abs(allocation.mismatch_mw) > 5 ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {allocation.mismatch_mw.toFixed(2)} MW
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                    <span className="text-slate-400 flex items-center gap-1"><Battery className="h-3.5 w-3.5" />Charge:</span>
                    <span className="text-cyan-300 font-semibold">{allocation.battery_charge_mw} MW</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                    <span className="text-slate-400 flex items-center gap-1"><Battery className="h-3.5 w-3.5" />Discharge:</span>
                    <span className="text-cyan-300 font-semibold">{allocation.battery_discharge_mw} MW</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between">
                    <span className="text-slate-400">Battery Conflict:</span>
                    <span className={allocation.battery_conflict ? 'text-red-400 font-semibold' : 'text-emerald-400 font-semibold'}>
                      {allocation.battery_conflict ? 'Yes' : 'No'}
                    </span>
                  </div>
                </div>
              )}

              {explanation && (
                <div className="mt-3 p-4 rounded-xl bg-cyan-500/5 border border-cyan-500/20 text-xs text-slate-300 space-y-2">
                  <p className="font-bold text-cyan-300 uppercase tracking-wider text-[10px]">Decision Support Summary</p>
                  <p>{explanation.summary}</p>
                  <p className="text-slate-400">{explanation.expected_savings}</p>
                  <p>
                    Risk Level:{' '}
                    <span className={
                      explanation.risk_level === 'high' ? 'text-red-400 font-bold' :
                      explanation.risk_level === 'medium' ? 'text-amber-400 font-bold' :
                      'text-emerald-400 font-bold'
                    }>
                      {explanation.risk_level.toUpperCase()}
                    </span>
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Quantum Circuit */}
          <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Cpu className="h-4 w-4 text-cyan-400" />
                Quantum Circuit (QAOAAnsatz)
              </h3>
              <button
                onClick={handleLoadCircuitDiagram}
                className="flex items-center gap-1.5 text-xs text-cyan-400 hover:underline font-semibold"
              >
                <ImageIcon className="h-3.5 w-3.5" />
                Render Circuit Diagram
              </button>
            </div>

            {circuitSummary ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 block">Qubits</span>
                  <span className="text-cyan-300 font-bold text-sm">{circuitSummary.n_qubits}</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 block">Reps (p)</span>
                  <span className="text-cyan-300 font-bold text-sm">{circuitSummary.reps}</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 block">Circuit Depth</span>
                  <span className="text-cyan-300 font-bold text-sm">{circuitSummary.circuit_depth}</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 block">Total Gates</span>
                  <span className="text-cyan-300 font-bold text-sm">{circuitSummary.total_gates}</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 mb-4">Circuit structure unavailable for this city.</p>
            )}

            {circuitDiagramUrl && (
              <img
                src={circuitDiagramUrl}
                alt={`${selectedCity.name} QAOA ansatz circuit diagram`}
                className="w-full rounded-xl border border-slate-800 bg-white"
              />
            )}
          </div>

          {/* Run History */}
          <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800">
            <h3 className="text-base font-bold text-white mb-4">Optimization Run History</h3>
            {history.length === 0 ? (
              <p className="text-xs text-slate-500">No prior runs recorded.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-400 border-b border-slate-800">
                      <th className="pb-2 pr-4">Run At</th>
                      <th className="pb-2 pr-4">Target (MW)</th>
                      <th className="pb-2 pr-4">Score</th>
                      <th className="pb-2 pr-4">Matched Optimum</th>
                      <th className="pb-2">Execution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(run => (
                      <tr key={run.id} className="border-b border-slate-800/50 text-slate-300">
                        <td className="py-2 pr-4 font-mono">{new Date(run.run_at).toLocaleString()}</td>
                        <td className="py-2 pr-4 font-mono">{run.allocation_result.target_demand_mw.toLocaleString()}</td>
                        <td className="py-2 pr-4 font-mono text-cyan-400">{run.optimization_score}</td>
                        <td className="py-2 pr-4">
                          {run.matched_classical_optimum ? (
                            <span className="text-emerald-400">Yes</span>
                          ) : (
                            <span className="text-amber-400">No</span>
                          )}
                        </td>
                        <td className="py-2 font-mono">{run.execution_time_ms} ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
