/**
 * Kartbryggan: låter sidofältet styra kartan (zooma till ett objekt)
 * utan att Mapbox-instansen hamnar i uiStore, som bara ska hålla
 * serialiserbart UI-state. MapContainer registrerar kartan vid load och
 * avregistrerar vid unmount; övriga komponenter anropar bara focus*.
 */
import type { Geometry } from 'geojson';
import type { Map as MapboxMap } from 'mapbox-gl';
import { geometryBounds, type Bounds } from '@/lib/geometry';

export interface FocusOptions {
  maxZoom?: number;
}

let instance: MapboxMap | null = null;

/** Fokus begärt innan kartan laddats (t.ex. valet ur en öppnad länk, som
 * ofta hämtas snabbare än kartstilen) — utförs, med sina options, när
 * kartan registreras. Bara det senaste begärda fokuset sparas. */
let pendingFocus: { bounds: Bounds; options?: FocusOptions } | null = null;

/** Zoomtak vid fokus — en enskild fastighet ska synas med omgivning,
 * och en punktgeometri (degenererad bbox) får inte zooma in i oändlighet. */
const DEFAULT_MAX_ZOOM = 16;

/** Filterraden och tidsreglaget ligger över kartans övre del; legenden
 * nere till höger. Luften gör att objektet inte hamnar bakom dem. */
const FOCUS_PADDING = { top: 120, bottom: 80, left: 60, right: 60 };

export function registerMap(map: MapboxMap | null): void {
  instance = map;
  if (map && pendingFocus) {
    const { bounds, options } = pendingFocus;
    pendingFocus = null;
    focusBounds(bounds, options);
  }
}

/** fitBounds till [väst, syd, öst, norr]. Ingen effekt om rektangeln
 * saknas; har kartan inte laddats ännu utförs fokuset när den registreras. */
export function focusBounds(bounds: Bounds | null | undefined, options?: FocusOptions): void {
  if (!bounds) return;
  const [west, south, east, north] = bounds;
  if (![west, south, east, north].every(Number.isFinite)) return;
  if (!instance) {
    pendingFocus = { bounds, options };
    return;
  }

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
 * Zooma/panorera kartan till en GeoJSON-geometri. Ingen effekt om geometri
 * saknas — objekt utan geometri (t.ex. från /changes) ska ändå kunna väljas
 * i sidofältet. Har kartan inte laddats ännu köas fokuset (se focusBounds).
 */
export function focusGeometry(geometry: Geometry | null | undefined, options?: FocusOptions): void {
  focusBounds(geometryBounds(geometry), options);
}
