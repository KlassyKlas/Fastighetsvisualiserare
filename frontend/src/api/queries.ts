/**
 * TanStack Query-fabriker för API:t.
 *
 * Demo-läge: när backend inte nås faller kartans queries tillbaka på
 * exempeldata och flaggar det SYNLIGT via uiStore.demoMode — aldrig tyst.
 * "Backend nås inte" betyder antingen nätverksfel (fetch kastar
 * TypeError; händer bara vid absolut VITE_API_URL) eller gateway-fel
 * 502/503/504 från proxyn (Vites dev-proxy respektive nginx svarar så
 * när backend är nere — fetch lyckas då och kastar ingenting).
 * Övriga HTTP-fel kastas vidare och visas i ErrorBanner.
 */
import { keepPreviousData, queryOptions } from '@tanstack/react-query';
import { client } from '@/api/client';
import { SOURCE_LABELS } from '@/config/map';
import {
  sampleDesoAreas,
  sampleDetailPlans,
  sampleImpactZones,
  sampleProjects,
  sampleProperties,
  sampleProximityScores,
} from '@/data/sampleData';
import { applyImpactZoneFilters, applyProjectFilters, applyPropertyFilters } from '@/lib/filters';
import { useUiStore } from '@/store/uiStore';
import type {
  DesoAreaCollection,
  DesoAreaFeature,
  DetailPlanCollection,
  FilterState,
  ImpactZoneCollection,
  NearbyProjectsResponse,
  ProjectCollection,
  PropertyCollection,
  ProximityScoresCollection,
  SyncResult,
} from '@/domain';

/** Servern tillåter max 2000 — begär taket så att inget trunkeras i onödan. */
const LIST_LIMIT = 2000;

const GATEWAY_STATUSES = new Set([502, 503, 504]);

class BackendUnreachableError extends Error {}

function isBackendUnreachable(error: unknown): boolean {
  return error instanceof TypeError || error instanceof BackendUnreachableError;
}

/**
 * Gemensam svarskontroll. Viktigt: kontrollera response.status, inte bara
 * `error` — Vite-proxyn svarar 502 med TOM kropp, vilket gör openapi-fetch-
 * felet till '' (falsy) och ett naivt `if (error) throw` släpper igenom det.
 */
function ensureOk(error: unknown, response: Response): void {
  if (GATEWAY_STATUSES.has(response.status)) {
    throw new BackendUnreachableError(`HTTP ${response.status}`);
  }
  if (!response.ok) {
    throw error ?? new Error(`HTTP ${response.status}`);
  }
}

function markDemoMode(demo: boolean): void {
  const state = useUiStore.getState();
  if (state.demoMode !== demo) {
    state.setDemoMode(demo);
  }
}

function nonEmpty<T>(values: T[]): T[] | undefined {
  return values.length > 0 ? values : undefined;
}

/** I demo-läge provas backend igen med jämna mellanrum så att appen
 * automatiskt går över till riktig data när den kommer tillbaka. */
function retryWhileDemo(): number | false {
  return useUiStore.getState().demoMode ? 15_000 : false;
}

/**
 * Querynycklarna innehåller BARA de filterfält som respektive endpoint
 * faktiskt använder — att nyckla på hela FilterState skulle ge en ny
 * cachepost (och en onödig identisk request) varje gång ett irrelevant
 * fält ändras, t.ex. varje steg på tidsreglaget.
 */
export function projectsQuery(filters: FilterState) {
  return queryOptions({
    queryKey: [
      'projects',
      { statuses: filters.statuses, projectTypes: filters.projectTypes, year: filters.year },
    ],
    queryFn: async ({ signal }): Promise<ProjectCollection> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/infrastructure/projects', {
          params: {
            query: {
              status: nonEmpty(filters.statuses),
              project_type: nonEmpty(filters.projectTypes),
              year: filters.year ?? undefined,
              limit: LIST_LIMIT,
            },
          },
          signal,
        });
        ensureOk(error, response);
        markDemoMode(false);
        return data as unknown as ProjectCollection;
      } catch (error) {
        if (isBackendUnreachable(error) && !signal.aborted) {
          markDemoMode(true);
          return applyProjectFilters(sampleProjects, filters);
        }
        throw error;
      }
    },
    staleTime: 60_000,
    refetchInterval: retryWhileDemo,
  });
}

