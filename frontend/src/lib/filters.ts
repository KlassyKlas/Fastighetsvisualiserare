/**
 * Klientsidig filtrering — används enbart i demo-läget. Mot riktig
 * backend skickas filtren som query-parametrar och utvärderas i databasen.
 * Semantiken här ska spegla backendens (app/services/*.py).
 */
import type {
  FilterState,
  ImpactZoneCollection,
  ProjectCollection,
  PropertyCollection,
} from '@/domain';

export function applyProjectFilters(
  collection: ProjectCollection,
  filters: FilterState,
): ProjectCollection {
  let features = collection.features;

  if (filters.statuses.length > 0) {
    features = features.filter(
      (f) => f.properties.status != null && filters.statuses.includes(f.properties.status),
    );
  }
  if (filters.projectTypes.length > 0) {
    features = features.filter(
      (f) =>
        f.properties.project_type != null &&
        filters.projectTypes.includes(f.properties.project_type),
    );
  }

  return {
    ...collection,
    features,
    numberMatched: features.length,
    numberReturned: features.length,
  };
}

export function applyImpactZoneFilters(
  collection: ImpactZoneCollection,
  filters: FilterState,
): ImpactZoneCollection {
  let features = collection.features;

  if (filters.statuses.length > 0) {
    features = features.filter(
      (f) => f.properties.status != null && filters.statuses.includes(f.properties.status),
    );
  }
  if (filters.projectTypes.length > 0) {
    features = features.filter(
      (f) =>
        f.properties.project_type != null &&
        filters.projectTypes.includes(f.properties.project_type),
    );
  }

  return { ...collection, features };
}

export function applyPropertyFilters(
  collection: PropertyCollection,
  filters: FilterState,
): PropertyCollection {
  let features = collection.features;

  if (filters.municipalities.length > 0) {
    features = features.filter(
      (f) =>
        f.properties.municipality != null &&
        filters.municipalities.includes(f.properties.municipality),
    );
  }
  if (filters.minValue != null) {
    features = features.filter(
      (f) => (f.properties.assessed_value_sek ?? 0) >= (filters.minValue ?? 0),
    );
  }
  if (filters.maxValue != null) {
    features = features.filter(
      (f) => (f.properties.assessed_value_sek ?? 0) <= (filters.maxValue ?? Infinity),
    );
  }

  return {
    ...collection,
    features,
    numberMatched: features.length,
    numberReturned: features.length,
  };
}
