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
import { queryOptions } from '@tanstack/react-query';
import { client } from '@/api/client';
import {
  sampleImpactZones,
  sampleProjects,
  sampleProperties,
  sampleProximityScores,
} from '@/data/sampleData';
import { applyImpactZoneFilters, applyProjectFilters, applyPropertyFilters } from '@/lib/filters';
import { useUiStore } from '@/store/uiStore';
import type {
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

export function projectsQuery(filters: FilterState) {
  return queryOptions({
    queryKey: ['projects', filters],
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
    queryKey: ['properties', filters],
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
    queryKey: ['impact-zones', filters],
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
    queryKey: ['proximity-scores', filters],
    queryFn: async ({ signal }): Promise<ProximityScoresCollection> => {
      try {
        const { data, error, response } = await client.GET('/api/v1/analysis/proximity-scores', {
          params: {
            query: {
              status: nonEmpty(filters.statuses),
              project_type: nonEmpty(filters.projectTypes),
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

export async function syncTrafikverket(): Promise<SyncResult> {
  const { data, error, response } = await client.POST('/api/v1/infrastructure/sync/{source_name}', {
    params: { path: { source_name: 'trafikverket' } },
  });
  ensureOk(error, response);
  return data as SyncResult;
}
