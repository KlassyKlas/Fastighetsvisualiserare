import { Layer, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { matchColorExpression, STATUS_COLORS } from '@/config/map';
import type { ProjectCollection } from '@/domain';

interface Props {
  data: ProjectCollection;
  visible: boolean;
}

const statusColor = matchColorExpression('status', STATUS_COLORS);

/**
 * Linjeprojekt (vägar, järnvägar) renderas som linjer — den gamla appen
 * visade allt som cirklar och gjorde linjegeometrier oklickbara.
 */
const lineLayer: LayerProps = {
  id: 'infrastructure-lines',
  type: 'line',
  filter: ['==', ['geometry-type'], 'LineString'],
  layout: {
    'line-cap': 'round',
    'line-join': 'round',
  },
  paint: {
    'line-color': statusColor,
    'line-width': ['interpolate', ['linear'], ['zoom'], 5, 2, 10, 3.5, 14, 6],
    'line-opacity': 0.9,
  },
};

const circleLayer: LayerProps = {
  id: 'infrastructure-circles',
  type: 'circle',
  filter: ['==', ['geometry-type'], 'Point'],
  paint: {
    'circle-radius': [
      'interpolate',
      ['linear'],
      ['zoom'],
      5,
      [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', 'budget_sek'], 1000000000],
        0,
        4,
        100000000000,
        8,
      ],
      12,
      [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', 'budget_sek'], 1000000000],
        0,
        8,
        100000000000,
        20,
      ],
      16,
      [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', 'budget_sek'], 1000000000],
        0,
        14,
        100000000000,
        32,
      ],
    ],
    'circle-color': statusColor,
    'circle-stroke-width': 2,
    'circle-stroke-color': 'rgba(255, 255, 255, 0.5)',
    'circle-opacity': 0.85,
  },
};

const labelLayer: LayerProps = {
  id: 'infrastructure-labels',
  type: 'symbol',
  minzoom: 10,
  layout: {
    'text-field': ['get', 'name'],
    'text-size': 11,
    'text-offset': [0, 1.5],
    'text-anchor': 'top',
    'text-max-width': 12,
    'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
  },
  paint: {
    'text-color': '#e2e8f0',
    'text-halo-color': '#0f172a',
    'text-halo-width': 1,
  },
};

export default function InfrastructureLayer({ data, visible }: Props) {
  if (!visible || data.features.length === 0) return null;

  return (
    <Source id="infrastructure-source" type="geojson" data={data}>
      <Layer {...lineLayer} />
      <Layer {...circleLayer} />
      <Layer {...labelLayer} />
    </Source>
  );
}
