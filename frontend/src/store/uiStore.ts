import { create } from 'zustand';
import { DEFAULT_LAYER_VISIBILITY } from '@/config/map';
import type {
  DemographicsMetric,
  DetailPlanFeature,
  FilterState,
  IsochroneOrigin,
  IsochroneProfile,
  LayerVisibility,
  MapStyleId,
  ProjectFeature,
  ProjectStatus,
  ProjectType,
  PropertyFeature,
  SidebarTab,
} from '@/domain';
import { EMPTY_FILTERS } from '@/domain';
import type { ChangesPeriod } from '@/lib/changes';
import { readChangesSeenAt, writeChangesSeenAt } from '@/lib/changesSeen';
import { toggleMinute } from '@/lib/isochrone';
import { sameIsochronePoint, sameSelection, selectedUrlSelection } from '@/lib/urlState';
import type { UrlSelection, UrlState } from '@/lib/urlState';

// Typerna bor i domain.ts (URL-tolkningen behöver dem utan storen) men
// exporteras även härifrån för befintliga importer.
export type { MapStyleId, SidebarTab } from '@/domain';

interface UiState {
  layers: LayerVisibility;
  selectedProject: ProjectFeature | null;
  selectedProperty: PropertyFeature | null;
  selectedDetailPlan: DetailPlanFeature | null;
  /** Metrik som färgsätter demografilagret */
  demographicsMetric: DemographicsMetric;
  filters: FilterState;
  sidebarOpen: boolean;
  sidebarTab: SidebarTab;
  mapStyle: MapStyleId;
  searchQuery: string;
  /** true när backend inte nås och appen visar exempeldata */
  demoMode: boolean;
  /** Färga fastigheterna på kartan efter närhetspoäng */
  scoreColoring: boolean;
  /** Startpunkt för restidsanalysen (null = ingen analys aktiv) */
  isochroneOrigin: IsochroneOrigin | null;
  isochroneProfile: IsochroneProfile;
  /** Valda restider i minuter — högst fyra (Mapbox-gräns) */
  isochroneMinutes: number[];
  /** true medan användaren väljer startpunkt genom att klicka i kartan */
  isochronePicking: boolean;
  /** true medan användaren ritar ett bevakningsområde i kartan */
  watchDrawing: boolean;
  /** Hörnen (lng, lat) i området som ritas — sparas som polygon */
  watchDraftPoints: [number, number][];
  /** Fastighet som objektsrapporten visas för (null = ingen rapport) */
  reportProperty: PropertyFeature | null;
  /** Vald period i panelen "Nytt sedan senast" */
  changesPeriod: ChangesPeriod;
  /** När användaren senast markerade ändringarna som sedda (ISO, localStorage) */
  changesSeenAt: string | null;
  /** Val ur en öppnad länk som ännu inte hämtats (UrlSelectionLoader löser upp det) */
  pendingSelection: UrlSelection | null;

