import { describe, expect, it } from 'vitest';
import { planCountLabel } from './changes';

describe('planCountLabel', () => {
  it('böjer detaljplan efter antalet', () => {
    expect(planCountLabel(1)).toBe('1 detaljplan');
    expect(planCountLabel(0)).toBe('0 detaljplaner');
    expect(planCountLabel(5)).toBe('5 detaljplaner');
  });
});
import { sampleReferenceDate } from '@/data/sampleData';
import {
  CHANGES_PERIOD_LABELS,
  CHANGES_PERIODS,
  changesNow,
  isFirstVisit,
  resolveSince,
  summarizeChangeCounts,
} from './changes';

const NOW = new Date('2026-09-01T14:37:21.456Z');

describe('resolveSince', () => {
  it('senaste besöket utan markör = 30 dagar bakåt från hel timme', () => {
    expect(resolveSince('visit', null, null, NOW)).toBe('2026-08-02T14:00:00.000Z');
  });

  it('senaste besöket med markör returnerar markören oförändrad', () => {
    expect(resolveSince('visit', '2026-08-30T09:15:00.000Z', null, NOW)).toBe(
      '2026-08-30T09:15:00.000Z',
    );
  });

  it('7 och 30 dagar räknas från hel timme så att querynyckeln är stabil', () => {
    expect(resolveSince('7d', null, null, NOW)).toBe('2026-08-25T14:00:00.000Z');
    expect(resolveSince('30d', null, null, NOW)).toBe('2026-08-02T14:00:00.000Z');
    // Två renderingar inom samma timme ger samma nyckel
    const later = new Date('2026-09-01T14:59:59.999Z');
    expect(resolveSince('7d', null, null, later)).toBe(resolveSince('7d', null, null, NOW));
  });

  it('senaste synk använder synkens starttid, eller null utan synk', () => {
    expect(resolveSince('sync', null, '2026-08-31T22:00:00Z', NOW)).toBe('2026-08-31T22:00:00Z');
    expect(resolveSince('sync', '2026-08-30T09:15:00.000Z', null, NOW)).toBeNull();
  });

  it('ogiltig markör behandlas som första besöket', () => {
    expect(resolveSince('visit', 'trasigt', null, NOW)).toBe('2026-08-02T14:00:00.000Z');
  });
});

describe('isFirstVisit', () => {
  it('null och otolkbara värden är första besöket', () => {
    expect(isFirstVisit(null)).toBe(true);
    expect(isFirstVisit('inte-en-tid')).toBe(true);
    expect(isFirstVisit('2026-08-30T09:15:00.000Z')).toBe(false);
  });
});

describe('changesNow', () => {
  it('demo-läget räknar mot exempeldatats referensdatum', () => {
    expect(changesNow(true).toISOString()).toBe(`${sampleReferenceDate}T12:00:00.000Z`);
  });

  it('live-läget använder riktiga klockan', () => {
    const before = Date.now();
    const now = changesNow(false).getTime();
    expect(now).toBeGreaterThanOrEqual(before);
    expect(now - before).toBeLessThan(5_000);
  });
});

describe('periodchips', () => {
  it('alla perioder har en svensk etikett', () => {
    for (const period of CHANGES_PERIODS) {
      expect(CHANGES_PERIOD_LABELS[period]).toBeTruthy();
    }
    expect(CHANGES_PERIODS).toHaveLength(4);
  });
});

describe('summarizeChangeCounts', () => {
  it('utelämnar nollor och böjer efter antal', () => {
    expect(
      summarizeChangeCounts({ project_new: 3, project_changed: 1, plan_new: 1, plan_changed: 0 }),
    ).toBe('3 nya · 1 ändrat projekt · 1 ny detaljplan');
  });

  it('bara detaljplaner', () => {
    expect(
      summarizeChangeCounts({ project_new: 0, project_changed: 0, plan_new: 0, plan_changed: 2 }),
    ).toBe('2 ändrade detaljplaner');
  });

  it('en ändrad detaljplan i singular', () => {
    expect(
      summarizeChangeCounts({ project_new: 0, project_changed: 0, plan_new: 0, plan_changed: 1 }),
    ).toBe('1 ändrad detaljplan');
  });

  it('en ny och en ändrad detaljplan delar substantiv i singular', () => {
    expect(
      summarizeChangeCounts({ project_new: 0, project_changed: 0, plan_new: 1, plan_changed: 1 }),
    ).toBe('1 ny · 1 ändrad detaljplan');
  });

  it('olika numerus ger varje del sitt eget substantiv', () => {
    expect(
      summarizeChangeCounts({ project_new: 0, project_changed: 0, plan_new: 2, plan_changed: 1 }),
    ).toBe('2 nya detaljplaner · 1 ändrad detaljplan');
    expect(
      summarizeChangeCounts({ project_new: 1, project_changed: 1, plan_new: 1, plan_changed: 3 }),
    ).toBe('1 nytt · 1 ändrat projekt · 1 ny detaljplan · 3 ändrade detaljplaner');
  });

  it('flera nya och flera ändrade detaljplaner delar plural', () => {
    expect(
      summarizeChangeCounts({ project_new: 0, project_changed: 0, plan_new: 2, plan_changed: 3 }),
    ).toBe('2 nya · 3 ändrade detaljplaner');
  });

  it('visar alltid något — även utan händelser', () => {
    expect(
      summarizeChangeCounts({ project_new: 0, project_changed: 0, plan_new: 0, plan_changed: 0 }),
    ).toBe('Inga nya eller ändrade objekt.');
  });
});
