import { Layer, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { matchColorExpression, PROPERTY_TYPE_COLORS, SCORE_GRADIENT } from '@/config/map';
import type { PropertyCollection, ProximityScoresCollection } from '@/domain';

interface Props {
  data: PropertyCollection | ProximityScoresCollection;
  visible: boolean;
  /** Färga efter närhetspoäng (kräver att data innehåller score) */
  colorByScore?: boolean;
  maxScore?: number;
}

const typeFillLayer: LayerProps = {
  id: 'property-fills',
  type: 'fill',
  paint: {
    'fill-color': matchColorExpression('property_type', PROPERTY_TYPE_COLORS),
    'fill-opacity': 0.5,
  },
};

function scoreFillLayer(maxScore: number): LayerProps {
  const safeMax = Math.max(maxScore, 1);
  return {
    id: 'property-fills',
    type: 'fill',
    paint: {
      'fill-color': [
        'interpolate',
        ['linear'],
        ['get', 'score'],
        0,
        SCORE_GRADIENT.low,
        safeMax / 2,
        SCORE_GRADIENT.mid,
        safeMax,
        SCORE_GRADIENT.high,
      ],
      'fill-opacity': 0.65,
    },
  };
}

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

export default function PropertyLayer({
  data,
  visible,
  colorByScore = false,
  maxScore = 1,
}: Props) {
  if (!visible || data.features.length === 0) return null;

  const fillLayer = colorByScore ? scoreFillLayer(maxScore) : typeFillLayer;

  return (
    <Source id="property-source" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...borderLayer} />
      <Layer {...labelLayer} />
    </Source>
  );
}
