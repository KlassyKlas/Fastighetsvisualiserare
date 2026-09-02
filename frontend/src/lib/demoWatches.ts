/**
 * Bevakade områden i demo-läget: lagras i webbläsarens localStorage
 * och utvärderas klientsidigt med samma semantik som backendens
 * app/services/watches.py (ST_Intersects + tidsjämförelse mot
 * last_seen_at). Mot riktig backend används API:t i stället.
 */
import type { MultiPolygon, Position } from 'geojson';
import { sampleDetailPlans, sampleProjects } from '@/data/sampleData';
import type {
  WatchedAreaCollection,
  WatchedAreaFeature,
  WatchEventKind,
  WatchEvents,
  WatchEventsResponse,
} from '@/domain';
import { geometryIntersectsMultiPolygon } from '@/lib/spatial';

const STORAGE_KEY = 'fastighetsvisualiserare.demoWatches';

interface StoredWatch {
  id: number;
  name: string;
  /** MultiPolygon-koordinater i WGS84 */
  coordinates: Position[][][];
  last_seen_at: string;
  created_at: string;
}

/** localStorage kan saknas (tester) eller kasta (privat läge) — då blir
 * demobevakningarna bara tomma i stället för att fälla appen. */
function readStore(): StoredWatch[] {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as StoredWatch[]) : [];
  } catch {
    return [];
  }
}

function writeStore(watches: StoredWatch[]): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(watches));
  } catch {
    // Skrivfel (kvot, privat läge) — bevakningen lever kvar tills omladdning.
  }
}

function toFeature(watch: StoredWatch): WatchedAreaFeature {
  return {
    type: 'Feature',
    geometry: { type: 'MultiPolygon', coordinates: watch.coordinates } satisfies MultiPolygon,
    properties: {
      id: watch.id,
      name: watch.name,
      last_seen_at: watch.last_seen_at,
      created_at: watch.created_at,
      updated_at: watch.created_at,
    },
  };
}

export function listDemoWatches(): WatchedAreaCollection {
  const features = readStore().map(toFeature);
  return {
    type: 'FeatureCollection',
    features,
    numberMatched: features.length,
    numberReturned: features.length,
  };
}

/** Spara en ritad polygon (yttre ring). Ringen sluts om den inte redan är sluten. */
export function createDemoWatch(name: string, ring: Position[]): WatchedAreaFeature {
  const closed =
    ring.length > 0 &&
    (ring[0][0] !== ring[ring.length - 1][0] || ring[0][1] !== ring[ring.length - 1][1])
      ? [...ring, ring[0]]
      : ring;
  const now = new Date().toISOString();
  const watch: StoredWatch = {
    id: Date.now(),
    name,
    coordinates: [[closed]],
    // Samma semantik som backend: en ny bevakning börjar "ren".
    last_seen_at: now,
    created_at: now,
  };
  writeStore([...readStore(), watch]);
  return toFeature(watch);
}

export function deleteDemoWatch(id: number): void {
  writeStore(readStore().filter((watch) => watch.id !== id));
}

export function markDemoWatchSeen(id: number): void {
  writeStore(
    readStore().map((watch) =>
      watch.id === id ? { ...watch, last_seen_at: new Date().toISOString() } : watch,
    ),
  );
}

/** Spegling av backendens classify_event — nytt vinner över ändrat. */
export function classifyDemoEvent(
  createdAt: string | null | undefined,
  updatedAt: string | null | undefined,
  seenAt: string,
): WatchEventKind | null {
  if (createdAt != null && createdAt > seenAt) return 'nytt';
  if (updatedAt != null && updatedAt > seenAt) return 'ändrat';
  return null;
}

/**
 * Händelser och innehållsräkning för demobevakningarna, beräknat mot
 * exempeldatat. Demodatats tidsstämplar är illustrativa och ligger före
 * referensdatumet (sampleReferenceDate); en bevakning skapas med
 * last_seen_at = nu, så i praktiken visas räkningarna medan
 * händelselistorna förblir tomma. Panelen "Nytt sedan senast" räknar i
 * stället mot referensdatumet (lib/demoChanges) och visar dem.
 */
export function demoWatchEvents(): WatchEventsResponse {
  const watches: WatchEvents[] = readStore().map((watch) => {
    const projects = sampleProjects.features.filter((feature) =>
      geometryIntersectsMultiPolygon(feature.geometry, watch.coordinates),
    );
    const plans = sampleDetailPlans.features.filter((feature) =>
      geometryIntersectsMultiPolygon(feature.geometry, watch.coordinates),
    );

    const projectEvents = projects.flatMap((feature) => {
      const kind = classifyDemoEvent(
        feature.properties.created_at,
        feature.properties.updated_at,
        watch.last_seen_at,
      );
      return kind ? [{ event_kind: kind, project: feature }] : [];
    });
    const planEvents = plans.flatMap((feature) => {
      const kind = classifyDemoEvent(
        feature.properties.created_at,
        feature.properties.updated_at,
        watch.last_seen_at,
      );
      return kind ? [{ event_kind: kind, plan: feature }] : [];
    });

    return {
      watch_id: watch.id,
      watch_name: watch.name,
      last_seen_at: watch.last_seen_at,
      project_count: projects.length,
      plan_count: plans.length,
      project_events: projectEvents,
      plan_events: planEvents,
    } as unknown as WatchEvents;
  });

  const totalEvents = watches.reduce(
    (sum, watch) => sum + (watch.project_events?.length ?? 0) + (watch.plan_events?.length ?? 0),
    0,
  );
  return { watches, total_events: totalEvents };
}
