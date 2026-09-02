/**
 * Kontraktstest: sökvägarna som klientkoden använder måste finnas i
 * backendens incheckade openapi.json. Typsystemet garanterar redan
 * schema.d.ts ↔ klientkod; det här testet garanterar openapi.json ↔
 * schema.d.ts inte har divergerat (CI regenererar dessutom typerna och
 * diffar). Det var exakt den här sortens drift som gjorde att den gamla
 * appen aldrig pratade med sin backend.
 */
import { describe, expect, it } from 'vitest';
import openapi from '../../../backend/openapi.json';
import {
  sampleDetailPlans,
  sampleImpactZones,
  sampleProjects,
  sampleProperties,
  sampleProximityScores,
  sampleReferenceDate,
} from '@/data/sampleData';

const USED_PATHS = [
  '/api/v1/health',
  '/api/v1/infrastructure/projects',
  '/api/v1/infrastructure/projects/{project_id}',
  '/api/v1/infrastructure/impact-zones',
  '/api/v1/infrastructure/sources',
  '/api/v1/infrastructure/sync/{source_name}',
  '/api/v1/infrastructure/sync/runs',
  '/api/v1/properties',
  '/api/v1/properties/{property_id}',
  '/api/v1/properties/{property_id}/nearby-projects',
  '/api/v1/analysis/proximity-scores',
  '/api/v1/planning/detail-plans',
  '/api/v1/planning/detail-plans/{plan_id}',
  '/api/v1/demographics/deso-areas',
  '/api/v1/demographics/deso-areas/lookup',
  '/api/v1/watches',
  '/api/v1/watches/events',
  '/api/v1/watches/{watch_id}',
  '/api/v1/watches/{watch_id}/mark-seen',
  '/api/v1/changes',
] as const;

describe('API-kontraktet', () => {
  const paths = Object.keys(openapi.paths);

  it.each(USED_PATHS)('backenden exponerar %s', (path) => {
    expect(paths).toContain(path);
  });

  it('statusenum i schemat matchar värdena i demodatat', () => {
    const schemaStatuses: string[] = openapi.components.schemas.ProjectStatus.enum;
    const sampleStatuses = new Set(
      sampleProjects.features.map((f) => f.properties.status).filter(Boolean),
    );
    for (const status of sampleStatuses) {
      expect(schemaStatuses).toContain(status);
    }
  });
});

describe('demodatat (genererat från backendens seed-fixturer)', () => {
  it('är giltiga FeatureCollections', () => {
    for (const collection of [sampleProjects, sampleProperties, sampleImpactZones]) {
      expect(collection.type).toBe('FeatureCollection');
      expect(collection.features.length).toBeGreaterThan(0);
    }
  });

  it('påverkanszoner finns även för linjeprojekt', () => {
    // Zonerna ska täcka ALLA projekt — den gamla klientbuffringen
    // hoppade över allt som inte var punkter.
    expect(sampleImpactZones.features).toHaveLength(sampleProjects.features.length);
    for (const zone of sampleImpactZones.features) {
      expect(['Polygon', 'MultiPolygon']).toContain(zone.geometry?.type);
    }
  });

  it('alla fastigheter har MultiPolygon-geometri och numeriskt id', () => {
    for (const feature of sampleProperties.features) {
      expect(feature.geometry?.type).toBe('MultiPolygon');
      expect(typeof feature.properties.id).toBe('number');
    }
  });

  it('demo-poängen är rankade och summerar sina bidrag', () => {
    const features = sampleProximityScores.features;
    expect(features.length).toBeGreaterThan(0);
    features.forEach((feature, index) => {
      expect(feature.properties.rank).toBe(index + 1);
      const contributions = feature.properties.contributions ?? [];
      const sum = contributions.reduce((acc, c) => acc + c.points, 0);
      expect(feature.properties.score).toBeCloseTo(sum, 1);
    });
  });

  it('har tidsstämplar före referensdatumet (driver "Nytt sedan senast" i demo-läge)', () => {
    expect(sampleReferenceDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    const reference = Date.parse(`${sampleReferenceDate}T00:00:00Z`);
    for (const collection of [sampleProjects, sampleDetailPlans, sampleProperties]) {
      for (const feature of collection.features) {
        const created = Date.parse(feature.properties.created_at ?? '');
        const updated = Date.parse(feature.properties.updated_at ?? '');
        expect(Number.isNaN(created)).toBe(false);
        expect(Number.isNaN(updated)).toBe(false);
        expect(created).toBeLessThanOrEqual(updated);
        // Strikt före: en demo-bevakning skapad "nu" får aldrig se dem som händelser
        expect(updated).toBeLessThan(reference);
      }
    }
  });
});
