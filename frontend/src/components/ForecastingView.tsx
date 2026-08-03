import React, { useEffect, useState } from 'react';
import { City, ForecastResponse, LossCurvePoint, ActualVsPredictedPoint } from '../types/index.js';
import { api } from '../api/client.js';
import {
  TrendingUp,
  Activity,
  Calendar
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend
} from 'recharts';

interface ForecastingViewProps {
  selectedCity: City;
}

export const ForecastingView: React.FC<ForecastingViewProps> = ({ selectedCity }) => {
  const [horizon, setHorizon] = useState<'next_day' | 'next_week'>('next_day');
  const [asOfDate, setAsOfDate] = useState<string>('');
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [lossCurve, setLossCurve] = useState<LossCurvePoint[]>([]);
  const [actualVsPred, setActualVsPred] = useState<ActualVsPredictedPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  // The static training dataset ends at a fixed historical date — default
  // to whatever date this city's data actually supports, rather than
  // letting the backend 422 against "today" (see backend's
  // forecast_city_load_use_case.py data-honesty rationale).
  useEffect(() => {
    api.getLatestAvailableDate(selectedCity.name)
      .then(res => setAsOfDate(res.latest_available_date))
      .catch(err => console.error('Failed to fetch latest available date:', err));
  }, [selectedCity.name]);

  useEffect(() => {
    if (!asOfDate) return;
    let isMounted = true;
    setLoading(true);
    setError('');

    Promise.all([
      api.getForecast(selectedCity.name, horizon, asOfDate),
      api.getLossCurve(selectedCity.name),
      api.getActualVsPredicted(selectedCity.name, horizon)
    ])
      .then(([fRes, lRes, aRes]) => {
        if (isMounted) {
          setForecast(fRes);
          setLossCurve(lRes);
          setActualVsPred(aRes);
          setLoading(false);
        }
      })
      .catch(err => {
        console.error(err);
        if (isMounted) {
          setError(err.message || 'Failed to load forecast data');
          setLoading(false);
        }
      });

    return () => { isMounted = false; };
  }, [selectedCity.name, horizon, asOfDate]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <Activity className="h-6 w-6 animate-spin" />
          <span className="font-semibold text-slate-300">Evaluating LSTM Neural Network Models...</span>
        </div>
      </div>
    );
  }

  const epochsRun = lossCurve.length;

  return (
    <div className="space-y-6 pb-12">

      {/* Header & Controls */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-cyan-400" />
            <h1 className="text-2xl font-extrabold text-white">{selectedCity.name} Load Forecasting</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Multi-layer LSTM model evaluating historical load profiles, weather features, and seasonal trends.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* As-Of Date */}
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-2 rounded-xl border border-slate-800">
            <Calendar className="h-4 w-4 text-slate-500" />
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="bg-transparent text-xs font-semibold text-cyan-300 focus:outline-none"
            />
          </div>

          {/* Horizon Toggle */}
          <div className="flex items-center bg-slate-950 p-1.5 rounded-xl border border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setHorizon('next_day')}
              className={`px-4 py-2 rounded-lg transition-all ${
                horizon === 'next_day'
                  ? 'bg-cyan-500 text-slate-950 shadow font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              24h Next-Day
            </button>
            <button
              onClick={() => setHorizon('next_week')}
              className={`px-4 py-2 rounded-lg transition-all ${
                horizon === 'next_week'
                  ? 'bg-cyan-500 text-slate-950 shadow font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              7-Day Next-Week
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Prediction Telemetry Highlight */}
      {forecast && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Target Predicted Load</span>
            <div className="text-3xl font-extrabold text-cyan-400 mt-1 font-mono">
              {forecast.predicted_mw.toLocaleString()} MW
            </div>
            <span className="text-[11px] text-slate-400 mt-2 block">Target Date: {forecast.target_date}</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Confidence Interval</span>
            <div className="text-lg font-bold text-white mt-1 font-mono">
              {forecast.confidence_interval_mw
                ? `${forecast.confidence_interval_mw[0]} - ${forecast.confidence_interval_mw[1]} MW`
                : 'Not available'}
            </div>
            <span className="text-[11px] text-slate-400 mt-2 block">
              {forecast.confidence_interval_mw
                ? 'Calibrated uncertainty band'
                : 'This model reports point forecasts only — no fabricated interval'}
            </span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Model Artifact Version</span>
            <div className="text-lg font-bold text-slate-200 mt-1">
              {forecast.model_version}
            </div>
            <span className="text-[11px] text-slate-400 mt-2 block">As-of {forecast.as_of_date}</span>
          </div>
        </div>
      )}

      {/* Actual vs Predicted Demand Line Chart */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white">Actual vs. Predicted Demand (Held-out Test Period)</h3>
            <p className="text-xs text-slate-400">Real historical demand vs. the trained model's predictions on unseen dates</p>
          </div>
        </div>

        <div className="h-72">
          {actualVsPred.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={actualVsPred}>
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
                <Legend />
                <Line type="monotone" dataKey="actual_mw" stroke="#38bdf8" strokeWidth={2} name="Actual Load (MW)" dot={false} />
                <Line type="monotone" dataKey="predicted_mw" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 5" name="LSTM Prediction (MW)" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-slate-500">No test-period data available for this city/horizon.</div>
          )}
        </div>
      </div>

      {/* Loss Curves */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="mb-4">
          <h3 className="text-base font-bold text-white">Neural Network Training & Validation Loss Curve</h3>
          <p className="text-xs text-slate-400">
            {epochsRun > 0
              ? `Convergence over ${epochsRun} training epochs (MSE loss) — this city's actual EarlyStopping run`
              : 'No training history recorded for the currently-promoted model version'}
          </p>
        </div>

        <div className="h-64">
          {lossCurve.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lossCurve}>
                <XAxis dataKey="epoch" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
                <Legend />
                <Line type="monotone" dataKey="loss" stroke="#10b981" strokeWidth={2} name="Training Loss" dot={false} />
                <Line type="monotone" dataKey="val_loss" stroke="#ef4444" strokeWidth={2} name="Validation Loss" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-slate-500">No loss curve data available.</div>
          )}
        </div>
      </div>

    </div>
  );
};
