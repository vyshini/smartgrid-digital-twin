import { Alert, Grid, Paper, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, CartesianGrid, Tooltip, XAxis, YAxis, ResponsiveContainer } from 'recharts';
import { MetricCard } from '../components/MetricCard';
import { apiClient } from '../lib/apiClient';
import { formatMw, formatPct } from '../lib/format';

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: apiClient.getNationalOverview,
  });

  if (isLoading) {
    return <Typography>Loading national overview...</Typography>;
  }
  if (error || !data) {
    return <Alert severity="error">Failed to load dashboard overview.</Alert>;
  }

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">National Grid Overview</Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 3 }}>
          <MetricCard title="Tomorrow Prediction" value={formatMw(data.national_forecast_demand_mw)} />
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <MetricCard title="Optimization Score" value={formatPct(data.avg_optimization_score)} />
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <MetricCard title="Renewable Utilization" value={formatPct(data.avg_renewable_pct)} />
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <MetricCard title="CO2 Reduction" value={formatPct(data.avg_co2_reduction_pct)} />
        </Grid>
      </Grid>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>
          City-wise Forecast & Optimization
        </Typography>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data.cities}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="city_name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="latest_forecast_mw" fill="#30C3FF" name="Forecast (MW)" />
            <Bar dataKey="latest_optimization_score" fill="#5DFFBC" name="Optimization Score" />
          </BarChart>
        </ResponsiveContainer>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>
          System Alerts
        </Typography>
        <Stack spacing={1}>
          {data.system_alerts.length ? (
            data.system_alerts.map((alert) => (
              <Alert key={alert} severity={alert.includes('low') ? 'warning' : 'info'}>
                {alert}
              </Alert>
            ))
          ) : (
            <Alert severity="success">No active system alerts.</Alert>
          )}
        </Stack>
      </Paper>
    </Stack>
  );
}
