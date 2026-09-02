import { useQuery } from '@tanstack/react-query';
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

  const { data: syncRuns } = useQuery(syncRunsQuery());
  const latestSync = latestSyncStartedAt(syncRuns?.runs);

  // I demo-läge räknas perioderna mot exempeldatats referensdatum (se
  // changesNow) — annars vore panelen alltid tom i demon.
  const since = resolveSince(changesPeriod, changesSeenAt, latestSync, changesNow(demoMode));
  const { data, isPending, isError } = useQuery({
    ...changesQuery(since),
    enabled: since != null,
  });

  const totalEvents = data?.total_events ?? 0;
  const shownEvents = (data?.project_events?.length ?? 0) + (data?.plan_events?.length ?? 0);
  const firstVisit = changesPeriod === 'visit' && isFirstVisit(changesSeenAt);
  const sinceLabel = formatDateTime(since);

  const periodDisabled = (period: ChangesPeriod) => period === 'sync' && latestSync == null;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5" />
          Nytt sedan senast
          {totalEvents > 0 && (
            <span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold normal-case tracking-normal">
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
          Ingen synk registrerad ännu — synkronisera en källa under Lager.
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

      {since != null && isPending && <p className="text-xs text-slate-500">Hämtar ändringar…</p>}
      {isError && <p className="text-xs text-red-400">Kunde inte hämta ändringar från backend.</p>}

      {data && (
        <>
          {/* Räkneraden säger redan "Inga nya eller ändrade objekt." vid noll
              händelser — listan renderas bara när det finns rader, annars
              hade två tomtexter stått under varandra. */}
          <p className="text-xs text-slate-300">{summarizeChangeCounts(data)}</p>

          {shownEvents > 0 && (
            <EventList
              projectEvents={data.project_events}
              planEvents={data.plan_events}
              onSelect={selectEvent}
            />
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
