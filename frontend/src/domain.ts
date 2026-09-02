/**
 * Domäntyper. Alla API-former kommer från de genererade typerna i
 * `api/schema.d.ts` (körs om med `npm run typegen`) — inget dupliceras
 * för hand mot backend.
 */
import type { Feature, FeatureCollection, Geometry, Polygon } from 'geojson';
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
export type ProximityScoreProps = components['schemas']['ProximityScoreProps'];
export type ScoreContribution = components['schemas']['ScoreContribution'];
export type DetailPlanProps = components['schemas']['DetailPlanProps'];
export type DesoAreaProps = components['schemas']['DesoAreaProps'];
export type WatchedAreaProps = components['schemas']['WatchedAreaProps'];
export type WatchedAreaCreate = components['schemas']['WatchedAreaCreate'];
export type WatchEventKind = components['schemas']['WatchEventKind'];
export type WatchEvents = components['schemas']['WatchEvents'];
export type WatchEventsResponse = components['schemas']['WatchEventsResponse'];
export type ProjectWatchEvent = components['schemas']['ProjectWatchEvent'];
export type DetailPlanWatchEvent = components['schemas']['DetailPlanWatchEvent'];
export type ChangesResponse = components['schemas']['ChangesResponse'];
export type SyncRunInfo = components['schemas']['SyncRunInfo'];
export type SyncRunList = components['schemas']['SyncRunList'];

/**
 * API:t serialiserar geometrier som generisk GeoJSON. För kartlagren
 * behöver vi @types/geojson-formerna — egenskaperna är identiska.
 */
export type ProjectFeature = Feature<Geometry, ProjectProps>;
export type PropertyFeature = Feature<Geometry, PropertyProps>;
export type ImpactZoneFeature = Feature<Geometry, ImpactZoneProps>;
export type ProximityScoreFeature = Feature<Geometry, ProximityScoreProps>;
export type DetailPlanFeature = Feature<Geometry, DetailPlanProps>;
export type DesoAreaFeature = Feature<Geometry, DesoAreaProps>;
export type WatchedAreaFeature = Feature<Geometry, WatchedAreaProps>;

export interface PaginatedCollection {
  numberMatched?: number;
  numberReturned?: number;
}

export type ProjectCollection = FeatureCollection<Geometry, ProjectProps> & PaginatedCollection;
export type PropertyCollection = FeatureCollection<Geometry, PropertyProps> & PaginatedCollection;
export type ImpactZoneCollection = FeatureCollection<Geometry, ImpactZoneProps>;
export type ProximityScoresCollection = FeatureCollection<Geometry, ProximityScoreProps> &
  PaginatedCollection & { max_distance_m?: number };
export type DetailPlanCollection = FeatureCollection<Geometry, DetailPlanProps> &
  PaginatedCollection;
export type DesoAreaCollection = FeatureCollection<Geometry, DesoAreaProps> & PaginatedCollection;
export type WatchedAreaCollection = FeatureCollection<Geometry, WatchedAreaProps> &
  PaginatedCollection;

/** Metrik som färgsätter demografilagret (DeSO-choropleth). */
export type DemographicsMetric = 'population' | 'density' | 'income' | 'education';

/**
 * Restidsanalys (isokroner). Datat kommer från Mapbox Isochrone API,
 * inte från backendens kontrakt — därför definieras typerna här.
 */
export type IsochroneProfile = 'walking' | 'cycling' | 'driving';

export interface IsochroneOrigin {
  longitude: number;
  latitude: number;
  /** Visningsnamn i panelen och legenden, t.ex. fastighetsbeteckning. */
  label: string;
}

export interface IsochroneContourProps {
  /** Restid i minuter för konturen. */
  contour: number;
}

export type IsochroneCollection = FeatureCollection<Polygon, IsochroneContourProps>;

export interface LayerVisibility {
  infrastructure: boolean;
  properties: boolean;
  impactZones: boolean;
  detailPlans: boolean;
  demographics: boolean;
  watches: boolean;
  buildings3d: boolean;
  terrain: boolean;
}

export interface FilterState {
  statuses: ProjectStatus[];
  projectTypes: ProjectType[];
  municipalities: string[];
  minValue: number | null;
  maxValue: number | null;
  /** Visa bara projekt som är aktiva under detta år (null = alla år) */
  year: number | null;
}

export const EMPTY_FILTERS: FilterState = {
  statuses: [],
  projectTypes: [],
  municipalities: [],
  minValue: null,
  maxValue: null,
  year: null,
};
