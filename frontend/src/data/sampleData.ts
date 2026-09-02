/**
 * Demodata för läget när backend inte nås.
 *
 * sampleData.json GENERERAS från backendens seed-fixturer med
 * `uv run python -m scripts.export_sample_data` och har därmed exakt
 * samma form som API:ts svar. Redigera aldrig JSON-filen för hand.
 */
import type {
  DesoAreaCollection,
  DetailPlanCollection,
  ImpactZoneCollection,
  ProjectCollection,
  PropertyCollection,
  ProximityScoresCollection,
} from '@/domain';
import raw from './sampleData.json';

interface SampleData {
  /** Datumet (ÅÅÅÅ-MM-DD) som demodatats tidsstämplar är relativa till. */
  referenceDate: string;
  properties: PropertyCollection;
  infrastructureProjects: ProjectCollection;
  impactZones: ImpactZoneCollection;
  proximityScores: ProximityScoresCollection;
  detailPlans: DetailPlanCollection;
  desoAreas: DesoAreaCollection;
}

const data = raw as unknown as SampleData;

/**
 * Demodatats "nu". Tidsstämplarna (created_at/updated_at) i exempeldatat
 * är illustrativa och ligger strax före detta datum, så att "Nytt sedan
 * senast" har något att visa i demo-läge.
 */
export const sampleReferenceDate: string = data.referenceDate;
export const sampleProperties = data.properties;
export const sampleProjects = data.infrastructureProjects;
export const sampleImpactZones = data.impactZones;
export const sampleProximityScores = data.proximityScores;
export const sampleDetailPlans = data.detailPlans;
export const sampleDesoAreas = data.desoAreas;
