import { create } from 'zustand';
import type {
  DemographicsMetric,
  DetailPlanFeature,
  FilterState,
  IsochroneOrigin,
  IsochroneProfile,
  LayerVisibility,
  ProjectFeature,
  ProjectStatus,
  ProjectType,
  PropertyFeature,
} from '@/domain';
import { EMPTY_FILTERS } from '@/domain';
import { toggleMinute } from '@/lib/isochrone';

export type SidebarTab = 'search' | 'layers' | 'analysis' | 'watches' | 'details';
export type MapStyleId = 'dark' | 'satellite';

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

  toggleLayer: (layer: keyof LayerVisibility) => void;
  setSelectedProject: (feature: ProjectFeature | null) => void;
  setSelectedProperty: (feature: PropertyFeature | null) => void;
  setSelectedDetailPlan: (feature: DetailPlanFeature | null) => void;
  setDemographicsMetric: (metric: DemographicsMetric) => void;
  setFilters: (filters: Partial<FilterState>) => void;
  toggleStatus: (status: ProjectStatus) => void;
  toggleProjectType: (projectType: ProjectType) => void;
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
  clearSelection: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  layers: {
    infrastructure: true,
    properties: true,
    impactZones: true,
    // Nya nationella lager är avstängda tills användaren slår på dem —
    // de hämtas per kartvy och ska inte belasta förstaladdningen.
    detailPlans: false,
    demographics: false,
    watches: true,
    buildings3d: true,
    terrain: true,
  },

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

  toggleLayer: (layer) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: !state.layers[layer] },
    })),

  setSelectedProject: (feature) =>
    set({
      selectedProject: feature,
      selectedProperty: null,
      selectedDetailPlan: null,
      sidebarTab: feature ? 'details' : 'search',
    }),

  setSelectedProperty: (feature) =>
    set({
      selectedProperty: feature,
      selectedProject: null,
      selectedDetailPlan: null,
      sidebarTab: feature ? 'details' : 'search',
    }),

  setSelectedDetailPlan: (feature) =>
    set({
      selectedDetailPlan: feature,
      selectedProject: null,
      selectedProperty: null,
      sidebarTab: feature ? 'details' : 'search',
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

  clearSelection: () =>
    set({
      selectedProject: null,
      selectedProperty: null,
      selectedDetailPlan: null,
      sidebarTab: 'search',
    }),
}));
