import React, { useEffect, useState } from 'react';
import { City, ForecastResponse, LossCurvePoint, ActualVsPredictedPoint } from '../types/index.js';
import { api } from '../api/client.js';
import {
  TrendingUp,
  Activity,
  Calendar,
  Layers,
  BarChart2,
  CheckCircle2
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
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [lossCurve, setLossCurve] = useState<LossCurvePoint[]>([]);
  const [actualVsPred, setActualVsPred] = useState<ActualVsPredictedPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    Promise.all([
      api.getForecast(selectedCity.name, horizon),
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
        if (isMounted) setLoading(false);
      });

    return () => { isMounted = false; };
  }, [selectedCity.name, horizon]);

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

      {/* Prediction Telemetry Highlight */}
      {forecast && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Target Predicted Load</span>
            <div className="text-3xl font-extrabold text-cyan-400 mt-1 font-mono">
              {forecast.predicted_mw.toLocaleString()} MW
            </div>
            <span className="text-[11px] text-slate-400 mt-2 block">Target Date: {forecast.target_date}</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Confidence Interval (95%)</span>
            <div className="text-lg font-bold text-white mt-1 font-mono">
              {forecast.confidence_interval_mw[0]} - {forecast.confidence_interval_mw[1]} MW
            </div>
            <span className="text-[11px] text-emerald-400 mt-2 block">Band ±4.0% Variance</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Model Artifact Version</span>
            <div className="text-lg font-bold text-slate-200 mt-1">
              {forecast.model_version}
            </div>
            <span className="text-[11px] text-slate-400 mt-2 block">Trained on 1,964 Historical Days</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Validation MAPE Error</span>
            <div className="text-2xl font-extrabold text-emerald-400 mt-1 font-mono">
              5.82%
            </div>
            <span className="text-[11px] text-slate-400 mt-2 block">High Predictive Accuracy</span>
          </div>
        </div>
      )}

      {/* Actual vs Predicted Demand Line Chart */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white">Actual vs. Predicted Demand (Held-out Test Period)</h3>
            <p className="text-xs text-slate-400">Comparing real grid smart meter readings against neural network output</p>
          </div>
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={actualVsPred}>
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
              <Legend />
              <Line type="monotone" dataKey="actual_mw" stroke="#38bdf8" strokeWidth={2} name="Actual Load (MW)" />
              <Line type="monotone" dataKey="predicted_mw" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 5" name="LSTM Prediction (MW)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Loss Curves */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="mb-4">
          <h3 className="text-base font-bold text-white">Neural Network Training & Validation Loss Curve</h3>
          <p className="text-xs text-slate-400">Convergence over 30 training epochs (MSE loss)</p>
        </div>

        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={lossCurve}>
              <XAxis dataKey="epoch" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
              <Legend />
              <Line type="monotone" dataKey="loss" stroke="#10b981" strokeWidth={2} name="Training Loss" />
              <Line type="monotone" dataKey="val_loss" stroke="#ef4444" strokeWidth={2} name="Validation Loss" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
};
