import { useMemo } from 'react';
import { Layer, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';
import type { ExpressionSpecification } from 'mapbox-gl';

import { DEMOGRAPHICS_GRADIENT, DEMOGRAPHICS_METRICS } from '@/config/map';
import { metricDomain } from '@/lib/deso';
import type { DemographicsMetric, DesoAreaCollection } from '@/domain';

interface Props {
  data: DesoAreaCollection;
  visible: boolean;
  metric: DemographicsMetric;
}

/**
 * DeSO-choropleth: sekventiell skala mellan kartvyns min och max för
 * vald metrik. Områden utan värde tonas ner i stället för att döljas —
 * "data saknas" är också information.
 */
export default function DesoLayer({ data, visible, metric }: Props) {
  const property = DEMOGRAPHICS_METRICS[metric].property;
  const domain = useMemo(() => metricDomain(data, metric), [data, metric]);

  if (!visible || data.features.length === 0) return null;

  const fillColor: ExpressionSpecification | string = domain
    ? [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', property], domain[0]],
        domain[0],
        DEMOGRAPHICS_GRADIENT.low,
        (domain[0] + domain[1]) / 2,
        DEMOGRAPHICS_GRADIENT.mid,
        domain[1],
        DEMOGRAPHICS_GRADIENT.high,
      ]
    : DEMOGRAPHICS_GRADIENT.mid;

  const fillLayer: LayerProps = {
    id: 'deso-fills',
    type: 'fill',
    paint: {
      'fill-color': fillColor,
      'fill-opacity': [
        'case',
        ['==', ['coalesce', ['get', property], null], null],
        0.06,
        0.35,
      ] as unknown as number,
    },
  };

  const lineLayer: LayerProps = {
    id: 'deso-borders',
    type: 'line',
    paint: {
      'line-color': '#94a3b8',
      'line-width': 0.5,
      'line-opacity': 0.35,
    },
  };

  return (
    <Source id="deso-source" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...lineLayer} />
    </Source>
  );
}
