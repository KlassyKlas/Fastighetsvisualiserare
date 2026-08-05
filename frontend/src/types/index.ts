import type { FeatureCollection, Feature, Geometry } from 'geojson';

export type ProjectStatus = 'planerad' | 'pågående' | 'avslutad';

export type ProjectType =
  | 'väg'
  | 'järnväg'
  | 'kollektivtrafik'
  | 'bro'
  | 'tunnel'
  | 'cykelväg'
  | 'övrigt';

export type PropertyType =
  | 'bostad'
  | 'kontor'
  | 'handel'
  | 'industri'
  | 'utbildning'
  | 'villa';

export interface InfrastructureProperties {
  id: string;
  external_id?: string;
  source: string;
  name: string;
  description: string;
  project_type: ProjectType;
  status: ProjectStatus;
  start_date?: string;
  end_date?: string;
  budget_sek?: number;
  impact_radius_m: number;
  metadata?: Record<string, unknown>;
}

export interface PropertyProperties {
  id: string;
  designation: string;
  municipality: string;
  county: string;
  area_sqm: number;
  assessed_value_sek: number;
  property_type: PropertyType;
  owner_name: string;
  owner_org_number?: string;
  address: string;
  postal_code: string;
  city: string;
  building_year?: number;
  living_area_sqm?: number;
  zoning?: string;
  metadata?: Record<string, unknown>;
}

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

export type InfrastructureFeature = Feature<Geometry, InfrastructureProperties>;
export type PropertyFeature = Feature<Geometry, PropertyProperties>;
export type InfrastructureCollection = FeatureCollection<Geometry, InfrastructureProperties>;
export type PropertyCollection = FeatureCollection<Geometry, PropertyProperties>;

export type { FeatureCollection, Feature, Geometry };
