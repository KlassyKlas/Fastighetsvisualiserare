import { describe, expect, it } from 'vitest';
import { sampleProjects, sampleProperties } from '@/data/sampleData';
import { EMPTY_FILTERS } from '@/domain';
import { applyProjectFilters, applyPropertyFilters } from './filters';

describe('applyProjectFilters', () => {
  it('utan filter returneras allt', () => {
    const result = applyProjectFilters(sampleProjects, EMPTY_FILTERS);
    expect(result.features).toHaveLength(sampleProjects.features.length);
  });

  it('filtrerar på status', () => {
    const result = applyProjectFilters(sampleProjects, {
      ...EMPTY_FILTERS,
      statuses: ['planerad'],
    });
    expect(result.features.length).toBeGreaterThan(0);
    expect(result.features.every((f) => f.properties.status === 'planerad')).toBe(true);
    expect(result.numberMatched).toBe(result.features.length);
  });

  it('filtrerar på flera statusar samtidigt', () => {
    const result = applyProjectFilters(sampleProjects, {
      ...EMPTY_FILTERS,
      statuses: ['planerad', 'avslutad'],
    });
    expect(result.features.every((f) => f.properties.status !== 'pågående')).toBe(true);
  });

  it('filtrerar på projekttyp', () => {
    const result = applyProjectFilters(sampleProjects, {
      ...EMPTY_FILTERS,
      projectTypes: ['järnväg'],
    });
    expect(result.features.length).toBeGreaterThan(0);
    expect(result.features.every((f) => f.properties.project_type === 'järnväg')).toBe(true);
  });

  it('filtrerar på aktivt år — samma semantik som backend', () => {
    const result = applyProjectFilters(sampleProjects, { ...EMPTY_FILTERS, year: 2012 });
    const names = result.features.map((f) => f.properties.name);
    expect(names).toContain('Citybanan'); // aktiv 2009–2017
    expect(names).not.toContain('Tvärförbindelse Södertörn'); // 2025–2032
  });
});

describe('applyPropertyFilters', () => {
  it('filtrerar på kommun', () => {
    const result = applyPropertyFilters(sampleProperties, {
      ...EMPTY_FILTERS,
      municipalities: ['Solna'],
    });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties.designation).toBe('Solna Centrum 2:1');
  });

  it('filtrerar på exakt ägarnamn — samma semantik som backend', () => {
    const result = applyPropertyFilters(sampleProperties, {
      ...EMPTY_FILTERS,
      owner: 'Unibail-Rodamco-Westfield',
    });
    expect(result.features).toHaveLength(2);
    expect(result.numberMatched).toBe(2);
    expect(
      result.features.every((f) => f.properties.owner_name === 'Unibail-Rodamco-Westfield'),
    ).toBe(true);

    // Ingen fritext eller normalisering: delsträng och annan skiftning matchar inte
    expect(
      applyPropertyFilters(sampleProperties, { ...EMPTY_FILTERS, owner: 'Unibail' }).features,
    ).toHaveLength(0);
    expect(
      applyPropertyFilters(sampleProperties, { ...EMPTY_FILTERS, owner: 'vasakronan ab' }).features,
    ).toHaveLength(0);
  });

  it('ägarfiltret kombineras med kommunfiltret', () => {
    const result = applyPropertyFilters(sampleProperties, {
      ...EMPTY_FILTERS,
      owner: 'Unibail-Rodamco-Westfield',
      municipalities: ['Täby'],
    });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties.municipality).toBe('Täby');
  });

  it('filtrerar på värdeintervall', () => {
    const result = applyPropertyFilters(sampleProperties, {
      ...EMPTY_FILTERS,
      minValue: 100_000_000,
      maxValue: 300_000_000,
    });
    expect(result.features.length).toBeGreaterThan(0);
    for (const feature of result.features) {
      const value = feature.properties.assessed_value_sek ?? 0;
      expect(value).toBeGreaterThanOrEqual(100_000_000);
      expect(value).toBeLessThanOrEqual(300_000_000);
    }
  });
});
