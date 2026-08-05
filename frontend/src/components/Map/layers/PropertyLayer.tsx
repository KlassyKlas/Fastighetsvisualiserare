import { Layer, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { matchColorExpression, PROPERTY_TYPE_COLORS } from '@/config/map';
import type { PropertyCollection } from '@/domain';

interface Props {
  data: PropertyCollection;
  visible: boolean;
}

const fillLayer: LayerProps = {
  id: 'property-fills',
  type: 'fill',
  paint: {
    'fill-color': matchColorExpression('property_type', PROPERTY_TYPE_COLORS),
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
  if (!visible || data.features.length === 0) return null;

  return (
    <Source id="property-source" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...borderLayer} />
      <Layer {...labelLayer} />
    </Source>
  );
}