export function propertiesQuery(filters: FilterState) {
  return queryOptions({
    queryKey: [
      'properties',
      {
        municipalities: filters.municipalities,
        minValue: filters.minValue,
        maxValue: filters.maxValue,
      },
    ],
    queryFn: async ({ signal }): Promise<PropertyCollection> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/properties', {
          params: {
            query: {
              municipality: nonEmpty(filters.municipalities),
              min_value: filters.minValue ?? undefined,
              max_value: filters.maxValue ?? undefined,
              limit: LIST_LIMIT,
            },
          },
          signal,
        });
        ensureOk(error, response);
        markDemoMode(false);
        return data as unknown as PropertyCollection;
      } catch (error) {
        if (isBackendUnreachable(error) && !signal.aborted) {
          markDemoMode(true);
          return applyPropertyFilters(sampleProperties, filters);
        }
        throw error;
      }
    },
    staleTime: 60_000,
    refetchInterval: retryWhileDemo,
  });
}

export function impactZonesQuery(filters: FilterState) {
  return queryOptions({
    queryKey: [
      'impact-zones',
      { statuses: filters.statuses, projectTypes: filters.projectTypes, year: filters.year },
    ],
    queryFn: async ({ signal }): Promise<ImpactZoneCollection> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/infrastructure/impact-zones', {
          params: {
            query: {
              status: nonEmpty(filters.statuses),
              project_type: nonEmpty(filters.projectTypes),
              year: filters.year ?? undefined,
            },
          },
          signal,
        });
        ensureOk(error, response);
        markDemoMode(false);
        return data as unknown as ImpactZoneCollection;
      } catch (error) {
        if (isBackendUnreachable(error) && !signal.aborted) {
          markDemoMode(true);
          return applyImpactZoneFilters(sampleImpactZones, filters);
        }
        throw error;
      }
    },
    staleTime: 60_000,
    refetchInterval: retryWhileDemo,
  });
}

export function proximityScoresQuery(filters: FilterState) {
  return queryOptions({
    queryKey: [
      'proximity-scores',
      { statuses: filters.statuses, projectTypes: filters.projectTypes, year: filters.year },
    ],
    queryFn: async ({ signal }): Promise<ProximityScoresCollection> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/analysis/proximity-scores', {
          params: {
            query: {
              status: nonEmpty(filters.statuses),
              project_type: nonEmpty(filters.projectTypes),
              year: filters.year ?? undefined,
              limit: LIST_LIMIT,
            },
          },
          signal,
        });
        ensureOk(error, response);
        markDemoMode(false);
        return data as unknown as ProximityScoresCollection;
      } catch (error) {
        if (isBackendUnreachable(error) && !signal.aborted) {
          markDemoMode(true);
          // Demo-poängen är förberäknade för hela projektmängden —
          // filter påverkar dem inte (illustrativt läge).
          return sampleProximityScores;
        }
        throw error;
      }
    },
    staleTime: 60_000,
    refetchInterval: retryWhileDemo,
    // Behåll förra svaret medan nytt hämtas — annars flimrar kartan
    // mellan typ- och poängfärger vid varje filterändring.
    placeholderData: keepPreviousData,
  });
}

/**
 * Detaljplaner och DeSO-områden hämtas per kartvy (bbox "väst,syd,öst,norr")
 * — nationella datamängder är för stora att hämta i sin helhet.
 * Demodatat är litet och returneras ofiltrerat.
 */
