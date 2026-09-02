/**
 * Restidsanalys (isokroner) via Mapbox Isochrone API.
 *
 * Anropen går direkt från klienten till Mapbox med samma token som
 * kartrenderingen — backend är inte inblandad, så analysen fungerar
 * även i demo-läge. Detta är ett medvetet undantag från regeln om att
 * spatial analys görs i PostGIS: restidszoner kräver Mapbox vägnät.
 */
import type { ExpressionSpecification } from 'mapbox-gl';
import type { Geometry } from 'geojson';
import { FALLBACK_COLOR, ISOCHRONE_PALETTE } from '@/config/map';
import type { IsochroneOrigin, IsochroneProfile } from '@/domain';
import { geometryBounds } from '@/lib/geometry';

/** Mapbox tillåter högst fyra konturer per anrop. */
export const MAX_ISOCHRONE_CONTOURS = 4;

/** Mapbox tak för en enskild kontur, i minuter. */
export const MAX_ISOCHRONE_MINUTES = 60;

/** Restider användaren kan välja bland (minuter). */
export const ISOCHRONE_MINUTE_CHOICES = [5, 10, 15, 20, 30, 45, 60];

/**
 * Sorterade, unika minutvärden inom Mapbox gränser — API:t kräver
 * stigande ordning och avvisar värden över 60 minuter.
 */
export function normalizeMinutes(minutes: number[]): number[] {
  return [...new Set(minutes)]
    .filter((m) => Number.isInteger(m) && m >= 1 && m <= MAX_ISOCHRONE_MINUTES)
    .sort((a, b) => a - b);
}

/**
 * Lägg till eller ta bort en restid ur urvalet. Vid fyra valda konturer
 * lämnas urvalet orört — UI:t inaktiverar också de övriga valen då.
 */
export function toggleMinute(selected: number[], minute: number): number[] {
  if (selected.includes(minute)) {
    return selected.filter((m) => m !== minute);
  }
  if (selected.length >= MAX_ISOCHRONE_CONTOURS) {
    return selected;
  }
  return normalizeMinutes([...selected, minute]);
}

export function buildIsochroneUrl(
  origin: Pick<IsochroneOrigin, 'longitude' | 'latitude'>,
  profile: IsochroneProfile,
  minutes: number[],
  token: string,
): string {
  const contours = normalizeMinutes(minutes);
  if (contours.length === 0) {
    throw new Error('Minst en restidskontur krävs.');
  }
  if (contours.length > MAX_ISOCHRONE_CONTOURS) {
    throw new Error(`Mapbox tillåter högst ${MAX_ISOCHRONE_CONTOURS} restidskonturer.`);
  }
  const coordinates = `${origin.longitude.toFixed(6)},${origin.latitude.toFixed(6)}`;
  const params = new URLSearchParams({
    contours_minutes: contours.join(','),
    polygons: 'true',
    // Utan denoise returnerar Mapbox många små öar långt från startpunkten.
    denoise: '1',
    access_token: token,
  });
  return `https://api.mapbox.com/isochrone/v1/mapbox/${profile}/${coordinates}?${params}`;
}

/** Färg per restid: kortast restid får palettens första (grönaste) färg. */
export function isochroneColorByMinute(minutes: number[]): Record<number, string> {
  const sorted = normalizeMinutes(minutes);
  return Object.fromEntries(
    sorted.map((minute, index) => [
      minute,
      ISOCHRONE_PALETTE[Math.min(index, ISOCHRONE_PALETTE.length - 1)],
    ]),
  );
}

/**
 * Mapbox match-uttryck för konturfärger. Byggs manuellt i stället för
 * via matchColorExpression eftersom `contour` är numerisk — strängnycklar
 * från Object.entries matchar aldrig numeriska egenskapsvärden.
 */
export function contourColorExpression(minutes: number[]): ExpressionSpecification {
  const pairs = Object.entries(isochroneColorByMinute(minutes)).flatMap(([minute, color]) => [
    Number(minute),
    color,
  ]);
  return ['match', ['get', 'contour'], ...pairs, FALLBACK_COLOR] as ExpressionSpecification;
}

/**
 * Representativ startpunkt för en godtycklig geometri: mittpunkten av
 * omslutande rektangel (geometryBounds). Räcker som isokron-origo för
 * fastigheter och projekt — exakta tyngdpunkter behövs inte för
 * restidszoner.
 */
export function geometryAnchor(
  geometry: Geometry | null | undefined,
): Pick<IsochroneOrigin, 'longitude' | 'latitude'> | null {
  const bounds = geometryBounds(geometry);
  if (!bounds) return null;
  const [west, south, east, north] = bounds;
  return { longitude: (west + east) / 2, latitude: (south + north) / 2 };
}
