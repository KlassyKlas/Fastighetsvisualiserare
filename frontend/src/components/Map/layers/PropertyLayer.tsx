import { Source, Layer } from 'react-map-gl';
import type { FeatureCollection } from 'geojson';
import type { LayerProps } from 'react-map-gl';

interface Props {
  data: FeatureCollection;
  visible: boolean;
}

const fillLayer: LayerProps = {
  id: 'property-fills',
  type: 'fill',
  paint: {
    'fill-color': [
      'match',
      ['get', 'property_type'],
      'bostad', '#14b8a6',
      'kontor', '#a855f7',
      'handel', '#f97316',
      'industri', '#ef4444',
      'utbildning', '#06b6d4',
      'villa', '#84cc16',
      '#6b7280',
    ],
    'fill-opacity': 0.5,
  },
};

const borderLayer: LayerProps = {
  id: 'property-borders',
  type: 'line',
  paint: {
    'line-color': '#ffffff',
    'line-width': 1,
    'line-opacity': 0.6,
  },
};

const labelLayer: LayerProps = {
  id: 'property-labels',
  type: 'symbol',
  minzoom: 14,
  layout: {
    'text-field': ['get', 'designation'],
    'text-size': 10,
    'text-anchor': 'center',
    'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
  },
  paint: {
    'text-color': '#e2e8f0',
    'text-halo-color': '#0f172a',
    'text-halo-width': 1,
  },
};

export default function PropertyLayer({ data, visible }: Props) {
  if (!visible || !data || !data.features.length) return null;

  return (
    <Source id="property-source" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...borderLayer} />
      <Layer {...labelLayer} />
    </Source>
  );
}
