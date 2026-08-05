import { describe, expect, it } from 'vitest';
import type { DesoAreaCollection } from '@/domain';
import { metricDomain } from './deso';

function collection(populations: (number | null)[]): DesoAreaCollection {
  return {
    type: 'FeatureCollection',
    features: populations.map((population, index) => ({
      type: 'Feature',
      geometry: null as never,
      properties: { id: index + 1, deso_code: `0180C${index}`, population },
    })),
  } as unknown as DesoAreaCollection;
}

describe('metricDomain', () => {
  it('ger min och max och ignorerar null-värden', () => {
    expect(metricDomain(collection([1200, null, 3400, 800]), 'population')).toEqual([800, 3400]);
  });

  it('null när alla värden saknas eller är lika', () => {
    expect(metricDomain(collection([null, null]), 'population')).toBeNull();
    expect(metricDomain(collection([1000, 1000]), 'population')).toBeNull();
  });
});
