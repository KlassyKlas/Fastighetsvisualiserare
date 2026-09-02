/**
 * Kartbryggan: låter sidofältet styra kartan (zooma till ett objekt)
 * utan att Mapbox-instansen hamnar i uiStore, som bara ska hålla
 * serialiserbart UI-state. MapContainer registrerar kartan vid load och
 * avregistrerar vid unmount; övriga komponenter anropar bara focus*.
 */
import type { Geometry } from 'geojson';
import type { Map as MapboxMap } from 'mapbox-gl';
import { geometryBounds, type Bounds } from '@/lib/geometry';

let instance: MapboxMap | null = null;

/** Zoomtak vid fokus — en enskild fastighet ska synas med omgivning,
 * och en punktgeometri (degenererad bbox) får inte zooma in i oändlighet. */
const DEFAULT_MAX_ZOOM = 16;

/** Filterraden och tidsreglaget ligger över kartans övre del; legenden
 * nere till höger. Luften gör att objektet inte hamnar bakom dem. */
const FOCUS_PADDING = { top: 120, bottom: 80, left: 60, right: 60 };

export function registerMap(map: MapboxMap | null): void {
  instance = map;
}

/** fitBounds till [väst, syd, öst, norr]. Ingen effekt om kartan inte
 * laddats eller rektangeln saknas. */
export function focusBounds(
  bounds: Bounds | null | undefined,
  options?: { maxZoom?: number },
): void {
  if (!instance || !bounds) return;
  const [west, south, east, north] = bounds;
  if (![west, south, east, north].every(Number.isFinite)) return;
  instance.fitBounds(
    [
      [west, south],
      [east, north],
    ],
    {
      padding: FOCUS_PADDING,
      maxZoom: options?.maxZoom ?? DEFAULT_MAX_ZOOM,
      duration: 800,
    },
  );
}

/**
 * Zooma/panorera kartan till en GeoJSON-geometri. Ingen effekt om kartan
 * inte laddats eller geometri saknas — objekt utan geometri (t.ex. från
 * /changes) ska ändå kunna väljas i sidofältet.
 */
export function focusGeometry(
  geometry: Geometry | null | undefined,
  options?: { maxZoom?: number },
): void {
  focusBounds(geometryBounds(geometry), options);
}
