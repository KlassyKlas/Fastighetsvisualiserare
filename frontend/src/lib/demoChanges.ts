/**
 * "Nytt sedan senast" i demo-läget: beräknas klientsidigt mot
 * exempeldatat med samma semantik som backendens
 * app/services/changes.py — WHERE created_at > since OR updated_at >
 * since, sorterat updated_at DESC, id DESC, projekt fyller limit först
 * och detaljplaner får resten, medan räkningarna alltid gäller hela
 * urvalet. Mot riktig backend används API:t i stället.
 */
import { sampleDetailPlans, sampleProjects } from '@/data/sampleData';
import type {
  ChangesResponse,
  DetailPlanFeature,
  DetailPlanWatchEvent,
  ProjectFeature,
  ProjectWatchEvent,
  WatchEventKind,
} from '@/domain';
import { classifyDemoEvent } from '@/lib/demoWatches';

interface Stamped {
  properties: {
    id: number;
    created_at?: string | null;
    updated_at?: string | null;
  };
}

/**
 * Normalisera till toISOString-form så att strängjämförelsen i
 * classifyDemoEvent blir korrekt även om klienten skrev "…Z" och
 * demodatat "…00Z" utan millisekunder (samma instant, olika text).
 */
function toIso(value: string | null | undefined): string | null {
  if (value == null) return null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : new Date(ms).toISOString();
}

/**
 * Backendens textform för samma instant: Pydantic skriver "…T08:00:00Z"
 * utan millisekunddel vid hela sekunder, medan toISOString alltid ger
 * "…T08:00:00.000Z". Svarets `since` ekas i backendens form så att demo
 * och live ger identisk text.
 */
function toApiIso(iso: string): string {
  return iso.replace(/\.000Z$/, 'Z');
}

interface Classified<T> {
  feature: T;
  kind: WatchEventKind;
}

/** Händelserna i ett lager, i backendens ordning (updated_at desc, id desc). */
function classifyLayer<T extends Stamped>(features: T[], since: string): Classified<T>[] {
  const events: Classified<T>[] = [];
  for (const feature of features) {
    const kind = classifyDemoEvent(
      toIso(feature.properties.created_at),
      toIso(feature.properties.updated_at),
      since,
    );
    if (kind) events.push({ feature, kind });
  }
  return events.sort((a, b) => {
    const byUpdated = (toIso(b.feature.properties.updated_at) ?? '').localeCompare(
      toIso(a.feature.properties.updated_at) ?? '',
    );
    return byUpdated !== 0 ? byUpdated : b.feature.properties.id - a.feature.properties.id;
  });
}

function countKinds(events: Classified<unknown>[]): { fresh: number; changed: number } {
  let fresh = 0;
  let changed = 0;
  for (const event of events) {
    if (event.kind === 'nytt') fresh += 1;
    else changed += 1;
  }
  return { fresh, changed };
}

/** Svaret för en period utan händelser — samma form som backend ger. */
function emptyChanges(since: string): ChangesResponse {
  return {
    since,
    project_events: [],
    plan_events: [],
    project_new: 0,
    project_changed: 0,
    plan_new: 0,
    plan_changed: 0,
    total_events: 0,
    truncated: false,
  };
}

export function demoChanges(since: string, limit = 200): ChangesResponse {
  // Otolkbart since: backend hade svarat 422, men demo-läget ska inte
  // krascha. Råsträngen får INTE skickas vidare till strängjämförelsen —
  // t.ex. "" sorterar före varje tidsstämpel och hade gjort allt "nytt".
  const sinceIso = toIso(since);
  if (sinceIso == null) return emptyChanges(since);

  const projectEvents = classifyLayer<ProjectFeature>(sampleProjects.features, sinceIso);
  const planEvents = classifyLayer<DetailPlanFeature>(sampleDetailPlans.features, sinceIso);

  const projects = projectEvents.slice(0, limit);
  const remaining = Math.max(0, limit - projects.length);
  const plans = planEvents.slice(0, remaining);
  const truncated = projectEvents.length > limit || planEvents.length > remaining;

  const projectCounts = countKinds(projectEvents);
  const planCounts = countKinds(planEvents);

  return {
    since: toApiIso(sinceIso),
    // Kontraktets feature-typer är löst typade GeoJSON-objekt; demodatat
    // har redan API:ts form (genererat från seed-fixturerna).
    project_events: projects.map(
      (event) =>
        ({ event_kind: event.kind, project: event.feature }) as unknown as ProjectWatchEvent,
    ),
    plan_events: plans.map(
      (event) =>
        ({ event_kind: event.kind, plan: event.feature }) as unknown as DetailPlanWatchEvent,
    ),
    project_new: projectCounts.fresh,
    project_changed: projectCounts.changed,
    plan_new: planCounts.fresh,
    plan_changed: planCounts.changed,
    total_events:
      projectCounts.fresh + projectCounts.changed + planCounts.fresh + planCounts.changed,
    truncated,
  };
}
