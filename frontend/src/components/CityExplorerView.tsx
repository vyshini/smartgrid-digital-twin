import React, { useEffect, useState } from 'react';
import { City, GridNode, TransmissionLine } from '../types/index.js';
import { api } from '../api/client.js';
import {
  Zap,
  Activity,
  ShieldCheck,
  ShieldAlert,
  AlertOctagon,
  PowerOff,
  Radio,
  Server
} from 'lucide-react';

interface CityExplorerViewProps {
  city: City;
}

// The real backend models grid nodes as generic substations — a static
// transmission_capacity_mw and a health status, nothing more. There is no
// generation "type" (thermal/hydro/wind/solar) or live "current output"
// measurement on a node in this schema, so status is what drives the icon.
const NODE_STATUS_STYLE: Record<GridNode['status'], { icon: React.ElementType; color: string; label: string }> = {
  healthy: { icon: ShieldCheck, color: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30', label: 'Healthy' },
  degraded: { icon: ShieldAlert, color: 'text-amber-400 bg-amber-400/10 border-amber-400/30', label: 'Degraded' },
  critical: { icon: AlertOctagon, color: 'text-red-400 bg-red-400/10 border-red-400/30', label: 'Critical' },
  offline: { icon: PowerOff, color: 'text-slate-500 bg-slate-500/10 border-slate-500/30', label: 'Offline' },
};

export const CityExplorerView: React.FC<CityExplorerViewProps> = ({ city }) => {
  const [nodes, setNodes] = useState<GridNode[]>([]);
  const [lines, setLines] = useState<TransmissionLine[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedNode, setSelectedNode] = useState<GridNode | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setSelectedNode(null);
    api.getCityDetail(city.id)
      .then(res => {
        if (isMounted) {
          setNodes(res.grid_nodes);
          setLines(res.transmission_lines);
          if (res.grid_nodes.length > 0) setSelectedNode(res.grid_nodes[0]);
          setLoading(false);
        }
      })
      .catch(err => {
        console.error(err);
        if (isMounted) setLoading(false);
      });
    return () => { isMounted = false; };
  }, [city.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <Activity className="h-6 w-6 animate-spin" />
          <span className="font-semibold text-slate-300">Loading Grid Topology...</span>
        </div>
      </div>
    );
  }

  const totalCapacity = nodes.reduce((sum, n) => sum + n.transmission_capacity_mw, 0);
  const connectedLinesFor = (nodeId: number) =>
    lines.filter(l => l.from_node_id === nodeId || l.to_node_id === nodeId);

  return (
    <div className="space-y-6 pb-12">

      {/* Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold text-white">{city.name} Grid Topology</h1>
            <span className="px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 text-xs font-bold border border-cyan-500/20">
              {city.timezone}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {city.state} • Population {city.population.toLocaleString()}
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800">
            <span className="text-slate-400 block">Grid Nodes</span>
            <span className="text-cyan-400 font-bold text-sm">{nodes.length} Active</span>
          </div>
          <div className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800">
            <span className="text-slate-400 block">Total Capacity</span>
            <span className="text-emerald-400 font-bold text-sm">{totalCapacity.toLocaleString()} MW</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Node Grid */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-cyan-400 animate-pulse" />
              <h3 className="font-extrabold text-base text-white">Substation Nodes</h3>
            </div>
            <span className="text-xs text-slate-400">Click a node to inspect telemetry</span>
          </div>

          {nodes.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-xs text-slate-500">
              No grid nodes seeded for this city yet.
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {nodes.map((node) => {
                const style = NODE_STATUS_STYLE[node.status] ?? NODE_STATUS_STYLE.healthy;
                const Icon = style.icon;
                const isSelected = selectedNode?.id === node.id;

                return (
                  <button
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-4 rounded-xl border transition-all text-left flex flex-col justify-between ${
                      isSelected
                        ? 'bg-slate-800 border-cyan-400 shadow-lg shadow-cyan-500/20 scale-[1.02]'
                        : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className={`p-2 rounded-lg border ${style.color}`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${style.color}`}>
                        {style.label}
                      </span>
                    </div>

                    <div>
                      <h4 className="font-bold text-xs text-white truncate">{node.node_code}</h4>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {connectedLinesFor(node.id).length} transmission {connectedLinesFor(node.id).length === 1 ? 'line' : 'lines'}
                      </p>
                    </div>

                    <div className="mt-3 pt-2 border-t border-slate-800 flex justify-between items-center text-xs font-mono">
                      <span className="text-slate-400">Capacity:</span>
                      <span className="text-cyan-300 font-bold">{node.transmission_capacity_mw.toLocaleString()} MW</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Node Inspector Sidebar */}
        <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl flex flex-col justify-between">
          {selectedNode ? (
            <div className="space-y-5">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Selected Node Telemetry</span>
                <span className="text-xs font-mono text-slate-400">ID #{selectedNode.id}</span>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Server className="h-5 w-5 text-cyan-400" />
                  {selectedNode.node_code}
                </h3>
                <span className="text-xs text-slate-400 capitalize">
                  Status: {NODE_STATUS_STYLE[selectedNode.status]?.label ?? selectedNode.status}
                </span>
              </div>

              <div className="space-y-3 font-mono text-xs">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Transmission Capacity:</span>
                  <span className="text-slate-200 font-bold">{selectedNode.transmission_capacity_mw.toLocaleString()} MW</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Connected Lines:</span>
                  <span className="text-emerald-400 font-bold">{connectedLinesFor(selectedNode.id).length}</span>
                </div>

                {connectedLinesFor(selectedNode.id).map(line => (
                  <div key={line.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800/60 flex justify-between items-center text-[11px]">
                    <span className="text-slate-500">Line #{line.id}:</span>
                    <span className={line.utilization_pct > 80 ? 'text-amber-400 font-bold' : 'text-cyan-300 font-bold'}>
                      {line.utilization_pct}% utilized
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-500 my-auto py-12">
              <Zap className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-xs">Select any node on the left to inspect its details.</p>
            </div>
          )}
        </div>

      </div>

      {/* Transmission Lines Telemetry */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <h3 className="text-base font-bold text-white mb-4">Inter-Substation Transmission Corridors</h3>

        {lines.length === 0 ? (
          <div className="text-xs text-slate-500 py-6 text-center">No transmission lines seeded for this city yet.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {lines.map(line => (
              <div key={line.id} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">Line #{line.id} ({line.length_km} km)</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    line.utilization_pct > 80 ? 'bg-amber-500/10 text-amber-400' : 'bg-emerald-500/10 text-emerald-400'
                  }`}>
                    {line.utilization_pct}% Utilized
                  </span>
                </div>

                <div className="flex justify-between text-slate-400 font-mono">
                  <span>Power Flow:</span>
                  <span className="text-cyan-300 font-semibold">{line.current_load_mw} / {line.capacity_mw} MW</span>
                </div>

                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${line.utilization_pct > 80 ? 'bg-amber-400' : 'bg-cyan-400'}`}
                    style={{ width: `${Math.min(line.utilization_pct, 100)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
};
