import { create } from 'zustand';
import type {
  FilterState,
  LayerVisibility,
  ProjectFeature,
  ProjectStatus,
  ProjectType,
  PropertyFeature,
} from '@/domain';
import { EMPTY_FILTERS } from '@/domain';

export type SidebarTab = 'search' | 'layers' | 'analysis' | 'details';
export type MapStyleId = 'dark' | 'satellite';

interface UiState {
  layers: LayerVisibility;
  selectedProject: ProjectFeature | null;
  selectedProperty: PropertyFeature | null;
  filters: FilterState;
  sidebarOpen: boolean;
  sidebarTab: SidebarTab;
  mapStyle: MapStyleId;
  searchQuery: string;
  /** true när backend inte nås och appen visar exempeldata */
  demoMode: boolean;
  /** Färga fastigheterna på kartan efter närhetspoäng */
  scoreColoring: boolean;

  toggleLayer: (layer: keyof LayerVisibility) => void;
  setSelectedProject: (feature: ProjectFeature | null) => void;
  setSelectedProperty: (feature: PropertyFeature | null) => void;
  setFilters: (filters: Partial<FilterState>) => void;
  toggleStatus: (status: ProjectStatus) => void;
  toggleProjectType: (projectType: ProjectType) => void;
  setSidebarOpen: (open: boolean) => void;
  setSidebarTab: (tab: SidebarTab) => void;
  setMapStyle: (style: MapStyleId) => void;
  setSearchQuery: (query: string) => void;
  setDemoMode: (demo: boolean) => void;
  setScoreColoring: (enabled: boolean) => void;
  clearSelection: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  layers: {
    infrastructure: true,
    properties: true,
    impactZones: true,
    buildings3d: true,
    terrain: true,
  },

  selectedProject: null,
  selectedProperty: null,
  filters: EMPTY_FILTERS,
  sidebarOpen: true,
  sidebarTab: 'search',
  mapStyle: 'dark',
  searchQuery: '',
  demoMode: false,
  scoreColoring: false,

  toggleLayer: (layer) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: !state.layers[layer] },
    })),

  setSelectedProject: (feature) =>
    set({
      selectedProject: feature,
      selectedProperty: null,
      sidebarTab: feature ? 'details' : 'search',
    }),

  setSelectedProperty: (feature) =>
    set({
      selectedProperty: feature,
      selectedProject: null,
      sidebarTab: feature ? 'details' : 'search',
    }),

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

  clearSelection: () =>
    set({
      selectedProject: null,
      selectedProperty: null,
      sidebarTab: 'search',
    }),
}));
