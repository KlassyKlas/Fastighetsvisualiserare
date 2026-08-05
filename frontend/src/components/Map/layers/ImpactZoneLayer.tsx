import { Layer, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { matchColorExpression, STATUS_COLORS } from '@/config/map';
import type { ImpactZoneCollection } from '@/domain';

interface Props {
  data: ImpactZoneCollection;
  visible: boolean;
}

const statusColor = matchColorExpression('status', STATUS_COLORS);

/**
 * Påverkanszonerna kommer färdigbuffrade från backend (PostGIS ST_Buffer
 * över geography i meter — korrekt för punkter, linjer och ytor). I
 * demo-läget kommer motsvarande förberäknade zoner ur exempeldatat.
 * Ingen klientsidig buffring förekommer längre.
 */
const fillLayer: LayerProps = {
  id: 'impact-zone-fills',
  type: 'fill',
  paint: {
    'fill-color': statusColor,
    'fill-opacity': 0.08,
  },
};

const lineLayer: LayerProps = {
  id: 'impact-zone-borders',
  type: 'line',
  paint: {
    'line-color': statusColor,
    'line-width': 1.5,
    'line-opacity': 0.4,
    'line-dasharray': [4, 2],
  },
};

export default function ImpactZoneLayer({ data, visible }: Props) {
  if (!visible || data.features.length === 0) return null;

  return (
    <Source id="impact-zone-source" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...lineLayer} />
    </Source>
  );
}
