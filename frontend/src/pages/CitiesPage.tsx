import {
  Alert,
  Chip,
  Grid,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { CityMap } from '../components/CityMap';
import { useAppDispatch } from '../hooks/useAppDispatch';
import { useAppSelector } from '../hooks/useAppSelector';
import { apiClient } from '../lib/apiClient';
import { formatMw, formatNumber, formatPct } from '../lib/format';
import { setSelectedCityId } from '../store/uiSlice';

export function CitiesPage() {
  const selectedCityId = useAppSelector((s) => s.ui.selectedCityId);
  const dispatch = useAppDispatch();

  const citiesQuery = useQuery({
    queryKey: ['cities'],
    queryFn: apiClient.listCities,
  });

  const cityDetailQuery = useQuery({
    queryKey: ['city', selectedCityId],
    queryFn: () => apiClient.getCity(selectedCityId as number),
    enabled: Boolean(selectedCityId),
  });

  if (citiesQuery.isLoading) {
    return <Typography>Loading city nodes...</Typography>;
  }
  if (citiesQuery.error || !citiesQuery.data) {
    return <Alert severity="error">Unable to load city registry.</Alert>;
  }

  const selectedCity = selectedCityId
    ? citiesQuery.data.find((city) => city.id === selectedCityId) ?? null
    : null;

  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12, lg: 8 }}>
        <CityMap
          cities={citiesQuery.data}
          selectedCityId={selectedCityId}
          onSelect={(cityId) => dispatch(setSelectedCityId(cityId))}
        />
      </Grid>
      <Grid size={{ xs: 12, lg: 4 }}>
        <Paper sx={{ p: 2, mb: 2, maxHeight: 220, overflow: 'auto' }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Interconnected City Nodes
          </Typography>
          <List dense>
            {citiesQuery.data.map((city) => (
              <ListItemButton
                key={city.id}
                selected={selectedCityId === city.id}
                onClick={() => dispatch(setSelectedCityId(city.id))}
              >
                <ListItemText
                  primary={city.name}
                  secondary={`${city.state} • Population ${formatNumber(city.population)}`}
                />
              </ListItemButton>
            ))}
          </List>
        </Paper>
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            City Digital Twin Snapshot
          </Typography>
          {!selectedCity ? (
            <Typography color="text.secondary">Select a city node to inspect load and grid health.</Typography>
          ) : cityDetailQuery.isLoading ? (
            <Typography>Loading {selectedCity.name}...</Typography>
          ) : cityDetailQuery.error || !cityDetailQuery.data ? (
            <Alert severity="error">Failed to fetch city detail.</Alert>
          ) : (
            <Stack spacing={1.2}>
              <Typography variant="h6">{cityDetailQuery.data.city.name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {cityDetailQuery.data.city.state} • {cityDetailQuery.data.city.timezone}
              </Typography>
              <Typography variant="body2">
                Grid Nodes: {cityDetailQuery.data.grid_nodes.length} • Transmission Lines:{' '}
                {cityDetailQuery.data.transmission_lines.length}
              </Typography>
              {cityDetailQuery.data.grid_nodes.slice(0, 3).map((node) => (
                <Chip
                  key={node.id}
                  label={`${node.node_code}: ${node.status} • Capacity ${formatMw(node.transmission_capacity_mw)}`}
                />
              ))}
              {cityDetailQuery.data.transmission_lines.slice(0, 3).map((line) => (
                <Typography key={line.id} variant="caption" color="text.secondary">
                  Line {line.from_node_id}→{line.to_node_id}: {formatPct(line.utilization_pct)} utilized
                </Typography>
              ))}
            </Stack>
          )}
        </Paper>
      </Grid>
    </Grid>
  );
}
