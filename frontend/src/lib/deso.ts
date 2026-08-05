import { DEMOGRAPHICS_METRICS } from '@/config/map';
import type { DemographicsMetric, DesoAreaCollection } from '@/domain';

/** Min/max för metriken i aktuell data — choroplethens färgdomän. */
export function metricDomain(
  data: DesoAreaCollection,
  metric: DemographicsMetric,
): [number, number] | null {
  const property = DEMOGRAPHICS_METRICS[metric].property;
  let min = Infinity;
  let max = -Infinity;
  for (const feature of data.features) {
    const value = (feature.properties as Record<string, unknown>)[property];
    if (typeof value === 'number' && Number.isFinite(value)) {
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
  }
  if (!Number.isFinite(min) || min === max) return null;
  return [min, max];
}
