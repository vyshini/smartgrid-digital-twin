import React, { useEffect, useState } from 'react';
import { City } from '../types/index.js';
import { api } from '../api/client.js';
import {
  CloudSun,
  Thermometer,
  Droplets,
  Wind,
  Sun,
  CloudRain,
  Activity
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

interface WeatherViewProps {
  selectedCity: City;
}

export const WeatherView: React.FC<WeatherViewProps> = ({ selectedCity }) => {
  const [currentWeather, setCurrentWeather] = useState<any>(null);
  const [weatherHistory, setWeatherHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    Promise.all([
      api.getCurrentWeather(selectedCity.name),
      api.getWeatherHistory(selectedCity.name, 14)
    ])
      .then(([cRes, hRes]) => {
        if (isMounted) {
          setCurrentWeather(cRes);
          setWeatherHistory(hRes);
          setLoading(false);
        }
      })
      .catch(err => {
        console.error(err);
        if (isMounted) setLoading(false);
      });

    return () => { isMounted = false; };
  }, [selectedCity.name]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex items-center gap-3 text-cyan-400">
          <Activity className="h-6 w-6 animate-spin" />
          <span className="font-semibold text-slate-300">Fetching Weather Station Telemetry...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      
      {/* Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <CloudSun className="h-6 w-6 text-amber-400" />
            <h1 className="text-2xl font-extrabold text-white">{selectedCity.name} Weather Station Telemetry</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Sourced from per-city meteorological recordings feeding the LSTM load prediction features.
          </p>
        </div>
      </div>

      {/* Current Readings Row */}
      {currentWeather && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          
          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider">Temperature</span>
              <Thermometer className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-2xl font-extrabold text-white font-mono">
              {currentWeather.temperature_c}°C
            </div>
            <span className="text-[11px] text-slate-400 mt-1 block">Ambient temperature</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider">Relative Humidity</span>
              <Droplets className="h-4 w-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-extrabold text-cyan-400 font-mono">
              {currentWeather.humidity_pct}%
            </div>
            <span className="text-[11px] text-slate-400 mt-1 block">Moisture index</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider">Wind Speed</span>
              <Wind className="h-4 w-4 text-teal-400" />
            </div>
            <div className="text-2xl font-extrabold text-teal-300 font-mono">
              {currentWeather.wind_speed_kmph} km/h
            </div>
            <span className="text-[11px] text-slate-400 mt-1 block">Coastal & inland vector</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider">Solar Irradiance</span>
              <Sun className="h-4 w-4 text-yellow-400" />
            </div>
            <div className="text-2xl font-extrabold text-yellow-400 font-mono">
              {currentWeather.solar_irradiance} W/m²
            </div>
            <span className="text-[11px] text-slate-400 mt-1 block">PV array input power</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-lg">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider">Precipitation</span>
              <CloudRain className="h-4 w-4 text-blue-400" />
            </div>
            <div className="text-2xl font-extrabold text-blue-300 font-mono">
              {currentWeather.precipitation_mm} mm
            </div>
            <span className="text-[11px] text-slate-400 mt-1 block">Rainfall accumulation</span>
          </div>

        </div>
      )}

      {/* Weather History Chart */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="mb-4">
          <h3 className="text-base font-bold text-white">14-Day Temperature & Solar Irradiance Trends</h3>
          <p className="text-xs text-slate-400">Primary exogenous features used by the LSTM load forecaster</p>
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={weatherHistory}>
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
              <Legend />
              <Line type="monotone" dataKey="temperature_c" stroke="#f59e0b" strokeWidth={2} name="Temperature (°C)" />
              <Line type="monotone" dataKey="solar_irradiance" stroke="#06b6d4" strokeWidth={2} name="Solar Irradiance (W/m²)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
};
