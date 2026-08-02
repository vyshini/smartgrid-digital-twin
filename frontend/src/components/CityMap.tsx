import { Paper, Typography } from '@mui/material';
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet';
import type { City } from '../core/types';

interface CityMapProps {
  cities: City[];
  selectedCityId: number | null;
  onSelect: (cityId: number) => void;
}

export function CityMap({ cities, selectedCityId, onSelect }: CityMapProps) {
  return (
    <Paper sx={{ p: 1.5, height: 460 }}>
      <Typography variant="subtitle1" sx={{ px: 1, pb: 1 }}>
        India Smart Grid Nodes
      </Typography>
      <MapContainer center={[22.5, 79]} zoom={5} style={{ height: '400px', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {cities.map((city) => (
          <CircleMarker
            key={city.id}
            center={[city.latitude, city.longitude]}
            radius={selectedCityId === city.id ? 10 : 7}
            pathOptions={{
              color: selectedCityId === city.id ? '#5DFFBC' : '#30C3FF',
              fillOpacity: 0.88,
            }}
            eventHandlers={{ click: () => onSelect(city.id) }}
          >
            <Tooltip>
              <strong>{city.name}</strong>
              <br />
              {city.state}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </Paper>
  );
}
