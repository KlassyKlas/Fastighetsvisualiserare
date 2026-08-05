export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string;

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

export const STATUS_COLORS: Record<string, string> = {
  planerad: '#f59e0b',
  pågående: '#3b82f6',
  avslutad: '#22c55e',
};

export const PROPERTY_TYPE_COLORS: Record<string, string> = {
  bostad: '#14b8a6',
  kontor: '#a855f7',
  handel: '#f97316',
  industri: '#ef4444',
  utbildning: '#06b6d4',
  villa: '#84cc16',
};

export const STATUS_LABELS: Record<string, string> = {
  planerad: 'Planerad',
  pågående: 'Pågående',
  avslutad: 'Avslutad',
};

export const PROPERTY_TYPE_LABELS: Record<string, string> = {
  bostad: 'Bostad',
  kontor: 'Kontor',
  handel: 'Handel',
  industri: 'Industri',
  utbildning: 'Utbildning',
  villa: 'Villa',
};

export const PROJECT_TYPE_LABELS: Record<string, string> = {
  väg: 'Väg',
  järnväg: 'Järnväg',
  kollektivtrafik: 'Kollektivtrafik',
  bro: 'Bro',
  tunnel: 'Tunnel',
  cykelväg: 'Cykelväg',
  övrigt: 'Övrigt',
};
