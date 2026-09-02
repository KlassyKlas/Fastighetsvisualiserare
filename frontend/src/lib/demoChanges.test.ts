import { describe, expect, it } from 'vitest';
import { sampleDetailPlans, sampleProjects } from '@/data/sampleData';
import { changesNow } from './changes';
import { demoChanges } from './demoChanges';

/** Demodatats "nu" — appens egen demoklocka, inte en egen härledning som kan glida. */
const DEMO_NOW = changesNow(true).getTime();
const DAY_MS = 86_400_000;

function daysBack(days: number): string {
  return new Date(DEMO_NOW - days * DAY_MS).toISOString();
}

describe('demoChanges — speglar backendens changes()', () => {
  it('since långt bak ger alla objekt som nya', () => {
    const result = demoChanges('2000-01-01T00:00:00Z');
    expect(result.project_new).toBe(sampleProjects.features.length);
    expect(result.plan_new).toBe(sampleDetailPlans.features.length);
    expect(result.project_changed).toBe(0);
    expect(result.plan_changed).toBe(0);
    expect(result.total_events).toBe(
      sampleProjects.features.length + sampleDetailPlans.features.length,
    );
    expect(result.truncated).toBe(false);
    expect(result.project_events).toHaveLength(sampleProjects.features.length);
  });

  it('since i framtiden ger inga händelser', () => {
    const result = demoChanges('2999-01-01T00:00:00Z');
    expect(result.total_events).toBe(0);
    expect(result.project_events).toEqual([]);
    expect(result.plan_events).toEqual([]);
    expect(result.truncated).toBe(false);
  });

  it('räknar både nya och ändrade inom de senaste sju demodagarna', () => {
    const result = demoChanges(daysBack(7));
    // Exporten stämplar vart tredje objekt som ändrat dagen före referensdatumet
    expect(result.project_changed).toBeGreaterThan(0);
    expect(result.project_new).toBeGreaterThan(0);
    const kinds = new Set((result.project_events ?? []).map((event) => event.event_kind));
    expect(kinds).toEqual(new Set(['nytt', 'ändrat']));
    expect(result.total_events).toBe(
      result.project_new + result.project_changed + result.plan_new + result.plan_changed,
    );
  });

  it('nya vinner över ändrade — samma objekt räknas bara en gång', () => {
    const since = daysBack(30);
    const sinceMs = Date.parse(since);
    const result = demoChanges(since);
    const events = result.project_events ?? [];
    const ids = events.map((event) => event.project.properties.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(result.project_new + result.project_changed).toBe(ids.length);

    // Ett objekt som både skapats OCH ändrats efter since är "nytt" — inte
    // "ändrat", och inte båda. Fallet måste finnas i datat för att regeln
    // ska prövas alls; sedan ska varje händelses sort följa stämplarna.
    const createdAndUpdatedAfter = events.filter(
      ({ project: { properties } }) =>
        Date.parse(properties.created_at ?? '') > sinceMs &&
        properties.updated_at !== properties.created_at,
    );
    expect(createdAndUpdatedAfter.length).toBeGreaterThan(0);
    for (const event of events) {
      const created = Date.parse(event.project.properties.created_at ?? '');
      expect(event.event_kind).toBe(created > sinceMs ? 'nytt' : 'ändrat');
    }
  });

  it('sorterar senast ändrade först och bryter lika på id fallande', () => {
    const events = demoChanges('2000-01-01T00:00:00Z').project_events ?? [];
    for (let i = 1; i < events.length; i++) {
      const prev = events[i - 1].project.properties;
      const curr = events[i].project.properties;
      const prevUpdated = Date.parse(prev.updated_at ?? '');
      const currUpdated = Date.parse(curr.updated_at ?? '');
      expect(prevUpdated >= currUpdated).toBe(true);
      if (prevUpdated === currUpdated) {
        expect(prev.id).toBeGreaterThan(curr.id);
      }
    }
  });

  it('limit trunkerar listan men inte räkningarna — projekt först', () => {
    const full = demoChanges('2000-01-01T00:00:00Z');
    const limited = demoChanges('2000-01-01T00:00:00Z', 1);
    expect(limited.project_events).toHaveLength(1);
    expect(limited.plan_events).toHaveLength(0);
    expect(limited.truncated).toBe(true);
    expect(limited.total_events).toBe(full.total_events);
  });

  it('detaljplaner får det som blir över av limit', () => {
    const projectCount = sampleProjects.features.length;
    const result = demoChanges('2000-01-01T00:00:00Z', projectCount + 2);
    expect(result.project_events).toHaveLength(projectCount);
    expect(result.plan_events).toHaveLength(2);
    expect(result.truncated).toBe(sampleDetailPlans.features.length > 2);
  });

  it('since utan millisekunder och med millisekunder ger samma svar', () => {
    // Stämpeln hämtas ur datat i stället för att hårdkodas, så att testet
    // överlever ändringar i seed-fixturen och referensdatumet.
    const probe = sampleProjects.features.find(
      (f) => f.properties.created_at != null && f.properties.updated_at === f.properties.created_at,
    );
    if (!probe?.properties.created_at) throw new Error('Demodatat saknar oförändrat projekt');
    const stamp = probe.properties.created_at;
    expect(stamp).toMatch(/:\d\dZ$/); // backendens form: inga millisekunder
    const a = demoChanges(stamp);
    const b = demoChanges(new Date(stamp).toISOString());
    expect(a.total_events).toBe(b.total_events);
    expect(a.since).toBe(b.since);
    // Objektet skapat exakt vid since är INTE nytt (strikt större än)
    const ids = new Set((a.project_events ?? []).map((event) => event.project.properties.id));
    for (const feature of sampleProjects.features) {
      if (feature.properties.created_at === stamp && feature.properties.updated_at === stamp) {
        expect(ids.has(feature.properties.id)).toBe(false);
      }
    }
  });

  it('ekar since normaliserat till UTC i backendens textform', () => {
    // Pydantic skriver ingen millisekunddel vid hela sekunder — demo och
    // live ska ge identisk text för samma instant.
    expect(demoChanges('2026-07-20T10:00:00+02:00').since).toBe('2026-07-20T08:00:00Z');
    expect(demoChanges('2026-07-20T08:00:00.000Z').since).toBe('2026-07-20T08:00:00Z');
    expect(demoChanges('2026-07-20T08:00:00.250Z').since).toBe('2026-07-20T08:00:00.250Z');
  });

  it('otolkbart since ger tomt svar — inte "allt är nytt"', () => {
    // "" sorterar före varje tidsstämpel; skickad rå till strängjämförelsen
    // hade den klassat hela demodatat som nytt. (OBS: "0" är INTE
    // otolkbart — Date.parse tolkar det som år 2000.)
    for (const broken of ['', 'trasigt', 'inte-en-tid']) {
      const result = demoChanges(broken);
      expect(result.total_events).toBe(0);
      expect(result.project_events).toEqual([]);
      expect(result.plan_events).toEqual([]);
      expect(result.truncated).toBe(false);
      expect(result.since).toBe(broken);
    }
  });
});
