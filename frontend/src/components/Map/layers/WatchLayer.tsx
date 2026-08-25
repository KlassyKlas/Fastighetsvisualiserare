import { useMemo } from 'react';
import { Layer, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';
import type { Feature, FeatureCollection, LineString, Point, Polygon } from 'geojson';

import { WATCH_COLOR } from '@/config/map';
import type { WatchedAreaCollection } from '@/domain';

interface Props {
  data: WatchedAreaCollection;
  visible: boolean;
}

const fillLayer: LayerProps = {
  id: 'watch-fills',
  type: 'fill',
  paint: {
    'fill-color': WATCH_COLOR,
    'fill-opacity': 0.06,
  },
};

const lineLayer: LayerProps = {
  id: 'watch-borders',
  type: 'line',
  paint: {
    'line-color': WATCH_COLOR,
    'line-width': 2,
    'line-opacity': 0.8,
    'line-dasharray': [3, 2],
  },
};

const labelLayer: LayerProps = {
  id: 'watch-labels',
  type: 'symbol',
  layout: {
    'text-field': ['get', 'name'],
    'text-size': 12,
    'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
  },
  paint: {
    'text-color': WATCH_COLOR,
    'text-halo-color': '#0f172a',
    'text-halo-width': 1.5,
  },
};

/** Sparade bevakningsområden: streckad kant, svag fyllnad och namnetikett. */
export default function WatchLayer({ data, visible }: Props) {
  if (!visible || data.features.length === 0) return null;

  return (
    <Source id="watch-source" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...lineLayer} />
      <Layer {...labelLayer} />
    </Source>
  );
}

const draftLineLayer: LayerProps = {
  id: 'watch-draft-line',
  type: 'line',
  filter: ['==', ['geometry-type'], 'LineString'],
  paint: {
    'line-color': WATCH_COLOR,
    'line-width': 2,
    'line-dasharray': [2, 2],
  },
};

const draftFillLayer: LayerProps = {
  id: 'watch-draft-fill',
  type: 'fill',
  filter: ['==', ['geometry-type'], 'Polygon'],
  paint: {
    'fill-color': WATCH_COLOR,
    'fill-opacity': 0.12,
  },
};

const draftPointLayer: LayerProps = {
  id: 'watch-draft-points',
  type: 'circle',
  filter: ['==', ['geometry-type'], 'Point'],
  paint: {
    'circle-radius': 5,
    'circle-color': WATCH_COLOR,
    'circle-stroke-color': '#0f172a',
    'circle-stroke-width': 1.5,
  },
};

/** Området under ritning: hörnpunkter, kantlinje och förhandsfyllnad. */
export function WatchDraftLayer({ points }: { points: [number, number][] }) {
  const data = useMemo<FeatureCollection>(() => {
    const features: Feature[] = points.map((point) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: point } satisfies Point,
      properties: {},
    }));
    if (points.length >= 2) {
      features.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: points } satisfies LineString,
        properties: {},
      });
    }
    if (points.length >= 3) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [[...points, points[0]]],
        } satisfies Polygon,
        properties: {},
      });
    }
    return { type: 'FeatureCollection', features };
  }, [points]);

  if (points.length === 0) return null;

  return (
    <Source id="watch-draft-source" type="geojson" data={data}>
      <Layer {...draftFillLayer} />
      <Layer {...draftLineLayer} />
      <Layer {...draftPointLayer} />
    </Source>
  );
}
