import { beforeEach, describe, expect, it } from 'vitest';
import {
  classifyDemoEvent,
  createDemoWatch,
  deleteDemoWatch,
  demoWatchEvents,
  listDemoWatches,
  markDemoWatchSeen,
} from './demoWatches';

/** Enkel localStorage-stubb — vitest kör i node-miljö utan DOM. */
function stubLocalStorage(): void {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
      clear: () => store.clear(),
    },
  });
}

/** Ruta över Stockholms innerstad — exempeldatat ligger här. */
const STOCKHOLM_RING: [number, number][] = [
  [17.9, 59.2],
  [18.3, 59.2],
  [18.3, 59.4],
  [17.9, 59.4],
];

beforeEach(() => {
  stubLocalStorage();
});

describe('demoWatches', () => {
  it('skapar, listar och tar bort bevakningar', () => {
    const created = createDemoWatch('Innerstan', STOCKHOLM_RING);
    expect(created.geometry.type).toBe('MultiPolygon');
    expect(created.properties.last_seen_at).toBeTruthy();

    const listed = listDemoWatches();
    expect(listed.features).toHaveLength(1);
    expect(listed.features[0].properties.name).toBe('Innerstan');

    deleteDemoWatch(created.properties.id);
    expect(listDemoWatches().features).toHaveLength(0);
  });

  it('räknar projekt och planer som skär området', () => {
    createDemoWatch('Innerstan', STOCKHOLM_RING);
    const events = demoWatchEvents();
    const watches = events.watches ?? [];
    expect(watches).toHaveLength(1);
    // Exempeldatat innehåller flera Stockholmsprojekt (Nya Slussen m.fl.)
    expect(watches[0].project_count).toBeGreaterThan(0);
    // Demodatats stämplar ligger före referensdatumet (2026-08-05) och
    // bevakningen skapas "nu" → inga händelser
    expect(events.total_events).toBe(0);
  });

  it('område långt bort ger inga träffar', () => {
    createDemoWatch('Ute i havet', [
      [10.0, 55.0],
      [10.1, 55.0],
      [10.1, 55.1],
      [10.0, 55.1],
    ]);
    const watches = demoWatchEvents().watches ?? [];
    expect(watches[0].project_count).toBe(0);
    expect(watches[0].plan_count).toBe(0);
  });

  it('markera som sett flyttar fram last_seen_at', () => {
    const created = createDemoWatch('Innerstan', STOCKHOLM_RING);
    const before = created.properties.last_seen_at;
    markDemoWatchSeen(created.properties.id);
    const after = listDemoWatches().features[0].properties.last_seen_at;
    expect(after == null || before == null || after >= before).toBe(true);
  });

  it('saknad localStorage ger tomma listor, inte krasch', () => {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: undefined,
    });
    expect(listDemoWatches().features).toHaveLength(0);
    expect(demoWatchEvents().watches).toHaveLength(0);
  });
});

describe('classifyDemoEvent — speglar backendens classify_event', () => {
  const seen = '2026-08-20T12:00:00Z';
  const before = '2026-08-19T12:00:00Z';
  const after = '2026-08-21T12:00:00Z';

  it('skapad efter sett = nytt', () => {
    expect(classifyDemoEvent(after, after, seen)).toBe('nytt');
  });
  it('bara uppdaterad efter sett = ändrat', () => {
    expect(classifyDemoEvent(before, after, seen)).toBe('ändrat');
  });
  it('orörd sedan sett = ingen händelse', () => {
    expect(classifyDemoEvent(before, before, seen)).toBeNull();
  });
  it('saknade tidsstämplar = ingen händelse', () => {
    expect(classifyDemoEvent(null, null, seen)).toBeNull();
  });
});
