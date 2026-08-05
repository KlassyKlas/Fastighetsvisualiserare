import { useMemo } from 'react';
import { Source, Layer } from 'react-map-gl';
import type { LayerProps } from 'react-map-gl';
import * as turf from '@turf/turf';
import type { FeatureCollection, Feature } from 'geojson';

interface Props {
  data: FeatureCollection;
  visible: boolean;
}

const fillLayer: LayerProps = {
  id: 'impact-zone-fills',
  type: 'fill',
  paint: {
    'fill-color': [
      'match',
      ['get', 'status'],
      'planerad', '#f59e0b',
      'pågående', '#3b82f6',
      'avslutad', '#22c55e',
      '#6b7280',
    ],
    'fill-opacity': 0.08,
  },
};

const lineLayer: LayerProps = {
  id: 'impact-zone-borders',
  type: 'line',
  paint: {
    'line-color': [
      'match',
      ['get', 'status'],
      'planerad', '#f59e0b',
      'pågående', '#3b82f6',
      'avslutad', '#22c55e',
      '#6b7280',
    ],
    'line-width': 1.5,
    'line-opacity': 0.4,
    'line-dasharray': [4, 2],
  },
};

export default function ImpactZoneLayer({ data, visible }: Props) {
  const bufferedData = useMemo<FeatureCollection>(() => {
    if (!data || !data.features.length) {
      return { type: 'FeatureCollection', features: [] };
    }

    const bufferedFeatures: Feature[] = [];

    for (const feature of data.features) {
      const radiusM = feature.properties?.impact_radius_m;
      if (!radiusM || feature.geometry.type !== 'Point') continue;

      try {
        const buffered = turf.buffer(feature, radiusM / 1000, {
          units: 'kilometers',
        });
        if (buffered) {
          buffered.properties = {
            ...feature.properties,
          };
          bufferedFeatures.push(buffered as Feature);
        }
      } catch {
        // Skip features that can't be buffered
      }
    }

    return {
      type: 'FeatureCollection',
      features: bufferedFeatures,
    };
  }, [data]);

  if (!visible || !bufferedData.features.length) return null;

  return (
    <Source id="impact-zone-source" type="geojson" data={bufferedData}>
      <Layer {...fillLayer} />
      <Layer {...lineLayer} />
    </Source>
  );
}
