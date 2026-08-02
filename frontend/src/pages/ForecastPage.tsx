import {
  Alert,
  Button,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Horizon } from '../core/types';
import { apiClient } from '../lib/apiClient';
import { formatMw } from '../lib/format';

export function ForecastPage() {
  const [city, setCity] = useState('Delhi');
  const [horizon, setHorizon] = useState<Horizon>('next_day');
  const [asOfDate, setAsOfDate] = useState('');
  const [trigger, setTrigger] = useState(0);

  const forecastQuery = useQuery({
    queryKey: ['forecast', city, horizon, asOfDate, trigger],
    queryFn: () => apiClient.predictLoad(city, horizon, asOfDate || undefined),
    enabled: trigger > 0,
  });

  const weatherQuery = useQuery({
    queryKey: ['weather-current', city],
    queryFn: () => apiClient.getWeatherCurrent(city),
  });

  const chartData = useMemo(() => {
    if (!forecastQuery.data) {
      return [];
    }
    return [
      { label: 'Predicted Load', mw: forecastQuery.data.predicted_mw },
      { label: 'Temperature', mw: weatherQuery.data?.temperature_c ?? 0 },
      { label: 'Humidity', mw: weatherQuery.data?.humidity_pct ?? 0 },
    ];
  }, [forecastQuery.data, weatherQuery.data]);

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">LSTM Forecasting Console</Typography>
      <Paper sx={{ p: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel id="city-select-label">City</InputLabel>
              <Select labelId="city-select-label" value={city} label="City" onChange={(e) => setCity(e.target.value)}>
                {['Delhi', 'Mumbai', 'Bangalore', 'Hyderabad', 'Chennai', 'Kolkata', 'Ahmedabad', 'Pune'].map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel id="horizon-select-label">Horizon</InputLabel>
              <Select
                labelId="horizon-select-label"
                value={horizon}
                label="Horizon"
                onChange={(e) => setHorizon(e.target.value as Horizon)}
              >
                <MenuItem value="next_day">Next Day</MenuItem>
                <MenuItem value="next_week">Next Week</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <TextField
              fullWidth
              label="As Of Date"
              type="date"
              value={asOfDate}
              slotProps={{ inputLabel: { shrink: true } }}
              onChange={(e) => setAsOfDate(e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Button variant="contained" fullWidth sx={{ height: '100%' }} onClick={() => setTrigger((v) => v + 1)}>
              Run Forecast
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {forecastQuery.error ? <Alert severity="error">Forecast request failed for selected city/date.</Alert> : null}

      {forecastQuery.data ? (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Predicted Load
              </Typography>
              <Typography variant="h4">{formatMw(forecastQuery.data.predicted_mw)}</Typography>
              <Typography variant="body2" color="text.secondary">
                {forecastQuery.data.city} • Target {forecastQuery.data.target_date}
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                Forecast Drivers Snapshot
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="mw" stroke="#30C3FF" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>
        </Grid>
      ) : null}
    </Stack>
  );
}
