import {
  Alert,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Horizon } from '../core/types';
import { apiClient } from '../lib/apiClient';

export function AnalyticsPage() {
  const [city, setCity] = useState('Delhi');
  const [horizon, setHorizon] = useState<Horizon>('next_day');

  const lossQuery = useQuery({
    queryKey: ['analytics', 'loss', city],
    queryFn: () => apiClient.getLossCurve(city),
  });
  const actualVsPredictedQuery = useQuery({
    queryKey: ['analytics', 'avp', city, horizon],
    queryFn: () => apiClient.getActualVsPredicted(city, horizon),
  });

  const lastEpochSummary = useMemo(() => {
    if (!lossQuery.data || lossQuery.data.length === 0) {
      return null;
    }
    return lossQuery.data[lossQuery.data.length - 1];
  }, [lossQuery.data]);

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">Forecast Analytics & Accuracy</Typography>
      <Paper sx={{ p: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <FormControl fullWidth>
              <InputLabel id="analytics-city-label">City</InputLabel>
              <Select
                labelId="analytics-city-label"
                value={city}
                label="City"
                onChange={(e) => setCity(e.target.value)}
              >
                {['Delhi', 'Mumbai', 'Bangalore', 'Hyderabad', 'Chennai', 'Kolkata', 'Ahmedabad', 'Pune'].map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <FormControl fullWidth>
              <InputLabel id="analytics-horizon-label">Horizon</InputLabel>
              <Select
                labelId="analytics-horizon-label"
                value={horizon}
                label="Horizon"
                onChange={(e) => setHorizon(e.target.value as Horizon)}
              >
                <MenuItem value="next_day">Next Day</MenuItem>
                <MenuItem value="next_week">Next Week</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      {lossQuery.error || actualVsPredictedQuery.error ? (
        <Alert severity="error">Analytics data unavailable for selected city/model version.</Alert>
      ) : null}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              Loss Curve (Training vs Validation)
            </Typography>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={lossQuery.data ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="epoch" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="loss" stroke="#30C3FF" dot={false} />
                <Line type="monotone" dataKey="val_loss" stroke="#5DFFBC" dot={false} />
              </LineChart>
            </ResponsiveContainer>
            {lastEpochSummary ? (
              <Typography variant="body2" color="text.secondary">
                Final Epoch {lastEpochSummary.epoch}: loss={lastEpochSummary.loss.toFixed(4)}, val_loss=
                {lastEpochSummary.val_loss.toFixed(4)}
              </Typography>
            ) : null}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              Actual vs Predicted Demand
            </Typography>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={actualVsPredictedQuery.data ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="actual_mw" stroke="#FFB74D" dot={false} />
                <Line type="monotone" dataKey="predicted_mw" stroke="#30C3FF" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
      </Grid>
    </Stack>
  );
}
