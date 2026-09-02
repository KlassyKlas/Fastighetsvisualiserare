/**
 * Ren logik över synkloggen (GET /infrastructure/sync/runs): senaste
 * körning per källa för lagerpanelen och tidsankaret "sedan senaste
 * synk" för panelen Nytt sedan senast.
 */
import type { SyncRunInfo } from '@/domain';

/** Lyckad = avslutad utan fel. En rad utan finished_at pågår (eller dog). */
function isSuccessfulRun(run: SyncRunInfo): boolean {
  return run.finished_at != null && run.error == null;
}

/** Nyast först på started_at, därefter id — API:t levererar redan så,
 * men sorteringen görs om här för att inte lita på det. */
function newestFirst(runs: SyncRunInfo[]): SyncRunInfo[] {
  return [...runs].sort((a, b) => {
    const byStart = Date.parse(b.started_at) - Date.parse(a.started_at);
    return byStart !== 0 ? byStart : b.id - a.id;
  });
}

/**
 * Senaste körning per källnamn. Partial eftersom en källa utan körningar
 * saknas som nyckel — typen tvingar anroparen att hantera undefined
 * (tsconfig har inte noUncheckedIndexedAccess).
 */
export type RunBySource = Partial<Record<string, SyncRunInfo>>;

/** Senaste körningen per källa, oavsett utfall. */
export function latestRunBySource(runs: SyncRunInfo[] | undefined): RunBySource {
  const result: RunBySource = {};
  for (const run of newestFirst(runs ?? [])) {
    result[run.source] ??= run;
  }
  return result;
}

/** Senaste LYCKADE körningen per källa — det som "Senast synkad" avser. */
export function latestSuccessfulRunBySource(runs: SyncRunInfo[] | undefined): RunBySource {
  const result: RunBySource = {};
  for (const run of newestFirst(runs ?? [])) {
    if (isSuccessfulRun(run)) result[run.source] ??= run;
  }
  return result;
}

/**
 * Tidsankaret för perioden "Senaste synk": starttiden för den senaste
 * LYCKADE körningen. En misslyckad körning har inte ändrat något, och en
 * oavslutad rad (pågående — eller död, om processen dödades mitt i
 * hämtningen) får inte bli ankare: en död rad hade annars dolt allt som
 * den senaste riktiga synken ändrade tills nästa körning startas. Medan
 * en synk pågår pekar ankaret alltså på föregående lyckade körning.
 * null när ingen lyckad synk är registrerad.
 */
export function latestSyncStartedAt(runs: SyncRunInfo[] | undefined): string | null {
  const run = newestFirst(runs ?? []).find(isSuccessfulRun);
  return run?.started_at ?? null;
}
