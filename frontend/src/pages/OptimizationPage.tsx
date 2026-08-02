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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { useEffect, useMemo, useState } from 'react';
import { Pie, PieChart, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { apiClient } from '../lib/apiClient';
import { formatMw, formatPct } from '../lib/format';

export function OptimizationPage() {
  const [cityId, setCityId] = useState<number>(1);
  const [targetDemand, setTargetDemand] = useState('');
  const [forecastDate, setForecastDate] = useState('');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
 

  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  const citiesQuery = useQuery({ queryKey: ['cities'], queryFn: apiClient.listCities });
  const latestQuery = useQuery({
    queryKey: ['optimization', 'latest', cityId],
    queryFn: () => apiClient.getLatestOptimization(cityId),
    retry: false,
  });

  const selectedCityName = useMemo(
    () => citiesQuery.data?.find((c) => c.id === cityId)?.name,
    [citiesQuery.data, cityId],
  );

  const latestDateQuery = useQuery({
    queryKey: ['optimization', 'latest-date', selectedCityName],
    queryFn: () => apiClient.getLatestAvailableDate(selectedCityName as string),
    enabled: Boolean(selectedCityName),
  });

  useEffect(() => {
    if (latestDateQuery.data?.latest_available_date) {
      setForecastDate(latestDateQuery.data.latest_available_date);
    }
  }, [latestDateQuery.data]);


  const explanationQuery = useQuery({
    queryKey: ['optimization', 'explanation', latestQuery.data?.id],
    queryFn: () => apiClient.getOptimizationExplanation(latestQuery.data!.id),
    enabled: Boolean(latestQuery.data?.id),
    retry: false,
  });

  const runMutation = useMutation({
    mutationFn: () =>
      apiClient.runOptimization(cityId, {
        target_demand_mw: targetDemand ? Number(targetDemand) : undefined,
        forecast_as_of_date: forecastDate || undefined,
      }),
    onSuccess: (result) => {
      setActiveJobId(result.job_id);
      enqueueSnackbar('Optimization job started.', { variant: 'info' });
    },
    onError: () => enqueueSnackbar('Unable to start optimization.', { variant: 'error' }),
  });

  const jobQuery = useQuery({
    queryKey: ['optimization', 'job', activeJobId],
    queryFn: () => apiClient.getOptimizationJob(activeJobId as string),
    enabled: Boolean(activeJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' ? 2000 : false;
    },
  });

  useEffect(() => {
    if (jobQuery.data?.status === 'completed' && activeJobId) {
      setActiveJobId(null);
      void queryClient.invalidateQueries({ queryKey: ['optimization', 'latest', cityId] });
      void queryClient.invalidateQueries({ queryKey: ['dashboard', 'overview'] });
    }
  }, [activeJobId, cityId, jobQuery.data?.status, queryClient]);

  const pieData = useMemo(() => {
    const alloc = latestQuery.data?.allocation_result;
    if (!alloc) {
      return [];
    }
    return [
      { name: 'Coal', value: alloc.coal_mw, color: '#FF8A65' },
      { name: 'Hydro', value: alloc.hydro_mw, color: '#4FC3F7' },
      { name: 'Wind', value: alloc.wind_mw, color: '#81C784' },
      { name: 'Solar', value: alloc.solar_mw, color: '#FFD54F' },
      { name: 'Import', value: alloc.import_mw, color: '#CE93D8' },
    ];
  }, [latestQuery.data]);

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">Hybrid Quantum-Classical QAOA Optimization</Typography>
      <Paper sx={{ p: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel id="city-optimization-label">City</InputLabel>
              <Select
                labelId="city-optimization-label"
                value={cityId}
                label="City"
                onChange={(e) => setCityId(Number(e.target.value))}
              >
                {(citiesQuery.data ?? []).map((city) => (
                  <MenuItem key={city.id} value={city.id}>
                    {city.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <TextField
              fullWidth
              label="Target Demand (MW)"
              value={targetDemand}
              onChange={(e) => setTargetDemand(e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <TextField
              fullWidth
              type="date"
              label="Forecast As Of Date"
              value={forecastDate}
              slotProps={{ inputLabel: { shrink: true } }}
              onChange={(e) => setForecastDate(e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Button
              fullWidth
              variant="contained"
              sx={{ height: '100%' }}
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
            >
              {runMutation.isPending ? 'Starting...' : 'Run QAOA'}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {jobQuery.data?.status === 'running' ? <Alert severity="info">Optimization job running...</Alert> : null}
      {jobQuery.data?.status === 'failed' ? (
        <Alert severity="error">Optimization failed: {jobQuery.data.error ?? 'Unknown error'}</Alert>
      ) : null}

      {latestQuery.data ? (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Optimization Score
              </Typography>
              <Typography variant="h4">{formatPct(latestQuery.data.optimization_score)}</Typography>
              <Typography variant="body2">Grid Stability: {formatPct(latestQuery.data.grid_stability_score)}</Typography>
              <Typography variant="body2">Cost Reduction: {formatPct(latestQuery.data.cost_reduction_pct)}</Typography>
              <Typography variant="body2">
                Power Loss Reduction: {formatPct(latestQuery.data.power_loss_reduction_pct)}
              </Typography>
              <Typography variant="body2">Execution: {latestQuery.data.execution_time_ms} ms</Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Paper sx={{ p: 2, height: '100%' }}>
              <Typography variant="subtitle1">Generation Mix Allocation</Typography>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={86}>
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Paper sx={{ p: 2, height: '100%' }}>
              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                Decision Support
              </Typography>
              {explanationQuery.data ? (
                <Stack spacing={1}>
                  <Typography variant="body2">{explanationQuery.data.summary}</Typography>
                  <Typography variant="body2">{explanationQuery.data.expected_savings}</Typography>
                  <Typography variant="body2">
                    Risk Level: <strong>{explanationQuery.data.risk_level.toUpperCase()}</strong>
                  </Typography>
                </Stack>
              ) : (
                <Typography color="text.secondary">No explanation available for current run.</Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      ) : (
        <Alert severity="info">No optimization runs found for this city yet.</Alert>
      )}

      {latestQuery.data ? (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Dispatch Summary
          </Typography>
          <Typography>Target Demand: {formatMw(latestQuery.data.allocation_result.target_demand_mw)}</Typography>
          <Typography>Total Supply: {formatMw(latestQuery.data.allocation_result.total_supply_mw)}</Typography>
          <Typography>Mismatch: {formatMw(latestQuery.data.allocation_result.mismatch_mw)}</Typography>
        </Paper>
      ) : null}
    </Stack>
  );
}
