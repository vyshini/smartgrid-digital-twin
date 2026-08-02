import { Alert, Button, Grid, Paper, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../lib/apiClient';
import { downloadCsv } from '../lib/download';

export function ReportsPage() {
  const citiesQuery = useQuery({ queryKey: ['cities'], queryFn: apiClient.listCities });
  const overviewQuery = useQuery({ queryKey: ['dashboard', 'overview'], queryFn: apiClient.getNationalOverview });

  const selectedCity = citiesQuery.data?.[0];
  const optimizationQuery = useQuery({
    queryKey: ['report', 'optimization-history', selectedCity?.id],
    queryFn: () => apiClient.getOptimizationHistory(selectedCity!.id),
    enabled: Boolean(selectedCity?.id),
  });
  const simulationHistoryQuery = useQuery({
    queryKey: ['report', 'simulation-history', selectedCity?.id],
    queryFn: () => apiClient.getSimulationHistory(selectedCity!.id),
    enabled: Boolean(selectedCity?.id),
  });

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">Operational Reports</Typography>
      <Alert severity="info">
        Backend report-generation endpoints are pending; this console exports production data snapshots directly as CSV.
      </Alert>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              National Forecast & Optimization Report
            </Typography>
            <Button
              fullWidth
              variant="contained"
              disabled={!overviewQuery.data}
              onClick={() =>
                downloadCsv(
                  'national_overview_report.csv',
                  (overviewQuery.data?.cities ?? []).map((city) => ({
                    city: city.city_name,
                    forecast_mw: city.latest_forecast_mw,
                    optimization_score: city.latest_optimization_score,
                    grid_stability_score: city.grid_stability_score,
                    renewable_pct: city.renewable_pct,
                    co2_reduction_pct: city.co2_reduction_pct,
                  })),
                )
              }
            >
              Export CSV
            </Button>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              City Optimization Report ({selectedCity?.name ?? 'N/A'})
            </Typography>
            <Button
              fullWidth
              variant="contained"
              disabled={!optimizationQuery.data}
              onClick={() =>
                downloadCsv(
                  'city_optimization_report.csv',
                  (optimizationQuery.data ?? []).map((row) => ({
                    run_id: row.id,
                    run_at: row.run_at,
                    optimization_score: row.optimization_score,
                    cost_reduction_pct: row.cost_reduction_pct,
                    power_loss_reduction_pct: row.power_loss_reduction_pct,
                    grid_stability_score: row.grid_stability_score,
                    target_demand_mw: row.allocation_result.target_demand_mw,
                    total_supply_mw: row.allocation_result.total_supply_mw,
                  })),
                )
              }
            >
              Export CSV
            </Button>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              Simulation Scenario Report ({selectedCity?.name ?? 'N/A'})
            </Typography>
            <Button
              fullWidth
              variant="contained"
              disabled={!simulationHistoryQuery.data}
              onClick={() =>
                downloadCsv(
                  'simulation_history_report.csv',
                  (simulationHistoryQuery.data ?? []).map((row) => ({
                    scenario_type: row.scenario_type,
                    scenario_name: row.scenario_name,
                    as_of_date: row.as_of_date,
                    run_at: row.run_at,
                    result: JSON.stringify(row.result),
                  })),
                )
              }
            >
              Export CSV
            </Button>
          </Paper>
        </Grid>
      </Grid>
    </Stack>
  );
}
