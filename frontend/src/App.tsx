import React, { useEffect, useState } from 'react';
import { City, NationalOverview, User } from './types/index.js';
import { api } from './api/client.js';
import { Navbar } from './components/Navbar.js';
import { DashboardView } from './components/DashboardView.js';
import { CityExplorerView } from './components/CityExplorerView.js';
import { ForecastingView } from './components/ForecastingView.js';
import { QAOAOptimizationView } from './components/QAOAOptimizationView.js';
import { SimulationView } from './components/SimulationView.js';
import { WeatherView } from './components/WeatherView.js';
import { AuthModal } from './components/AuthModal.js';
import { Activity, ShieldCheck, Zap } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [cities, setCities] = useState<City[]>([]);
  const [selectedCity, setSelectedCity] = useState<City | null>(null);
  const [overview, setOverview] = useState<NationalOverview | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [authOpen, setAuthOpen] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  const loadTelemetry = () => {
    Promise.all([
      api.getCities(),
      api.getNationalOverview()
    ])
      .then(([cRes, oRes]) => {
        setCities(cRes);
        setOverview(oRes);
        setSelectedCity(prev => prev ?? (cRes.length > 0 ? cRes[0] : null));
      })
      .catch(err => {
        console.error('Failed to load Digital Twin telemetry:', err);
      });
  };

  useEffect(() => {
    let isMounted = true;
    const token = localStorage.getItem('smartgrid_token');

    if (!token) {
      // No session at all — require login before fetching any protected
      // data. The real backend correctly rejects unauthenticated calls to
      // /cities, /dashboard/overview, and /auth/me (require_any_authenticated_role),
      // so there is nothing honest to show until someone signs in.
      if (isMounted) {
        setAuthOpen(true);
        setLoading(false);
      }
      return;
    }

    // A token exists in storage — validate it before trusting it.
    api.getMe()
      .then(u => {
        if (!isMounted) return;
        setUser(u);
        loadTelemetry();
        setLoading(false);
      })
      .catch(() => {
        // Stale/expired/invalid token — clear it and require a fresh login.
        api.logout();
        if (isMounted) {
          setAuthOpen(true);
          setLoading(false);
        }
      });

    return () => { isMounted = false; };
  }, []);

  const handleUserUpdate = (u: User) => {
    setUser(u);
    loadTelemetry();
  };

  const handleLogout = () => {
    api.logout();
    setUser(null);
    setCities([]);
    setOverview(null);
    setSelectedCity(null);
    setAuthOpen(true);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
        <div className="flex items-center gap-3 text-cyan-400 mb-2">
          <Activity className="h-8 w-8 animate-spin" />
          <span className="text-xl font-extrabold tracking-tight">SmartGrid Digital Twin</span>
        </div>
        <p className="text-xs text-slate-400 font-mono">Initializing National Telemetry & QAOA Solver...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200">

      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        cities={cities}
        selectedCity={selectedCity}
        setSelectedCity={setSelectedCity}
        user={user}
        onOpenAuth={() => setAuthOpen(true)}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {!user ? (
          <div className="flex flex-col items-center justify-center py-24 text-center gap-3">
            <ShieldCheck className="h-10 w-10 text-cyan-400" />
            <p className="text-slate-300 font-semibold">Sign in to view live grid telemetry.</p>
            <button
              onClick={() => setAuthOpen(true)}
              className="mt-2 px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold"
            >
              Sign In
            </button>
          </div>
        ) : (
          <>
            {activeTab === 'dashboard' && (
              <DashboardView
                overview={overview}
                cities={cities}
                onSelectCity={(city) => setSelectedCity(city)}
                onNavigateTab={(tab) => setActiveTab(tab)}
              />
            )}
            {activeTab === 'explorer' && selectedCity && (
              <CityExplorerView city={selectedCity} />
            )}
            {activeTab === 'forecast' && selectedCity && (
              <ForecastingView selectedCity={selectedCity} />
            )}
            {activeTab === 'qaoa' && selectedCity && (
              <QAOAOptimizationView selectedCity={selectedCity} />
            )}
            {activeTab === 'scenarios' && selectedCity && (
              <SimulationView selectedCity={selectedCity} />
            )}
            {activeTab === 'weather' && selectedCity && (
              <WeatherView selectedCity={selectedCity} />
            )}
          </>
        )}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-cyan-400" />
            <span className="font-semibold text-slate-300">Indian Smart Grid Digital Twin</span>
            <span className="text-slate-600">•</span>
            <span>LSTM Forecasting & QAOA Hybrid Optimization</span>
          </div>
          <div className="flex items-center gap-4 font-mono">
            <span>Backend: <span className="text-emerald-400">FastAPI :8000</span></span>
            <span>Status: <span className="text-cyan-400">Live</span></span>
          </div>
        </div>
      </footer>

      <AuthModal
        isOpen={authOpen}
        onClose={() => setAuthOpen(false)}
        onUserUpdate={handleUserUpdate}
      />

    </div>
  );
}
export default App;
