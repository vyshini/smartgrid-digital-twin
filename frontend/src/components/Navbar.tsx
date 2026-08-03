import React from 'react';
import { City, User } from '../types/index.js';
import {
  Activity,
  Cpu,
  Zap,
  TrendingUp,
  CloudSun,
  Sliders,
  ShieldCheck,
  User as UserIcon,
  Globe,
  Radio
} from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  cities: City[];
  selectedCity: City | null;
  setSelectedCity: (city: City) => void;
  user: User | null;
  onOpenAuth: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  cities,
  selectedCity,
  setSelectedCity,
  user,
  onOpenAuth
}) => {
  const tabs = [
    { id: 'dashboard', label: 'National Grid Overview', icon: Globe },
    { id: 'explorer', label: 'City Digital Twin', icon: Zap },
    { id: 'forecast', label: 'LSTM Load Forecast', icon: TrendingUp },
    { id: 'qaoa', label: 'Quantum QAOA Engine', icon: Cpu },
    { id: 'scenarios', label: 'Scenario Sandbox', icon: Sliders },
    { id: 'weather', label: 'Weather Telemetry', icon: CloudSun },
  ];

  return (
    <header className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Logo & Platform Badge */}
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-md shadow-cyan-500/20">
              <Zap className="h-6 w-6 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg text-white tracking-tight">SmartGrid</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 font-semibold border border-cyan-500/30">
                  Phase 2 Digital Twin
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Indian Power Grid Forecasting & QAOA Optimization</p>
            </div>
          </div>

          {/* Active City Selector */}
          <div className="flex items-center gap-2 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
            <Radio className="h-4 w-4 text-emerald-400 animate-ping" />
            <span className="text-xs text-slate-400 font-medium">Node:</span>
            <select
              value={selectedCity?.id || cities[0]?.id || 1}
              onChange={(e) => {
                const found = cities.find(c => c.id === parseInt(e.target.value));
                if (found) setSelectedCity(found);
              }}
              className="bg-transparent text-sm font-semibold text-cyan-300 focus:outline-none cursor-pointer"
            >
              {cities.map((city) => (
                <option key={city.id} value={city.id} className="bg-slate-900 text-slate-200">
                  {city.name} ({city.state})
                </option>
              ))}
            </select>
          </div>

          {/* User Auth & System Status */}
          <div className="flex items-center gap-3">
            <div className="hidden lg:flex items-center gap-2 text-xs text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2.5 py-1 rounded-md">
              <Activity className="h-3.5 w-3.5" />
              <span>Grid Synced (50.02 Hz)</span>
            </div>

            <button
              onClick={onOpenAuth}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition"
            >
              {user ? (
                <>
                  <ShieldCheck className="h-4 w-4 text-cyan-400" />
                  <span className="capitalize">{user.role}</span>
                </>
              ) : (
                <>
                  <UserIcon className="h-4 w-4 text-slate-400" />
                  <span>Operator Login</span>
                </>
              )}
            </button>
          </div>

        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto py-2 scrollbar-none border-t border-slate-800/60">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-all ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm shadow-cyan-500/10'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

      </div>
    </header>
  );
};
