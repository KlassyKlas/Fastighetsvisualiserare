/**
 * Domäntyper. Alla API-former kommer från de genererade typerna i
 * `api/schema.d.ts` (körs om med `npm run typegen`) — inget dupliceras
 * för hand mot backend.
 */
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import type { components } from '@/api/schema';

export type ProjectStatus = components['schemas']['ProjectStatus'];
export type ProjectType = components['schemas']['ProjectType'];
export type PropertyType = components['schemas']['PropertyType'];

export type ProjectProps = components['schemas']['InfrastructureProjectProps'];
export type PropertyProps = components['schemas']['PropertyProps'];
export type ImpactZoneProps = components['schemas']['ImpactZoneProps'];
export type NearbyProject = components['schemas']['NearbyProject'];
export type NearbyProjectsResponse = components['schemas']['NearbyProjectsResponse'];
export type SyncResult = components['schemas']['SyncResult'];

/**
 * API:t serialiserar geometrier som generisk GeoJSON. För kartlagren
 * behöver vi @types/geojson-formerna — egenskaperna är identiska.
 */
export type ProjectFeature = Feature<Geometry, ProjectProps>;
export type PropertyFeature = Feature<Geometry, PropertyProps>;
export type ImpactZoneFeature = Feature<Geometry, ImpactZoneProps>;

export interface PaginatedCollection {
  numberMatched?: number;
  numberReturned?: number;
}

export type ProjectCollection = FeatureCollection<Geometry, ProjectProps> & PaginatedCollection;
export type PropertyCollection = FeatureCollection<Geometry, PropertyProps> & PaginatedCollection;
export type ImpactZoneCollection = FeatureCollection<Geometry, ImpactZoneProps>;

export interface LayerVisibility {
  infrastructure: boolean;
  properties: boolean;
  impactZones: boolean;
  buildings3d: boolean;
  terrain: boolean;
}

export interface FilterState {
  statuses: ProjectStatus[];
  projectTypes: ProjectType[];
  municipalities: string[];
  minValue: number | null;
  maxValue: number | null;
}

export const EMPTY_FILTERS: FilterState = {
  statuses: [],
  projectTypes: [],
  municipalities: [],
  minValue: null,
  maxValue: null,
};
