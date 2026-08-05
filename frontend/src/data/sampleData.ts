/**
 * Demodata för läget när backend inte nås.
 *
 * sampleData.json GENERERAS från backendens seed-fixturer med
 * `uv run python -m scripts.export_sample_data` och har därmed exakt
 * samma form som API:ts svar. Redigera aldrig JSON-filen för hand.
 */
import type {
  ImpactZoneCollection,
  ProjectCollection,
  PropertyCollection,
  ProximityScoresCollection,
} from '@/domain';
import raw from './sampleData.json';

interface SampleData {
  properties: PropertyCollection;
  infrastructureProjects: ProjectCollection;
  impactZones: ImpactZoneCollection;
  proximityScores: ProximityScoresCollection;
}

const data = raw as unknown as SampleData;

export const sampleProperties = data.properties;
export const sampleProjects = data.infrastructureProjects;
export const sampleImpactZones = data.impactZones;
export const sampleProximityScores = data.proximityScores;
