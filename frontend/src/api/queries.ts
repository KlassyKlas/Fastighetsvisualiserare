/**
 * TanStack Query-fabriker för API:t.
 *
 * Demo-läge: om backend inte nås alls (nätverksfel) faller queries
 * tillbaka på exempeldata och flaggar det SYNLIGT via uiStore.demoMode —
 * aldrig tyst. HTTP-fel (backend uppe men svarar fel) kastas vidare
 * och visas som fel.
 */
import { queryOptions } from '@tanstack/react-query';
import { client } from '@/api/client';
import { sampleImpactZones, sampleProjects, sampleProperties } from '@/data/sampleData';
import { applyImpactZoneFilters, applyProjectFilters, applyPropertyFilters } from '@/lib/filters';
import { useUiStore } from '@/store/uiStore';
import type {
  FilterState,
  ImpactZoneCollection,
  NearbyProjectsResponse,
  ProjectCollection,
  PropertyCollection,
  SyncResult,
} from '@/domain';

/** Nätverksfel (fetch kastar TypeError när servern inte nås). */
function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError;
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

export function projectsQuery(filters: FilterState) {
  return queryOptions({
    queryKey: ['projects', filters],
    queryFn: async (): Promise<ProjectCollection> => {
      try {
        const { data, error } = await client.GET('/api/v1/infrastructure/projects', {
          params: {
            query: {
              status: nonEmpty(filters.statuses),
              project_type: nonEmpty(filters.projectTypes),
            },
          },
        });
        if (error) throw error;
        markDemoMode(false);
        return data as unknown as ProjectCollection;
      } catch (error) {
        if (isNetworkError(error)) {
          markDemoMode(true);
          return applyProjectFilters(sampleProjects, filters);
        }
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function propertiesQuery(filters: FilterState) {
  return queryOptions({
    queryKey: ['properties', filters],
    queryFn: async (): Promise<PropertyCollection> => {
      try {
        const { data, error } = await client.GET('/api/v1/properties', {
          params: {
            query: {
              municipality: nonEmpty(filters.municipalities),
              min_value: filters.minValue ?? undefined,
              max_value: filters.maxValue ?? undefined,
            },
          },
        });
        if (error) throw error;
        markDemoMode(false);
        return data as unknown as PropertyCollection;
      } catch (error) {
        if (isNetworkError(error)) {
          markDemoMode(true);
          return applyPropertyFilters(sampleProperties, filters);
        }
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function impactZonesQuery(filters: FilterState) {
  return queryOptions({
    queryKey: ['impact-zones', filters],
    queryFn: async (): Promise<ImpactZoneCollection> => {
      try {
        const { data, error } = await client.GET('/api/v1/infrastructure/impact-zones', {
          params: {
            query: {
              status: nonEmpty(filters.statuses),
              project_type: nonEmpty(filters.projectTypes),
            },
          },
        });
        if (error) throw error;
        return data as unknown as ImpactZoneCollection;
      } catch (error) {
        if (isNetworkError(error)) {
          return applyImpactZoneFilters(sampleImpactZones, filters);
        }
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function nearbyProjectsQuery(propertyId: number, maxDistanceM = 5000) {
  return queryOptions({
    queryKey: ['nearby-projects', propertyId, maxDistanceM],
    queryFn: async (): Promise<NearbyProjectsResponse> => {
      const { data, error } = await client.GET('/api/v1/properties/{property_id}/nearby-projects', {
        params: {
          path: { property_id: propertyId },
          query: { max_distance_m: maxDistanceM },
        },
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export async function syncTrafikverket(): Promise<SyncResult> {
  const { data, error } = await client.POST('/api/v1/infrastructure/sync/{source_name}', {
    params: { path: { source_name: 'trafikverket' } },
  });
  if (error) throw error;
  return data;
}
