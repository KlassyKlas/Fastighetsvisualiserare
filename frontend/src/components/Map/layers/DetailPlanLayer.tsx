import { Layer, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { matchColorExpression, PLAN_STATUS_COLORS } from '@/config/map';
import type { DetailPlanCollection } from '@/domain';

interface Props {
  data: DetailPlanCollection;
  visible: boolean;
}

const statusColor = matchColorExpression('status', PLAN_STATUS_COLORS);

/**
 * Detaljplaner ur Lantmäteriets NGP, färgade efter Boverkets planstatus.
 * Okända statusvärden (fri sträng i kontraktet) får reservfärgen.
 */
const fillLayer: LayerProps = {
  id: 'detail-plan-fills',
  type: 'fill',
  paint: {
    'fill-color': statusColor,
    'fill-opacity': 0.18,
  },
};

const lineLayer: LayerProps = {
  id: 'detail-plan-borders',
  type: 'line',
  paint: {
    'line-color': statusColor,
    'line-width': 1,
    'line-opacity': 0.7,
    'line-dasharray': [2, 1.5],
  },
};

export default function DetailPlanLayer({ data, visible }: Props) {
  if (!visible || data.features.length === 0) return null;

  return (
    <Source id="detail-plan-source" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...lineLayer} />
    </Source>
  );
}
