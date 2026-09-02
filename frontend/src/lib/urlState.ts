/**
 * Delbara länkar: appens tillstånd i query-strängen.
 *
 * Query-strängen bär app-state (filter, lager, flik, val, restid) och ägs
 * av oss; hash-delen (`#karta=zoom/lat/lng/bearing/pitch`) bär kartvyn
 * och ägs av Mapbox (`hash="karta"` på kartan). Modulen är ren — ingen
 * window-åtkomst, ingen store — lib/urlSync kopplar ihop den med båda.
 *
 * Parametrar utelämnas när värdet är lika med standardläget, så att en
 * orörd vy ger en ren adress. Tolkningen är tolerant: okända parametrar,
 * okända enumvärden och ogiltiga tal ignoreras och kastar aldrig — en
 * trasig länk ska öppna appen i standardläget, inte fälla den.
 *
 * OBS id-instabilitet: `fastighet`/`projekt`/`detaljplan` bär databasens
 * id, som skiljer sig mellan miljöer (och demodatats id är 1-baserade
 * index ur seed-ordningen). En länk med val gäller alltså per miljö.
 * Stabila nycklar som fastighetsbeteckning eller external_id saknar exakt
 * uppslagsendpoint, så id är ett medvetet val — övriga parametrar är
 * miljöoberoende.
 */
import {
  DEFAULT_LAYER_VISIBILITY,
  DEMOGRAPHICS_METRICS,
  ISOCHRONE_PROFILE_LABELS,
  LAYER_KEYS,
  MAP_STYLES,
  PROJECT_STATUSES,
  PROJECT_TYPES,
  YEAR_MAX,
  YEAR_MIN,
} from '@/config/map';
import type {
  DemographicsMetric,
  FilterState,
  IsochroneOrigin,
  IsochroneProfile,
  LayerVisibility,
  MapStyleId,
  SidebarTab,
} from '@/domain';
import { EMPTY_FILTERS } from '@/domain';
import { MAX_ISOCHRONE_CONTOURS, normalizeMinutes } from '@/lib/isochrone';

export type UrlSelectionKind = 'property' | 'project' | 'detailPlan';

export interface UrlSelection {
  kind: UrlSelectionKind;
  id: number;
}

export interface UrlIsochrone {
  origin: IsochroneOrigin;
  profile: IsochroneProfile;
  minutes: number[];
}

export interface UrlState {
  filters: FilterState;
  scoreColoring: boolean;
  layers: LayerVisibility;
  demographicsMetric: DemographicsMetric;
  mapStyle: MapStyleId;
  sidebarTab: SidebarTab;
  selection: UrlSelection | null;
  isochrone: UrlIsochrone | null;
}

/** Startpunktens etikett när den kommer ur en länk — namnet på objektet följer inte med. */
export const ISOCHRONE_URL_LABEL = 'Delad startpunkt';

/**
 * Standardläget — det som en tom adress betyder. Speglar storens
 * startvärden (uiStore); testet i urlState.test.ts kontrollerar att de
 * två inte glider isär.
 */
export const DEFAULT_URL_STATE: UrlState = {
  filters: EMPTY_FILTERS,
  scoreColoring: false,
  layers: DEFAULT_LAYER_VISIBILITY,
  demographicsMetric: 'population',
  mapStyle: 'dark',
  sidebarTab: 'search',
  selection: null,
  isochrone: null,
};

/**
 * Parameternamnen i adressen — en enda tabell som både serialisering och
 * tolkning läser, så att ett stavfel på ena sidan inte kan ge tyst
 * asymmetri. Valparametrarna nycklas på UrlSelectionKind.
 */
const PARAM = {
  status: 'status',
  projectType: 'typ',
  municipality: 'kommun',
  owner: 'agare',
  minValue: 'minvarde',
  maxValue: 'maxvarde',
  year: 'ar',
  scoreColoring: 'poang',
  layers: 'lager',
  demographicsMetric: 'metrik',
  mapStyle: 'stil',
  sidebarTab: 'flik',
  property: 'fastighet',
  project: 'projekt',
  detailPlan: 'detaljplan',
  isochrone: 'restid',
} as const;

/**
 * Valen i prioritetsordning: anges flera i samma länk vinner det första
 * (fastighet > projekt > detaljplan) — appen kan bara visa ett val.
 */
const SELECTION_KINDS: readonly UrlSelectionKind[] = ['property', 'project', 'detailPlan'];

