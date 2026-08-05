import { Source, Layer } from 'react-map-gl';
import type { FeatureCollection } from 'geojson';
import type { LayerProps } from 'react-map-gl';

interface Props {
  data: FeatureCollection;
  visible: boolean;
}

const circleLayer: LayerProps = {
  id: 'infrastructure-circles',
  type: 'circle',
  paint: {
    'circle-radius': [
      'interpolate',
      ['linear'],
      ['zoom'],
      5, ['interpolate', ['linear'], ['coalesce', ['get', 'budget_sek'], 1000000000], 0, 4, 100000000000, 8],
      12, ['interpolate', ['linear'], ['coalesce', ['get', 'budget_sek'], 1000000000], 0, 8, 100000000000, 20],
      16, ['interpolate', ['linear'], ['coalesce', ['get', 'budget_sek'], 1000000000], 0, 14, 100000000000, 32],
    ],
    'circle-color': [
      'match',
      ['get', 'status'],
      'planerad', '#f59e0b',
      'pågående', '#3b82f6',
      'avslutad', '#22c55e',
      '#6b7280',
    ],
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
  if (!visible || !data || !data.features.length) return null;

  return (
    <Source id="infrastructure-source" type="geojson" data={data}>
      <Layer {...circleLayer} />
      <Layer {...labelLayer} />
    </Source>
  );
}
