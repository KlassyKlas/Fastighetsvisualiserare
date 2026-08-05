import type { FeatureCollection } from 'geojson';
import type { FilterState } from '@/types';
import { sampleInfrastructure, sampleProperties } from '@/data/sampleData';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function buildQueryParams(filters?: Partial<FilterState>): string {
  if (!filters) return '';
  const params = new URLSearchParams();
  if (filters.statuses?.length) {
    filters.statuses.forEach((s) => params.append('status', s));
  }
  if (filters.projectTypes?.length) {
    filters.projectTypes.forEach((t) => params.append('project_type', t));
  }
  if (filters.municipalities?.length) {
    filters.municipalities.forEach((m) => params.append('municipality', m));
  }
  if (filters.minValue != null) {
    params.set('min_value', String(filters.minValue));
  }
  if (filters.maxValue != null) {
    params.set('max_value', String(filters.maxValue));
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function fetchInfrastructureProjects(
  filters?: Partial<FilterState>,
): Promise<FeatureCollection> {
  try {
    const response = await fetch(
      `${API_URL}/api/infrastructure/geojson${buildQueryParams(filters)}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch {
    console.warn('Backend ej tillgänglig, använder exempeldata för infrastruktur');
    return sampleInfrastructure;
  }
}

export async function fetchProperties(
  filters?: Partial<FilterState>,
): Promise<FeatureCollection> {
  try {
    const response = await fetch(
      `${API_URL}/api/properties/geojson${buildQueryParams(filters)}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch {
    console.warn('Backend ej tillgänglig, använder exempeldata för fastigheter');
    return sampleProperties;
  }
}

export async function searchProperties(query: string): Promise<FeatureCollection> {
  try {
    const response = await fetch(
      `${API_URL}/api/properties/search?q=${encodeURIComponent(query)}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch {
    console.warn('Backend ej tillgänglig för sökning');
    return { type: 'FeatureCollection', features: [] };
  }
}

export async function syncTrafikverket(): Promise<{ count: number }> {
  const response = await fetch(`${API_URL}/api/infrastructure/sync`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}
