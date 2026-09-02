/**
 * Ren tidslogik för panelen "Nytt sedan senast": vilken tidpunkt en vald
 * period motsvarar, och hur räkningarna sammanfattas. Ingen React och
 * ingen klocka här — `now` skickas in så att logiken är testbar och så
 * att demo-läget kan räkna mot exempeldatats referensdatum.
 */
import { sampleReferenceDate } from '@/data/sampleData';
import type { ChangesResponse } from '@/domain';

export type ChangesPeriod = 'visit' | '7d' | '30d' | 'sync';

/** Ordningen styr periodchipsen i panelen. */
export const CHANGES_PERIODS: ChangesPeriod[] = ['visit', '7d', '30d', 'sync'];

export const CHANGES_PERIOD_LABELS: Record<ChangesPeriod, string> = {
  visit: 'Senaste besöket',
  '7d': '7 dagar',
  '30d': '30 dagar',
  sync: 'Senaste synk',
};

/** Första besöket har ingen markör — då visas de senaste 30 dagarna. */
export const FIRST_VISIT_DAYS = 30;

const HOUR_MS = 3_600_000;
const DAY_MS = 24 * HOUR_MS;

/** Ingen markör, eller en som inte går att tolka, räknas som första besöket. */
export function isFirstVisit(seenAt: string | null): boolean {
  return seenAt == null || Number.isNaN(Date.parse(seenAt));
}

/** Avrundat nedåt till hel timme (UTC). */
function floorToHour(now: Date): Date {
  return new Date(Math.floor(now.getTime() / HOUR_MS) * HOUR_MS);
}

function daysBefore(now: Date, days: number): string {
  return new Date(floorToHour(now).getTime() - days * DAY_MS).toISOString();
}

/**
 * Tidpunkten "sedan" för en period, som ISO-sträng i UTC.
 *
 * `now` avrundas nedåt till hel timme för de relativa perioderna så att
 * querynyckeln (['changes', { since }]) är stabil mellan renderingar —
 * annars skulle varje rendering ge en ny cachepost och en ny request.
 * Första besöket (ingen markör) = 30 dagar bakåt. sync utan känd synk = null.
 */
export function resolveSince(
  period: ChangesPeriod,
  seenAt: string | null,
  latestSyncStartedAt: string | null,
  now: Date,
): string | null {
  switch (period) {
    case 'visit':
      return isFirstVisit(seenAt) ? daysBefore(now, FIRST_VISIT_DAYS) : seenAt;
    case '7d':
      return daysBefore(now, 7);
    case '30d':
      return daysBefore(now, 30);
    case 'sync':
      return latestSyncStartedAt;
  }
}

/**
 * Klockan som perioderna räknas mot. I demo-läge används exempeldatats
 * referensdatum (mitt på dagen) i stället för riktiga "nu": demodatats
 * tidsstämplar är fasta och ligger strax före referensdatumet, så mot
 * dagens datum skulle panelen alltid vara tom och demon säga ingenting.
 */
export function changesNow(demoMode: boolean): Date {
  return demoMode ? new Date(`${sampleReferenceDate}T12:00:00Z`) : new Date();
}

type ChangeCounts = Pick<
  ChangesResponse,
  'project_new' | 'project_changed' | 'plan_new' | 'plan_changed'
>;

/** En delräkning (antal + adjektiv böjt efter antalet) som summarizeChangeCounts sätter ihop. */
interface CountPart {
  count: number;
  adjective: string;
}

function planNoun(count: number): string {
  return count === 1 ? 'detaljplan' : 'detaljplaner';
}

/**
 * Räkneraden, t.ex. "3 nya · 1 ändrat projekt · 1 ny detaljplan".
 * Nollor utelämnas, böjningen följer antalet, och utan händelser
 * returneras en tydlig text i stället för en tom rad.
 *
 * "Projekt" böjs lika i singular och plural, men "detaljplan" gör det
 * inte: delarna delar substantiv bara när de har samma numerus ("1 ny ·
 * 1 ändrad detaljplan", "2 nya · 3 ändrade detaljplaner"); annars får
 * varje del sitt eget ("2 nya detaljplaner · 1 ändrad detaljplan") så att
 * raden aldrig blir "1 ändrad detaljplaner".
 */
export function summarizeChangeCounts(counts: ChangeCounts): string {
  const groups: string[] = [];

  const projectParts: string[] = [];
  if (counts.project_new > 0) {
    projectParts.push(counts.project_new === 1 ? '1 nytt' : `${counts.project_new} nya`);
  }
  if (counts.project_changed > 0) {
    projectParts.push(
      counts.project_changed === 1 ? '1 ändrat' : `${counts.project_changed} ändrade`,
    );
  }
  if (projectParts.length > 0) {
    groups.push(`${projectParts.join(' · ')} projekt`);
  }

  const planParts: CountPart[] = [];
  if (counts.plan_new > 0) {
    planParts.push({ count: counts.plan_new, adjective: counts.plan_new === 1 ? 'ny' : 'nya' });
  }
  if (counts.plan_changed > 0) {
    planParts.push({
      count: counts.plan_changed,
      adjective: counts.plan_changed === 1 ? 'ändrad' : 'ändrade',
    });
  }
  if (planParts.length > 0) {
    const sameNumber = planParts.every(
      (part) => planNoun(part.count) === planNoun(planParts[0].count),
    );
    groups.push(
      sameNumber
        ? `${planParts.map((part) => `${part.count} ${part.adjective}`).join(' · ')} ${planNoun(planParts[0].count)}`
        : planParts
            .map((part) => `${part.count} ${part.adjective} ${planNoun(part.count)}`)
            .join(' · '),
    );
  }

  return groups.length > 0 ? groups.join(' · ') : 'Inga nya eller ändrade objekt.';
}