// Giltiga enumvärden. Record<T, true> tvingar fram en kompileringsvarning
// när en flik läggs till utan att listan uppdateras.
const SIDEBAR_TAB_SET: Record<SidebarTab, true> = {
  search: true,
  layers: true,
  analysis: true,
  watches: true,
  details: true,
};
const SIDEBAR_TABS = Object.keys(SIDEBAR_TAB_SET) as SidebarTab[];
const MAP_STYLE_IDS = Object.keys(MAP_STYLES) as MapStyleId[];
const DEMOGRAPHICS_METRIC_IDS = Object.keys(DEMOGRAPHICS_METRICS) as DemographicsMetric[];
const ISOCHRONE_PROFILES = Object.keys(ISOCHRONE_PROFILE_LABELS) as IsochroneProfile[];

function isOneOf<T extends string>(value: string, allowed: readonly T[]): value is T {
  return (allowed as readonly string[]).includes(value);
}

function sameList(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function sameLayers(a: LayerVisibility, b: LayerVisibility): boolean {
  return LAYER_KEYS.every((key) => a[key] === b[key]);
}

/** Sex decimaler (~10 cm) räcker för en startpunkt och håller länken kort. */
function formatCoordinate(value: number): string {
  return String(Number(value.toFixed(6)));
}

/**
 * Samma punkt med länkens precision. Används för att en tillämpad länk
 * inte ska byta ut en vald startpunkt (och dess etikett) mot en avrundad
 * kopia av sig själv.
 */
export function sameIsochronePoint(a: IsochroneOrigin, b: IsochroneOrigin): boolean {
  return (
    formatCoordinate(a.longitude) === formatCoordinate(b.longitude) &&
    formatCoordinate(a.latitude) === formatCoordinate(b.latitude)
  );
}

/**
 * Skalära filter (ägare, värden, år) utelämnas när de är lika standard.
 * Är standarden satt men värdet null skrivs parametern TOM (`ar=`), som
 * tolkningen läser som null — serialisering och tolkning ska vara
 * inverser även med andra defaults än DEFAULT_URL_STATE.
 */
function setScalar(
  params: URLSearchParams,
  name: string,
  value: string | number | null,
  base: string | number | null,
): void {
  if (value === base) return;
  params.set(name, value == null ? '' : String(value));
}

export function serializeUrlState(state: UrlState, defaults: UrlState = DEFAULT_URL_STATE): string {
  const params = new URLSearchParams();
  const filters = state.filters;
  const base = defaults.filters;

  if (!sameList(filters.statuses, base.statuses)) {
    params.set(PARAM.status, filters.statuses.join(','));
  }
  if (!sameList(filters.projectTypes, base.projectTypes)) {
    params.set(PARAM.projectType, filters.projectTypes.join(','));
  }
  if (!sameList(filters.municipalities, base.municipalities)) {
    params.set(PARAM.municipality, filters.municipalities.join(','));
  }
  setScalar(params, PARAM.owner, filters.owner, base.owner);
  setScalar(params, PARAM.minValue, filters.minValue, base.minValue);
  setScalar(params, PARAM.maxValue, filters.maxValue, base.maxValue);
  setScalar(params, PARAM.year, filters.year, base.year);
  if (state.scoreColoring !== defaults.scoreColoring) {
    params.set(PARAM.scoreColoring, state.scoreColoring ? '1' : '0');
  }
  if (!sameLayers(state.layers, defaults.layers)) {
    // Fullständig lista över påslagna lager — `lager=` (tomt) betyder alla av.
    params.set(PARAM.layers, LAYER_KEYS.filter((key) => state.layers[key]).join(','));
  }
  if (state.demographicsMetric !== defaults.demographicsMetric) {
    params.set(PARAM.demographicsMetric, state.demographicsMetric);
  }
  if (state.mapStyle !== defaults.mapStyle) {
    params.set(PARAM.mapStyle, state.mapStyle);
  }

  // Detaljfliken är underförstådd när ett val finns (att välja öppnar den)
  // och meningslös utan — i båda fallen skrivs ingen `flik`.
  const impliedTab: SidebarTab = state.selection ? 'details' : defaults.sidebarTab;
  const tab =
    state.sidebarTab === 'details' && !state.selection ? defaults.sidebarTab : state.sidebarTab;
  if (tab !== impliedTab) {
    params.set(PARAM.sidebarTab, tab);
  }

  if (state.selection) {
    params.set(PARAM[state.selection.kind], String(state.selection.id));
  }
  if (state.isochrone) {
    const { origin, profile, minutes } = state.isochrone;
    params.set(
      PARAM.isochrone,
      [
        formatCoordinate(origin.longitude),
        formatCoordinate(origin.latitude),
        profile,
        normalizeMinutes(minutes).join('-'),
      ].join(','),
    );
  }

  // URLSearchParams kodar å/ä/ö och mellanslag korrekt (som browsern gör),
  // men även kommatecken — som är tillåtna okodade i en query-sträng och
  // gör listorna läsbara. Tolkningen förstår båda formerna.
  const query = params.toString().replace(/%2C/g, ',');
  return query ? `?${query}` : '';
}

/** Kommaseparerad lista → unika, icke-tomma värden i given ordning. */
function splitList(value: string): string[] {
  return [
    ...new Set(
      value
        .split(',')
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    ),
  ];
}

/** null när parametern saknas (behåll standard); annars de giltiga värdena. */
function parseEnumList<T extends string>(value: string | null, allowed: readonly T[]): T[] | null {
  if (value == null) return null;
  return splitList(value).filter((item): item is T => isOneOf(item, allowed));
}

/**
 * Skalär parameter: saknas → standard; tom → null (uttrycklig rensning,
 * motsvarigheten till det tomma värde serialiseringen skriver); ogiltig →
 * standard, som för alla andra trasiga värden.
 */
function parseScalar<T>(
  value: string | null,
  parse: (raw: string) => T | null,
  base: T | null,
): T | null {
  if (value == null) return base;
  if (value.trim() === '') return null;
  return parse(value) ?? base;
}

/** Bara siffror — "12", inte "12.0", "1e3", "+12" eller " 12". */
const DIGITS_RE = /^\d+$/;

function parseNonNegativeInt(value: string): number | null {
  if (!DIGITS_RE.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function parsePositiveId(value: string | null): number | null {
  if (value == null) return null;
  const parsed = parseNonNegativeInt(value);
  return parsed != null && parsed > 0 ? parsed : null;
}

/** År utanför reglagets intervall kan inte visas — ignoreras. */
function parseYear(value: string): number | null {
  const parsed = parseNonNegativeInt(value);
  return parsed != null && parsed >= YEAR_MIN && parsed <= YEAR_MAX ? parsed : null;
}

function parseCoordinate(value: string, limit: number): number | null {
  if (value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && Math.abs(parsed) <= limit ? parsed : null;
}

/**
 * `lng,lat,profil,min-min-…` — hela parametern ignoreras om någon del är
 * ogiltig. En TOM minutdel (`…,walking,`) är däremot ett giltigt läge:
 * startpunkt vald men alla restider avmarkerade (toggleIsochroneMinute
 * tillåter det, och panelen visar då startpunktskortet utan zoner). Det
 * är vad serialiseringen skriver för det läget, och det ska överleva
 * delning — annars försvinner startpunkten vid omladdning.
 */
function parseIsochrone(value: string | null): UrlIsochrone | null {
  if (value == null) return null;
  const parts = value.split(',');
  if (parts.length !== 4) return null;
  const longitude = parseCoordinate(parts[0], 180);
  const latitude = parseCoordinate(parts[1], 90);
  const profile = parts[2].trim();
  if (longitude == null || latitude == null || !isOneOf(profile, ISOCHRONE_PROFILES)) {
    return null;
  }
  const minutePart = parts[3].trim();
  if (minutePart === '') {
    return { origin: { longitude, latitude, label: ISOCHRONE_URL_LABEL }, profile, minutes: [] };
  }
  // normalizeMinutes sorterar stigande — vid fler än fyra behålls de kortaste.
  const minutes = normalizeMinutes(minutePart.split('-').map(Number)).slice(
    0,
    MAX_ISOCHRONE_CONTOURS,
  );
  if (minutes.length === 0) return null;
  return { origin: { longitude, latitude, label: ISOCHRONE_URL_LABEL }, profile, minutes };
}

function parseLayers(value: string | null, fallback: LayerVisibility): LayerVisibility {
  if (value == null) return fallback;
  const enabled = new Set(splitList(value));
  return Object.fromEntries(
    LAYER_KEYS.map((key) => [key, enabled.has(key)]),
  ) as unknown as LayerVisibility;
}

function parseSelection(params: URLSearchParams): UrlSelection | null {
  for (const kind of SELECTION_KINDS) {
    const id = parsePositiveId(params.get(PARAM[kind]));
    if (id != null) return { kind, id };
  }
  return null;
}

export function parseUrlState(
  search: string,
  defaults: UrlState = DEFAULT_URL_STATE,
): { state: UrlState; selection: UrlSelection | null } {
  const params = new URLSearchParams(search);
  const base = defaults.filters;

  const kommun = params.get(PARAM.municipality);
  const filters: FilterState = {
    statuses: parseEnumList(params.get(PARAM.status), PROJECT_STATUSES) ?? base.statuses,
    projectTypes: parseEnumList(params.get(PARAM.projectType), PROJECT_TYPES) ?? base.projectTypes,
    municipalities: kommun != null ? splitList(kommun) : base.municipalities,
    minValue: parseScalar(params.get(PARAM.minValue), parseNonNegativeInt, base.minValue),
    maxValue: parseScalar(params.get(PARAM.maxValue), parseNonNegativeInt, base.maxValue),
    year: parseScalar(params.get(PARAM.year), parseYear, base.year),
    owner: parseScalar(params.get(PARAM.owner), (raw) => raw.trim(), base.owner),
  };

  const poang = params.get(PARAM.scoreColoring);
  const scoreColoring = poang === '1' ? true : poang === '0' ? false : defaults.scoreColoring;

  const metrik = params.get(PARAM.demographicsMetric);
  const stil = params.get(PARAM.mapStyle);
  const selection = parseSelection(params);

  // Fliken 'details' utan val är meningslös — då gäller standardfliken,
  // samma som serialiseringen skriver för det läget.
  const flik = params.get(PARAM.sidebarTab);
  let sidebarTab: SidebarTab =
    flik != null && isOneOf(flik, SIDEBAR_TABS)
      ? flik
      : selection
        ? 'details'
        : defaults.sidebarTab;
  if (sidebarTab === 'details' && !selection) {
    sidebarTab = defaults.sidebarTab;
  }

  return {
    state: {
      filters,
      scoreColoring,
      layers: parseLayers(params.get(PARAM.layers), defaults.layers),
      demographicsMetric:
        metrik != null && isOneOf(metrik, DEMOGRAPHICS_METRIC_IDS)
          ? metrik
          : defaults.demographicsMetric,
      mapStyle: stil != null && isOneOf(stil, MAP_STYLE_IDS) ? stil : defaults.mapStyle,
      sidebarTab,
      selection,
      isochrone: parseIsochrone(params.get(PARAM.isochrone)),
    },
    selection,
  };
}

/** Det av storens tillstånd som URL:en speglar — strukturellt, så att
 * funktionen kan testas utan storen. */
export interface UrlStateSource {
  filters: FilterState;
  scoreColoring: boolean;
  layers: LayerVisibility;
  demographicsMetric: DemographicsMetric;
  mapStyle: MapStyleId;
  sidebarTab: SidebarTab;
  selectedProperty: { properties: { id: number } } | null;
  selectedProject: { properties: { id: number } } | null;
  selectedDetailPlan: { properties: { id: number } } | null;
  pendingSelection: UrlSelection | null;
  isochroneOrigin: IsochroneOrigin | null;
  isochroneProfile: IsochroneProfile;
  isochroneMinutes: number[];
}

/** Kartklickets feature kan ha id som sträng — bara positiva heltal duger i länken. */
function selectionFromFeature(
  kind: UrlSelectionKind,
  feature: { properties: { id: number } } | null,
): UrlSelection | null {
  if (!feature) return null;
  const id = Number(feature.properties.id);
  return Number.isSafeInteger(id) && id > 0 ? { kind, id } : null;
}

/** Det valda objektet som länkval — null utan val eller med obrukbart id. */
export function selectedUrlSelection(
  state: Pick<UrlStateSource, 'selectedProperty' | 'selectedProject' | 'selectedDetailPlan'>,
): UrlSelection | null {
  return (
    selectionFromFeature('property', state.selectedProperty) ??
    selectionFromFeature('project', state.selectedProject) ??
    selectionFromFeature('detailPlan', state.selectedDetailPlan)
  );
}

export function sameSelection(a: UrlSelection | null, b: UrlSelection | null): boolean {
  if (a == null || b == null) return a === b;
  return a.kind === b.kind && a.id === b.id;
}

export function urlStateFromStore(state: UrlStateSource): UrlState {
  // Valet i länken är det valda objektet — eller det som ännu laddas ur en
  // öppnad länk. Utan det senare skulle `fastighet=12` försvinna ur
  // adressen så snart något annat i storen ändras under hämtningen.
  const selection = selectedUrlSelection(state) ?? state.pendingSelection;

  return {
    filters: state.filters,
    scoreColoring: state.scoreColoring,
    layers: state.layers,
    demographicsMetric: state.demographicsMetric,
    mapStyle: state.mapStyle,
    sidebarTab: state.sidebarTab,
    selection,
    isochrone: state.isochroneOrigin
      ? {
          origin: state.isochroneOrigin,
          profile: state.isochroneProfile,
          minutes: state.isochroneMinutes,
        }
      : null,
  };
}
