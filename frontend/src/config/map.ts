import type { ExpressionSpecification } from 'mapbox-gl';
import type { IsochroneProfile, ProjectStatus, ProjectType, PropertyType } from '@/domain';

export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN ?? '';

export const MAP_STYLES = {
  dark: 'mapbox://styles/mapbox/dark-v11',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
} as const;

export const INITIAL_VIEW_STATE = {
  longitude: 18.07,
  latitude: 59.33,
  zoom: 11,
  pitch: 45,
  bearing: -17,
};

export const FALLBACK_COLOR = '#6b7280';

/** Färgskala för närhetspoäng: låg → hög, plus neutral för "utan poäng" */
export const SCORE_GRADIENT = {
  low: '#155e75',
  mid: '#eab308',
  high: '#ef4444',
  none: '#334155',
} as const;

/** Färger för restidskonturer: kortast restid först. Högst fyra konturer. */
export const ISOCHRONE_PALETTE = ['#22c55e', '#eab308', '#f97316', '#ef4444'];

export const ISOCHRONE_PROFILE_LABELS: Record<IsochroneProfile, string> = {
  walking: 'Gång',
  cycling: 'Cykel',
  driving: 'Bil',
};

/** Startpunktsmarkörens färg på kartan. */
export const ISOCHRONE_ORIGIN_COLOR = '#3b82f6';

export const STATUS_COLORS: Record<ProjectStatus, string> = {
  planerad: '#f59e0b',
  pågående: '#3b82f6',
  avslutad: '#22c55e',
};

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  planerad: 'Planerad',
  pågående: 'Pågående',
  avslutad: 'Avslutad',
};

export const PROJECT_TYPE_LABELS: Record<ProjectType, string> = {
  väg: 'Väg',
  järnväg: 'Järnväg',
  kollektivtrafik: 'Kollektivtrafik',
  bro: 'Bro',
  tunnel: 'Tunnel',
  cykelväg: 'Cykelväg',
  övrigt: 'Övrigt',
};

export const PROPERTY_TYPE_COLORS: Record<PropertyType, string> = {
  bostad: '#14b8a6',
  kontor: '#a855f7',
  handel: '#f97316',
  industri: '#ef4444',
  utbildning: '#06b6d4',
  villa: '#84cc16',
};

export const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  bostad: 'Bostad',
  kontor: 'Kontor',
  handel: 'Handel',
  industri: 'Industri',
  utbildning: 'Utbildning',
  villa: 'Villa',
};

/**
 * Svenska etiketter för datakällor. `source` är en fri sträng i
 * kontraktet (inte enum) — okända källnamn visas som de är.
 * Etiketterna speglar backendens display_name i datasource-registret.
 */
export const SOURCE_LABELS: Record<string, string> = {
  manual: 'Manuellt inlagd',
  trafikverket: 'Trafikverket (trafikinformation)',
  nationell_plan: 'Trafikverket (nationell plan)',
};

export const PROJECT_STATUSES = Object.keys(STATUS_LABELS) as ProjectStatus[];
export const PROJECT_TYPES = Object.keys(PROJECT_TYPE_LABELS) as ProjectType[];

/**
 * Bygg ett Mapbox match-uttryck från en färgtabell — enda källan för
 * färger är tabellerna ovan, aldrig hårdkodade kopior i lagerdefinitioner.
 */
export function matchColorExpression(
  property: string,
  colors: Record<string, string>,
): ExpressionSpecification {
  return [
    'match',
    ['get', property],
    ...Object.entries(colors).flat(),
    FALLBACK_COLOR,
  ] as ExpressionSpecification;
}
