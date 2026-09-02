import { describe, expect, it } from 'vitest';
import type { SyncRunInfo } from '@/domain';
import { latestRunBySource, latestSuccessfulRunBySource, latestSyncStartedAt } from './syncRuns';

function run(
  overrides: Partial<SyncRunInfo> & Pick<SyncRunInfo, 'id' | 'started_at'>,
): SyncRunInfo {
  return {
    source: 'trafikverket',
    finished_at: overrides.started_at,
    fetched: 10,
    upserted: 3,
    unchanged: 7,
    skipped: 0,
    truncated: false,
    error: null,
    ...overrides,
  };
}

// Medvetet i "fel" ordning — funktionerna får inte lita på API:ts sortering.
const RUNS: SyncRunInfo[] = [
  run({ id: 1, started_at: '2026-08-20T10:00:00Z', source: 'trafikverket' }),
  run({ id: 4, started_at: '2026-08-23T10:00:00Z', source: 'nationell_plan', finished_at: null }),
  run({
    id: 3,
    started_at: '2026-08-22T10:00:00Z',
    source: 'trafikverket',
    error: 'Timeout',
    finished_at: '2026-08-22T10:00:05Z',
  }),
  run({ id: 2, started_at: '2026-08-21T10:00:00Z', source: 'trafikverket' }),
];

describe('latestRunBySource', () => {
  it('ger senaste körningen per källa oavsett utfall', () => {
    const latest = latestRunBySource(RUNS);
    expect(latest.trafikverket?.id).toBe(3);
    expect(latest.nationell_plan?.id).toBe(4);
  });

  it('tom eller saknad lista ger tomt objekt', () => {
    expect(latestRunBySource(undefined)).toEqual({});
    expect(latestRunBySource([])).toEqual({});
  });
});

describe('latestSuccessfulRunBySource', () => {
  it('hoppar över misslyckade och pågående körningar', () => {
    const latest = latestSuccessfulRunBySource(RUNS);
    expect(latest.trafikverket?.id).toBe(2);
    expect(latest.nationell_plan).toBeUndefined();
  });
});

describe('latestSyncStartedAt', () => {
  it('tar senaste lyckade körningen — en oavslutad rad får inte bli ankare', () => {
    // RUNS[1] (id 4) är nyast men saknar finished_at: pågående eller död.
    // Hade den blivit ankare skulle allt som id 2 ändrade döljas.
    expect(latestSyncStartedAt(RUNS)).toBe('2026-08-21T10:00:00Z');
  });

  it('hoppar över misslyckade körningar', () => {
    expect(latestSyncStartedAt([RUNS[2], RUNS[0]])).toBe('2026-08-20T10:00:00Z');
  });

  it('null utan lyckad synk', () => {
    expect(latestSyncStartedAt(undefined)).toBeNull();
    expect(latestSyncStartedAt([RUNS[2]])).toBeNull();
    expect(latestSyncStartedAt([RUNS[1]])).toBeNull();
  });

  it('bryter lika starttid på id', () => {
    const same = [
      run({ id: 7, started_at: '2026-08-25T10:00:00Z', source: 'a' }),
      run({ id: 9, started_at: '2026-08-25T10:00:00Z', source: 'b' }),
    ];
    expect(latestRunBySource(same).b?.id).toBe(9);
    expect(latestSyncStartedAt(same)).toBe('2026-08-25T10:00:00Z');
  });
});
