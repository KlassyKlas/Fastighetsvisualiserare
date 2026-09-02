import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import clsx from 'clsx';
import { Check, Sparkles } from 'lucide-react';
import { changesQuery, syncRunsQuery } from '@/api/queries';
import { sampleReferenceDate } from '@/data/sampleData';
import {
  CHANGES_PERIOD_LABELS,
  CHANGES_PERIODS,
  changesNow,
  FIRST_VISIT_DAYS,
  isFirstVisit,
  resolveSince,
  summarizeChangeCounts,
  type ChangesPeriod,
} from '@/lib/changes';
import { formatDate, formatDateTime } from '@/lib/format';
import { latestSyncStartedAt } from '@/lib/syncRuns';
import { useUiStore } from '@/store/uiStore';
import EventList from './EventList';
import { useEventSelection } from './useEventSelection';

/** Rader som visas innan "Visa alla" — resten fälls ut på begäran. */
const VISIBLE_EVENTS = 20;

/**
 * "Nytt sedan senast": vad har hänt GLOBALT sedan senaste besöket,
 * de senaste 7/30 dagarna eller senaste synken. Bevakningarna nedanför
 * svarar på samma fråga per ritat område.
 */
export default function ChangesSection() {
  const demoMode = useUiStore((s) => s.demoMode);
  const changesPeriod = useUiStore((s) => s.changesPeriod);
  const changesSeenAt = useUiStore((s) => s.changesSeenAt);
  const setChangesPeriod = useUiStore((s) => s.setChangesPeriod);
  const markChangesSeen = useUiStore((s) => s.markChangesSeen);
  const selectEvent = useEventSelection();

  const { data: syncRuns, isError: syncRunsError } = useQuery(syncRunsQuery());
  const latestSync = latestSyncStartedAt(syncRuns?.runs);

  // Listan kan vara lång (upp till 200 rader) och ligger ovanför
  // bevakningarna — visa ett utdrag och låt användaren fälla ut resten.
  const [showAll, setShowAll] = useState(false);

  // I demo-läge räknas perioderna mot exempeldatats referensdatum (se
  // changesNow) — annars vore panelen alltid tom i demon.
  const since = resolveSince(changesPeriod, changesSeenAt, latestSync, changesNow(demoMode));
  const { data, isPending, isError } = useQuery({
    ...changesQuery(since),
    enabled: since != null,
  });

  const totalEvents = data?.total_events ?? 0;
  const projectEvents = data?.project_events ?? [];
  const planEvents = data?.plan_events ?? [];
  const shownEvents = projectEvents.length + planEvents.length;
  const visibleProjects = showAll ? projectEvents : projectEvents.slice(0, VISIBLE_EVENTS);
  const visiblePlans = showAll
    ? planEvents
    : planEvents.slice(0, Math.max(0, VISIBLE_EVENTS - visibleProjects.length));
  const hiddenEvents = shownEvents - visibleProjects.length - visiblePlans.length;
  const firstVisit = changesPeriod === 'visit' && isFirstVisit(changesSeenAt);
  const sinceLabel = formatDateTime(since);

  const periodDisabled = (period: ChangesPeriod) => period === 'sync' && latestSync == null;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5" />
          Nytt sedan senast
          {/* Neutral ton — flikens röda badge räknar osedda sedan senaste
              besöket, den här räknar vald period; de ska inte se ut som
              samma tal. */}
          {totalEvents > 0 && (
            <span
              className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-slate-600 text-slate-100 text-[10px] font-bold normal-case tracking-normal"
              title="Händelser i vald period"
            >
              {totalEvents > 99 ? '99+' : totalEvents}
            </span>
          )}
        </h3>
        <p className="text-xs text-slate-500">
          Projekt och detaljplaner som tillkommit eller ändrats i hela datamängden.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {CHANGES_PERIODS.map((period) => {
          const disabled = periodDisabled(period);
          return (
            <button
              key={period}
              onClick={() => setChangesPeriod(period)}
              aria-pressed={changesPeriod === period}
              disabled={disabled}
              title={disabled ? 'Ingen synk registrerad' : undefined}
              className={clsx(
                'px-2 py-0.5 rounded-full text-[11px] font-medium transition-colors',
                'disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-slate-700',
                changesPeriod === period
                  ? 'bg-blue-500/20 text-blue-300 border border-blue-500'
                  : 'bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-500',
              )}
            >
              {CHANGES_PERIOD_LABELS[period]}
            </button>
          );
        })}
      </div>

      {since == null ? (
        <p className="text-[11px] text-slate-500">
          {demoMode
            ? 'Synkloggen kräver att backend körs (demo-läge).'
            : syncRunsError
              ? 'Kunde inte hämta synkloggen från backend.'
              : 'Ingen synk registrerad ännu — synkronisera en källa under Lager.'}
        </p>
      ) : firstVisit ? (
        <p className="text-[11px] text-slate-500">
          Första besöket — visar de senaste {FIRST_VISIT_DAYS} dagarna.
        </p>
      ) : (
        sinceLabel && <p className="text-[11px] text-slate-500">Sedan {sinceLabel}</p>
      )}

      {demoMode && (
        <p className="text-xs text-amber-400/80">
          Demo-läge: händelserna beräknas mot exempeldatat (referens{' '}
          {formatDate(sampleReferenceDate)}).
          {/* Besöksmarkören sätts alltid till riktig tid — den ska gälla när
              backend kommer tillbaka — och hamnar därför efter alla
              exempelstämplar: perioden är tom tills en annan väljs. */}
          {changesPeriod === 'visit' && !firstVisit && (
            <>
              {' '}
              Besöksmarkören är riktig tid och ligger efter alla exempelhändelser — välj 7 eller 30
              dagar för att se dem.
            </>
          )}
        </p>
      )}

      {since != null && isPending && <p className="text-xs text-slate-500">Hämtar händelser…</p>}
      {isError && <p className="text-xs text-red-400">Kunde inte hämta händelser från backend.</p>}

      {data && (
        <>
          {/* Räkneraden säger redan "Inga nya eller ändrade objekt." vid noll
              händelser — listan renderas bara när det finns rader, annars
              hade två tomtexter stått under varandra. */}
          <p className="text-xs text-slate-300">{summarizeChangeCounts(data)}</p>

          {shownEvents > 0 && (
            <EventList
              projectEvents={visibleProjects}
              planEvents={visiblePlans}
              onSelect={selectEvent}
            />
          )}

          {(hiddenEvents > 0 || showAll) && shownEvents > VISIBLE_EVENTS && (
            <button
              onClick={() => setShowAll((value) => !value)}
              className="text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
            >
              {showAll ? 'Visa färre' : `Visa alla ${shownEvents} händelser`}
            </button>
          )}

          {data.truncated && (
            <p className="text-[11px] text-slate-500">
              Visar {shownEvents} av {totalEvents} händelser.
            </p>
          )}

          {changesPeriod === 'visit' && totalEvents > 0 && (
            <button
              onClick={markChangesSeen}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs transition-colors"
            >
              <Check className="w-3.5 h-3.5" />
              Markera som sett
            </button>
          )}
        </>
      )}
    </div>
  );
}