export function detailPlansQuery(bbox: string | null) {
  return queryOptions({
    queryKey: ['detail-plans', bbox],
    queryFn: async ({ signal }): Promise<DetailPlanCollection> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/planning/detail-plans', {
          params: { query: { bbox: bbox ?? undefined, limit: LIST_LIMIT } },
          signal,
        });
        ensureOk(error, response);
        markDemoMode(false);
        return data as unknown as DetailPlanCollection;
      } catch (error) {
        if (isBackendUnreachable(error) && !signal.aborted) {
          markDemoMode(true);
          return sampleDetailPlans;
        }
        throw error;
      }
    },
    staleTime: 60_000,
    refetchInterval: retryWhileDemo,
    // Behåll förra svaret medan nästa kartvy hämtas — annars blinkar lagret.
    placeholderData: keepPreviousData,
  });
}

export function desoAreasQuery(bbox: string | null) {
  return queryOptions({
    queryKey: ['deso-areas', bbox],
    queryFn: async ({ signal }): Promise<DesoAreaCollection> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/demographics/deso-areas', {
          params: { query: { bbox: bbox ?? undefined, limit: LIST_LIMIT } },
          signal,
        });
        ensureOk(error, response);
        markDemoMode(false);
        return data as unknown as DesoAreaCollection;
      } catch (error) {
        if (isBackendUnreachable(error) && !signal.aborted) {
          markDemoMode(true);
          return sampleDesoAreas;
        }
        throw error;
      }
    },
    staleTime: 60_000,
    refetchInterval: retryWhileDemo,
    placeholderData: keepPreviousData,
  });
}

/** DeSO-området som innehåller punkten — kräver backend (PostGIS-uppslag). */
export function desoLookupQuery(longitude: number, latitude: number) {
  return queryOptions({
    queryKey: ['deso-lookup', { longitude, latitude }],
    queryFn: async ({ signal }): Promise<DesoAreaFeature> => {
      const { data, error, response } = await client.GET(
        '/api/v1/demographics/deso-areas/lookup',
        {
          params: { query: { lng: longitude, lat: latitude } },
          signal,
        },
      );
      ensureOk(error, response);
      return data as unknown as DesoAreaFeature;
    },
    staleTime: 5 * 60_000,
    // 404 = ingen DeSO-yta synkad för punkten — omförsök hjälper inte.
    retry: false,
  });
}

export function nearbyProjectsQuery(propertyId: number, maxDistanceM = 5000) {
  return queryOptions({
    queryKey: ['nearby-projects', propertyId, maxDistanceM],
    queryFn: async ({ signal }): Promise<NearbyProjectsResponse> => {
      const { data, error, response } = await client.GET(
        '/api/v1/properties/{property_id}/nearby-projects',
        {
          params: {
            path: { property_id: propertyId },
            query: { max_distance_m: maxDistanceM },
          },
          signal,
        },
      );
      ensureOk(error, response);
      return data as NearbyProjectsResponse;
    },
    staleTime: 60_000,
  });
}

/** Utan backend (demo-läge, laddning, fel) visas de kända källorna så
 * att synk-sektionen aldrig blir tomt tyst. "manual" är ingen extern
 * källa. */
export const FALLBACK_SOURCES: Record<string, string> = Object.fromEntries(
  Object.entries(SOURCE_LABELS).filter(([name]) => name !== 'manual'),
);

/** Registrerade datakällor (källnamn → visningsnamn) — driver synkknapparna. */
export function sourcesQuery() {
  return queryOptions({
    queryKey: ['sources'],
    queryFn: async ({ signal }): Promise<Record<string, string>> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/infrastructure/sources', {
          signal,
        });
        ensureOk(error, response);
        markDemoMode(false);
        return data as Record<string, string>;
      } catch (error) {
        if (isBackendUnreachable(error) && !signal.aborted) {
          markDemoMode(true);
          return FALLBACK_SOURCES;
        }
        throw error;
      }
    },
    staleTime: 5 * 60_000,
    refetchInterval: retryWhileDemo,
  });
}

export async function syncSource(sourceName: string): Promise<SyncResult> {
  const { data, error, response } = await client.POST('/api/v1/infrastructure/sync/{source_name}', {
    params: { path: { source_name: sourceName } },
  });
  ensureOk(error, response);
  return data as SyncResult;
}