  toggleLayer: (layer: keyof LayerVisibility) => void;
  setSelectedProject: (feature: ProjectFeature | null) => void;
  setSelectedProperty: (feature: PropertyFeature | null) => void;
  setSelectedDetailPlan: (feature: DetailPlanFeature | null) => void;
  setDemographicsMetric: (metric: DemographicsMetric) => void;
  setFilters: (filters: Partial<FilterState>) => void;
  toggleStatus: (status: ProjectStatus) => void;
  toggleProjectType: (projectType: ProjectType) => void;
  /** Ägarvyn: null stänger den. Övriga filter lämnas orörda. */
  setOwnerFilter: (owner: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  setSidebarTab: (tab: SidebarTab) => void;
  setMapStyle: (style: MapStyleId) => void;
  setSearchQuery: (query: string) => void;
  setDemoMode: (demo: boolean) => void;
  setScoreColoring: (enabled: boolean) => void;
  setIsochroneOrigin: (origin: IsochroneOrigin | null) => void;
  setIsochroneProfile: (profile: IsochroneProfile) => void;
  toggleIsochroneMinute: (minute: number) => void;
  setIsochronePicking: (picking: boolean) => void;
  clearIsochrone: () => void;
  setWatchDrawing: (drawing: boolean) => void;
  addWatchDraftPoint: (point: [number, number]) => void;
  undoWatchDraftPoint: () => void;
  setReportProperty: (feature: PropertyFeature | null) => void;
  setChangesPeriod: (period: ChangesPeriod) => void;
  markChangesSeen: () => void;
  clearSelection: () => void;
  /** Delbara länkar: tillämpa hela URL-tillståndet i ett svep (lib/urlSync). */
  applyUrlState: (state: UrlState) => void;
  setPendingSelection: (selection: UrlSelection | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  layers: DEFAULT_LAYER_VISIBILITY,

  selectedProject: null,
  selectedProperty: null,
  selectedDetailPlan: null,
  demographicsMetric: 'population',
  filters: EMPTY_FILTERS,
  sidebarOpen: true,
  sidebarTab: 'search',
  mapStyle: 'dark',
  searchQuery: '',
  demoMode: false,
  scoreColoring: false,
  isochroneOrigin: null,
  isochroneProfile: 'walking',
  isochroneMinutes: [10, 20, 30],
  isochronePicking: false,
  watchDrawing: false,
  watchDraftPoints: [],
  reportProperty: null,
  changesPeriod: 'visit',
  changesSeenAt: readChangesSeenAt(),
  pendingSelection: null,

  toggleLayer: (layer) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: !state.layers[layer] },
    })),

  // Ett val användaren gör medan en länks objekt hämtas vinner: det
  // väntande släpps så att UrlSelectionLoader inte skriver över valet när
  // hämtningen blir klar. Att avmarkera (null) släpper inget — länkens
  // objekt får då fortfarande visas.
  setSelectedProject: (feature) =>
    set({
      selectedProject: feature,
      selectedProperty: null,
      selectedDetailPlan: null,
      sidebarTab: feature ? 'details' : 'search',
      ...(feature ? { pendingSelection: null } : {}),
    }),

  setSelectedProperty: (feature) =>
    set({
      selectedProperty: feature,
      selectedProject: null,
      selectedDetailPlan: null,
      sidebarTab: feature ? 'details' : 'search',
      ...(feature ? { pendingSelection: null } : {}),
    }),

  setSelectedDetailPlan: (feature) =>
    set({
      selectedDetailPlan: feature,
      selectedProject: null,
      selectedProperty: null,
      sidebarTab: feature ? 'details' : 'search',
      ...(feature ? { pendingSelection: null } : {}),
    }),

  setDemographicsMetric: (metric) => set({ demographicsMetric: metric }),

  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
    })),

  toggleStatus: (status) =>
    set((state) => {
      const statuses = state.filters.statuses.includes(status)
        ? state.filters.statuses.filter((s) => s !== status)
        : [...state.filters.statuses, status];
      return { filters: { ...state.filters, statuses } };
    }),

  toggleProjectType: (projectType) =>
    set((state) => {
      const projectTypes = state.filters.projectTypes.includes(projectType)
        ? state.filters.projectTypes.filter((t) => t !== projectType)
        : [...state.filters.projectTypes, projectType];
      return { filters: { ...state.filters, projectTypes } };
    }),

  setOwnerFilter: (owner) => set((state) => ({ filters: { ...state.filters, owner } })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSidebarTab: (tab) => set({ sidebarTab: tab }),
  setMapStyle: (style) => set({ mapStyle: style }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setDemoMode: (demo) => set({ demoMode: demo }),
  setScoreColoring: (enabled) => set({ scoreColoring: enabled }),

  // Att sätta en startpunkt avslutar alltid väljarläget — oavsett om
  // punkten kom från kartklick eller från en detaljpanel.
  setIsochroneOrigin: (origin) => set({ isochroneOrigin: origin, isochronePicking: false }),
  setIsochroneProfile: (profile) => set({ isochroneProfile: profile }),

  toggleIsochroneMinute: (minute) =>
    set((state) => ({ isochroneMinutes: toggleMinute(state.isochroneMinutes, minute) })),

  setIsochronePicking: (picking) => set({ isochronePicking: picking }),

  /** Profil och minutval behålls — bara analysen stängs av. */
  clearIsochrone: () => set({ isochroneOrigin: null, isochronePicking: false }),

  // Ritläget och isokron-väljaren tar båda över kartklicken — bara ett
  // av dem får vara aktivt åt gången. Att avsluta ritningen rensar
  // alltid utkastet.
  setWatchDrawing: (drawing) =>
    set({
      watchDrawing: drawing,
      watchDraftPoints: [],
      ...(drawing ? { isochronePicking: false } : {}),
    }),

  addWatchDraftPoint: (point) =>
    set((state) => ({ watchDraftPoints: [...state.watchDraftPoints, point] })),

  undoWatchDraftPoint: () =>
    set((state) => ({ watchDraftPoints: state.watchDraftPoints.slice(0, -1) })),

  setReportProperty: (feature) => set({ reportProperty: feature }),

  setChangesPeriod: (period) => set({ changesPeriod: period }),

  // Markören skrivs till localStorage OCH storen: storen driver
  // renderingen direkt, localStorage överlever omladdningen.
  markChangesSeen: () => {
    const now = new Date().toISOString();
    writeChangesSeenAt(now);
    set({ changesSeenAt: now });
  },

  clearSelection: () =>
    set({
      selectedProject: null,
      selectedProperty: null,
      selectedDetailPlan: null,
      sidebarTab: 'search',
    }),

  // Filter och lager ERSÄTTS, inte slås ihop: det länken inte nämner är
  // standard, inte "oförändrat" — utan `agare` finns inget ägarfilter,
  // utan `lager` gäller standardlagren. Restidsprofil och minuter behålls
  // när länken saknar restid (som clearIsochrone). Bara URL-fält rörs —
  // transient state som väljar- och ritläge lämnas som det är.
  //
  // Startpunkten: avser länken samma punkt som redan är vald behålls den —
  // länkens kopia är avrundad och har en generisk etikett, och ett byte
  // skulle både tappa objektets namn i panelen och hämta om isokronerna.
  //
  // Valet: länken är sanning även här. Saknar den val, eller avser den ett
  // annat objekt, släpps det valda (lib/urlSync lägger länkens som
  // pendingSelection så att UrlSelectionLoader hämtar det). Samma objekt
  // behålls — annars skulle detaljpanelen blinka vid varje popstate.
  applyUrlState: (url) =>
    set((state) => ({
      filters: url.filters,
      scoreColoring: url.scoreColoring,
      layers: url.layers,
      demographicsMetric: url.demographicsMetric,
      mapStyle: url.mapStyle,
      sidebarTab: url.sidebarTab,
      isochroneOrigin: url.isochrone
        ? state.isochroneOrigin && sameIsochronePoint(state.isochroneOrigin, url.isochrone.origin)
          ? state.isochroneOrigin
          : url.isochrone.origin
        : null,
      ...(url.isochrone
        ? { isochroneProfile: url.isochrone.profile, isochroneMinutes: url.isochrone.minutes }
        : {}),
      ...(sameSelection(url.selection, selectedUrlSelection(state))
        ? {}
        : { selectedProject: null, selectedProperty: null, selectedDetailPlan: null }),
    })),

  setPendingSelection: (selection) => set({ pendingSelection: selection }),
}));
