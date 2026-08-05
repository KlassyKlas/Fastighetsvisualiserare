import { create } from 'zustand';
import type { Feature } from 'geojson';
import type { LayerVisibility, FilterState, ProjectStatus, ProjectType } from '@/types';

interface AppState {
  layers: LayerVisibility;
  selectedProject: Feature | null;
  selectedProperty: Feature | null;
  filters: FilterState;
  sidebarOpen: boolean;
  sidebarTab: 'search' | 'layers' | 'details';
  mapStyle: 'dark' | 'satellite';
  searchQuery: string;

  toggleLayer: (layer: keyof LayerVisibility) => void;
  setSelectedProject: (feature: Feature | null) => void;
  setSelectedProperty: (feature: Feature | null) => void;
  setFilters: (filters: Partial<FilterState>) => void;
  toggleStatus: (status: ProjectStatus) => void;
  toggleProjectType: (projectType: ProjectType) => void;
  setSidebarOpen: (open: boolean) => void;
  setSidebarTab: (tab: 'search' | 'layers' | 'details') => void;
  setMapStyle: (style: 'dark' | 'satellite') => void;
  setSearchQuery: (query: string) => void;
  clearSelection: () => void;
}

export const useStore = create<AppState>((set) => ({
  layers: {
    infrastructure: true,
    properties: true,
    impactZones: true,
    buildings3d: true,
    terrain: true,
  },

  selectedProject: null,
  selectedProperty: null,

  filters: {
    statuses: [],
    projectTypes: [],
    municipalities: [],
    minValue: null,
    maxValue: null,
  },

  sidebarOpen: true,
  sidebarTab: 'search',
  mapStyle: 'dark',
  searchQuery: '',

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

  clearSelection: () =>
    set({
      selectedProject: null,
      selectedProperty: null,
      sidebarTab: 'search',
    }),
}));
