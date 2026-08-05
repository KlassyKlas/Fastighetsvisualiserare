import { Layer, Marker, Source } from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { ISOCHRONE_ORIGIN_COLOR } from '@/config/map';
import { contourColorExpression } from '@/lib/isochrone';
import type { IsochroneCollection, IsochroneOrigin } from '@/domain';

interface Props {
  origin: IsochroneOrigin;
  /** undefined medan zonerna hämtas — markören visas ändå direkt. */
  data: IsochroneCollection | undefined;
  minutes: number[];
}

/**
 * Restidszoner från Mapbox Isochrone API. Konturerna överlappar
 * (varje polygon täcker hela sitt restidsområde) — sort-key på kontur
 * ritar de längre restiderna underst så att de kortare syns ovanpå.
 */
export default function IsochroneLayer({ origin, data, minutes }: Props) {
  const contourColor = contourColorExpression(minutes);

  const fillLayer: LayerProps = {
    id: 'isochrone-fills',
    type: 'fill',
    layout: {
      'fill-sort-key': ['*', -1, ['get', 'contour']],
    },
    paint: {
      'fill-color': contourColor,
      'fill-opacity': 0.14,
    },
  };

  const lineLayer: LayerProps = {
    id: 'isochrone-borders',
    type: 'line',
    layout: {
      'line-sort-key': ['*', -1, ['get', 'contour']],
    },
    paint: {
      'line-color': contourColor,
      'line-width': 1.5,
      'line-opacity': 0.8,
    },
  };

  return (
    <>
      {data && data.features.length > 0 && (
        <Source id="isochrone-source" type="geojson" data={data}>
          <Layer {...fillLayer} />
          <Layer {...lineLayer} />
        </Source>
      )}
      <Marker
        longitude={origin.longitude}
        latitude={origin.latitude}
        color={ISOCHRONE_ORIGIN_COLOR}
        scale={0.8}
      />
    </>
  );
}
