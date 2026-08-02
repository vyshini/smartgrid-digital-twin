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
import { useMutation, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { apiClient } from '../lib/apiClient';

export function SimulationPage() {
  const [cityId, setCityId] = useState(1);
  const [weatherScenario, setWeatherScenario] = useState('');
  const [generationScenario, setGenerationScenario] = useState('');
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().slice(0, 10));
  const [scenarioResult, setScenarioResult] = useState<Record<string, unknown> | null>(null);

  const citiesQuery = useQuery({ queryKey: ['cities'], queryFn: apiClient.listCities });
  const weatherScenarioQuery = useQuery({
    queryKey: ['simulation', 'weather-scenarios'],
    queryFn: apiClient.listWeatherScenarios,
  });
  const generationScenarioQuery = useQuery({
    queryKey: ['simulation', 'generation-scenarios', cityId],
    queryFn: () => apiClient.listGenerationScenarios(cityId),
    enabled: Boolean(cityId),
  });

  const selectedCityName = useMemo(
    () => citiesQuery.data?.find((c) => c.id === cityId)?.name ?? '',
    [citiesQuery.data, cityId],
  );

  const filteredWeatherScenarios = useMemo(
    () => (weatherScenarioQuery.data ?? []).filter((s) => s.city === selectedCityName),
    [weatherScenarioQuery.data, selectedCityName],
  );
  const filteredGenerationScenarios = useMemo(
    () => (generationScenarioQuery.data ?? []).filter((s) => s.city === selectedCityName),
    [generationScenarioQuery.data, selectedCityName],
  );

  const runWeatherMutation = useMutation({
    mutationFn: () => apiClient.runWeatherScenario(weatherScenario, asOfDate),
    onSuccess: (data) => setScenarioResult(data),
  });
  const runGenerationMutation = useMutation({
    mutationFn: () => apiClient.runGenerationScenario(cityId, generationScenario, asOfDate),
    onSuccess: (data) => setScenarioResult(data),
  });

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">Smart Grid Simulation Scenarios</Typography>
      <Paper sx={{ p: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel id="sim-city-label">City</InputLabel>
              <Select
                labelId="sim-city-label"
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
              label="Scenario Date"
              type="date"
              value={asOfDate}
              slotProps={{ inputLabel: { shrink: true } }}
              onChange={(e) => setAsOfDate(e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel id="weather-scenario-label">Weather Scenario</InputLabel>
              <Select
                labelId="weather-scenario-label"
                value={weatherScenario}
                label="Weather Scenario"
                onChange={(e) => setWeatherScenario(e.target.value)}
              >
                {filteredWeatherScenarios.map((scenario) => (
                  <MenuItem key={scenario.key} value={scenario.key}>
                    {scenario.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Button
              fullWidth
              variant="contained"
              disabled={!weatherScenario || runWeatherMutation.isPending}
              sx={{ height: '100%' }}
              onClick={() => runWeatherMutation.mutate()}
            >
              Run Weather Simulation
            </Button>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth>
              <InputLabel id="generation-scenario-label">Generation Scenario</InputLabel>
              <Select
                labelId="generation-scenario-label"
                value={generationScenario}
                label="Generation Scenario"
                onChange={(e) => setGenerationScenario(e.target.value)}
              >
                {filteredGenerationScenarios.map((scenario) => (
                  <MenuItem key={scenario.key} value={scenario.key}>
                    {scenario.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <Button
              fullWidth
              variant="outlined"
              disabled={!generationScenario || runGenerationMutation.isPending}
              onClick={() => runGenerationMutation.mutate()}
            >
              Run Capacity Disruption Simulation
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {runWeatherMutation.isError || runGenerationMutation.isError ? (
        <Alert severity="error">Scenario execution failed. Verify role permissions and date validity.</Alert>
      ) : null}

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>
          Forecast / Optimization Impact
        </Typography>
        {scenarioResult ? (
          <pre className="json-pre">{JSON.stringify(scenarioResult, null, 2)}</pre>
        ) : (
          <Typography color="text.secondary">
            Select a city and run a weather or generation scenario to inspect the digital twin response.
          </Typography>
        )}
      </Paper>
    </Stack>
  );
}
