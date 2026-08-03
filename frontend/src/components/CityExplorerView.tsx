import React, { useEffect, useState } from 'react';
import { City, GridNode, TransmissionLine } from '../types/index.js';
import { api } from '../api/client.js';
import {
  Zap,
  Activity,
  Battery,
  Sun,
  Wind,
  Droplets,
  Flame,
  Radio,
  Server,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';

interface CityExplorerViewProps {
  city: City;
}

export const CityExplorerView: React.FC<CityExplorerViewProps> = ({ city }) => {
  const [nodes, setNodes] = useState<GridNode[]>([]);
  const [lines, setLines] = useState<TransmissionLine[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedNode, setSelectedNode] = useState<GridNode | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
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

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'thermal': return Flame;
      case 'hydro': return Droplets;
      case 'wind': return Wind;
      case 'solar': return Sun;
      case 'battery': return Battery;
      case 'industrial': return Server;
      default: return Zap;
    }
  };

  const getNodeColor = (type: string) => {
    switch (type) {
      case 'thermal': return 'text-amber-500 bg-amber-500/10 border-amber-500/30';
      case 'hydro': return 'text-cyan-400 bg-cyan-400/10 border-cyan-400/30';
      case 'wind': return 'text-teal-400 bg-teal-400/10 border-teal-400/30';
      case 'solar': return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30';
      case 'battery': return 'text-purple-400 bg-purple-400/10 border-purple-400/30';
      default: return 'text-blue-400 bg-blue-400/10 border-blue-400/30';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <Activity className="h-6 w-6 animate-spin" />
          <span className="font-semibold text-slate-300">Rendering Digital Twin Node Topology...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      
      {/* City Header */}
     <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
  <div>
    <div className="flex items-center gap-3">
      <h1 className="text-2xl font-extrabold text-white">{city.name} Grid Topology</h1>
      <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-bold border border-emerald-500/20">
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
      <span className="text-emerald-400 font-bold text-sm">
        {nodes.reduce((sum, n) => sum + n.transmission_capacity_mw, 0).toLocaleString()} MW
      </span>
    </div>
  </div>
</div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* SVG Interactive Topology Diagram */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-cyan-400 animate-pulse" />
              <h3 className="font-extrabold text-base text-white">Live Node & Transmission Lines</h3>
            </div>
            <span className="text-xs text-slate-400">Click a node to inspect telemetry</span>
          </div>

          <div className="relative h-96 w-full bg-slate-950/80 rounded-xl border border-slate-800/80 p-4 flex items-center justify-center grid-bg overflow-hidden">
            
            {/* SVG Lines */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {lines.map((line, idx) => {
                const fromNode = nodes.find(n => n.id === line.from_node_id);
                const toNode = nodes.find(n => n.id === line.to_node_id);
                if (!fromNode || !toNode) return null;

                // Scaled coordinates inside SVG canvas
                const x1 = 120 + (idx % 3) * 220;
                const y1 = 80 + Math.floor(idx / 3) * 120;
                const x2 = x1 + 140;
                const y2 = y1 + 50;

                return (
                  <g key={line.id}>
                    <line
                      x1={x1} y1={y1} x2={x2} y2={y2}
                      stroke={line.utilization_pct > 85 ? '#ef4444' : '#06b6d4'}
                      strokeWidth={3}
                      strokeDasharray={line.utilization_pct > 80 ? '6 4' : undefined}
                      className={line.utilization_pct > 80 ? 'animate-pulse' : ''}
                    />
                    <text
                      x={(x1 + x2) / 2}
                      y={(y1 + y2) / 2 - 8}
                      fill="#94a3b8"
                      fontSize="10"
                      className="font-mono"
                      textAnchor="middle"
                    >
                      {line.utilization_pct}%
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Nodes Rendered */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6 relative z-10 w-full max-w-2xl">
              {nodes.map((node) => {
                const Icon = getNodeIcon(node.node_type);
                const colorClass = getNodeColor(node.node_type);
                const isSelected = selectedNode?.id === node.id;

                return (
                  <button
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-4 rounded-xl border transition-all text-left flex flex-col justify-between ${
                      isSelected
                        ? 'bg-slate-800 border-cyan-400 shadow-lg shadow-cyan-500/20 scale-105'
                        : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className={`p-2 rounded-lg border ${colorClass}`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 uppercase">
                        {node.status}
                      </span>
                    </div>

                    <div>
                      <h4 className="font-bold text-xs text-white truncate">{node.name}</h4>
                      <p className="text-[11px] text-slate-400 capitalize mt-0.5">{node.node_type} facility</p>
                    </div>

                    <div className="mt-3 pt-2 border-t border-slate-800 flex justify-between items-center text-xs font-mono">
                      <span className="text-slate-400">Output:</span>
                      <span className="text-cyan-300 font-bold">{node.current_output_mw} MW</span>
                    </div>
                  </button>
                );
              })}
            </div>

          </div>
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
                <h3 className="text-lg font-bold text-white">{selectedNode.name}</h3>
                <span className="text-xs text-slate-400 capitalize">{selectedNode.node_type} Node • Lat {selectedNode.latitude.toFixed(2)} / Lng {selectedNode.longitude.toFixed(2)}</span>
              </div>

              <div className="space-y-3 font-mono text-xs">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Design Capacity:</span>
                  <span className="text-slate-200 font-bold">{selectedNode.capacity_mw} MW</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Current Output:</span>
                  <span className="text-emerald-400 font-bold">{selectedNode.current_output_mw} MW</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-slate-400">Capacity Factor:</span>
                    <span className="text-cyan-400 font-bold">
                      {Math.round((selectedNode.current_output_mw / selectedNode.capacity_mw) * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-cyan-500 h-full rounded-full transition-all"
                      style={{ width: `${(selectedNode.current_output_mw / selectedNode.capacity_mw) * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-300 space-y-1">
                <div className="font-bold text-cyan-400 flex items-center gap-1.5 mb-1">
                  <Activity className="h-4 w-4" />
                  <span>Substation Grid Operations</span>
                </div>
                <p>Monitored in real-time by Phase 2 automated SCADA telemetry. Load tap changers balanced.</p>
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-500 my-auto py-12">
              <Zap className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-xs">Select any node on the left canvas to inspect live metrics.</p>
            </div>
          )}
        </div>

      </div>

      {/* Transmission Lines Telemetry */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <h3 className="text-base font-bold text-white mb-4">Inter-Substation Transmission Corridors</h3>
        
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
                  style={{ width: `${line.utilization_pct}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
