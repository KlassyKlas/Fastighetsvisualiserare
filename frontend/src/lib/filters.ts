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

/**
 * Projektet är aktivt någon gång under året. Okända datum utesluter
 * inte — samma semantik som backendens year-filter. Datumen är
 * ISO-strängar (ÅÅÅÅ-MM-DD) så strängjämförelse är korrekt.
 */
function activeInYear(
  startDate: string | null | undefined,
  endDate: string | null | undefined,
  year: number,
): boolean {
  const startsInTime = startDate == null || startDate <= `${year}-12-31`;
  const endsInTime = endDate == null || endDate >= `${year}-01-01`;
  return startsInTime && endsInTime;
}

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
  if (filters.year != null) {
    const year = filters.year;
    features = features.filter((f) =>
      activeInYear(f.properties.start_date, f.properties.end_date, year),
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
  if (filters.year != null) {
    const year = filters.year;
    features = features.filter((f) =>
      activeInYear(f.properties.start_date, f.properties.end_date, year),
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
  // Som backend: fastigheter utan taxeringsvärde exkluderas när ett
  // värdefilter är aktivt (SQL-jämförelse mot NULL är aldrig sann)
  if (filters.minValue != null) {
    features = features.filter(
      (f) =>
        f.properties.assessed_value_sek != null &&
        f.properties.assessed_value_sek >= (filters.minValue ?? 0),
    );
  }
  if (filters.maxValue != null) {
    features = features.filter(
      (f) =>
        f.properties.assessed_value_sek != null &&
        f.properties.assessed_value_sek <= (filters.maxValue ?? Infinity),
    );
  }

  return {
    ...collection,
    features,
    numberMatched: features.length,
    numberReturned: features.length,
  };
}
