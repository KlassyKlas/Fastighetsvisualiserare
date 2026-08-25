import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import { Bell, Check, MapPinPlus, Trash2, Undo2, X } from 'lucide-react';
import { useState } from 'react';
import {
  createWatch,
  deleteWatch,
  markWatchSeen,
  watchesQuery,
  watchEventsQuery,
} from '@/api/queries';
import { STATUS_LABELS, WATCH_COLOR } from '@/config/map';
import type { WatchedAreaCreate, WatchEventKind, WatchEvents } from '@/domain';
import { useUiStore } from '@/store/uiStore';

const dateFormat = new Intl.DateTimeFormat('sv-SE', { dateStyle: 'medium', timeStyle: 'short' });

function formatSeen(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : dateFormat.format(parsed);
}

const EVENT_KIND_STYLES: Record<WatchEventKind, string> = {
  nytt: 'bg-green-500/20 text-green-300',
  ändrat: 'bg-amber-500/20 text-amber-300',
};

const EVENT_KIND_LABELS: Record<WatchEventKind, string> = {
  nytt: 'Nytt',
  ändrat: 'Ändrat',
};

function EventKindBadge({ kind }: { kind: WatchEventKind }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide',
        EVENT_KIND_STYLES[kind],
      )}
    >
      {EVENT_KIND_LABELS[kind]}
    </span>
  );
}

function WatchEventList({ events }: { events: WatchEvents }) {
  // Kontraktet markerar listfälten som valfria (default_factory) —
  // backend skickar dem alltid, men typerna kräver ?? [].
  const projectEvents = events.project_events ?? [];
  const planEvents = events.plan_events ?? [];
  if (projectEvents.length === 0 && planEvents.length === 0) {
    return <p className="text-xs text-slate-500">Inget nytt sedan du senast tittade.</p>;
  }
  return (
    <div className="space-y-1.5">
      {projectEvents.map((event) => (
        <div
          key={`project-${event.project.properties.id}`}
          className="flex items-start justify-between gap-2 bg-slate-900/60 rounded p-2"
        >
          <div className="min-w-0">
            <p className="text-xs text-slate-200 leading-snug">{event.project.properties.name}</p>
            <p className="text-[11px] text-slate-500">
              Infrastrukturprojekt
              {event.project.properties.status
                ? ` · ${STATUS_LABELS[event.project.properties.status] ?? event.project.properties.status}`
                : ''}
            </p>
          </div>
          <EventKindBadge kind={event.event_kind} />
        </div>
      ))}
      {planEvents.map((event) => (
        <div
          key={`plan-${event.plan.properties.id}`}
          className="flex items-start justify-between gap-2 bg-slate-900/60 rounded p-2"
        >
          <div className="min-w-0">
            <p className="text-xs text-slate-200 leading-snug">{event.plan.properties.name}</p>
            <p className="text-[11px] text-slate-500">
              Detaljplan
              {event.plan.properties.status ? ` · ${event.plan.properties.status}` : ''}
            </p>
          </div>
          <EventKindBadge kind={event.event_kind} />
        </div>
      ))}
    </div>
  );
}

export default function WatchPanel() {
  const demoMode = useUiStore((s) => s.demoMode);
  const watchDrawing = useUiStore((s) => s.watchDrawing);
  const watchDraftPoints = useUiStore((s) => s.watchDraftPoints);
  const setWatchDrawing = useUiStore((s) => s.setWatchDrawing);
  const undoWatchDraftPoint = useUiStore((s) => s.undoWatchDraftPoint);

  const [draftName, setDraftName] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const { data: watchData } = useQuery(watchesQuery());
  const { data: eventData } = useQuery(watchEventsQuery());

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['watches'] });
    queryClient.invalidateQueries({ queryKey: ['watch-events'] });
  };

  const createMutation = useMutation({
    mutationFn: createWatch,
    onSuccess: () => {
      invalidate();
      setWatchDrawing(false);
      setDraftName('');
      setErrorMessage(null);
    },
    onError: () => setErrorMessage('Kunde inte spara bevakningen. Kontrollera att backend körs.'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWatch,
    onSuccess: invalidate,
    onError: () => setErrorMessage('Kunde inte ta bort bevakningen.'),
  });

  const markSeenMutation = useMutation({
    mutationFn: markWatchSeen,
    onSuccess: invalidate,
    onError: () => setErrorMessage('Kunde inte markera som sett.'),
  });

  const saveDraft = () => {
    const name = draftName.trim();
    if (name.length === 0 || watchDraftPoints.length < 3) return;
    const ring = [...watchDraftPoints, watchDraftPoints[0]];
    createMutation.mutate({
      name,
      geometry: {
        type: 'Polygon',
        coordinates: [ring],
      } as unknown as WatchedAreaCreate['geometry'],
    });
  };

  const eventsByWatch = new Map<number, WatchEvents>(
    (eventData?.watches ?? []).map((entry) => [entry.watch_id, entry]),
  );
  const watches = watchData?.features ?? [];

  return (
    <div className="p-4 space-y-5">
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Bell className="w-3.5 h-3.5" />
          Bevakade områden
        </h3>
        <p className="text-xs text-slate-500">
          Rita ett område i kartan och få notiser när infrastrukturprojekt eller detaljplaner
          tillkommer eller ändras där.
        </p>
      </div>

      {watchDrawing ? (
        <div className="bg-slate-900/50 rounded-lg p-3 space-y-3">
          <p className="text-xs text-slate-300">
            Klicka i kartan för att lägga till hörn — minst tre behövs.{' '}
            <span className="text-slate-500">({watchDraftPoints.length} hittills)</span>
          </p>
          <input
            type="text"
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            placeholder="Namn på området, t.ex. Södermalm"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
          />
          <div className="flex gap-2">
            <button
              onClick={undoWatchDraftPoint}
              disabled={watchDraftPoints.length === 0}
              className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 rounded-lg text-xs transition-colors"
              title="Ångra senaste hörnet"
            >
              <Undo2 className="w-3.5 h-3.5" />
              Ångra
            </button>
            <button
              onClick={() => {
                setWatchDrawing(false);
                setDraftName('');
              }}
              className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs transition-colors"
            >
              <X className="w-3.5 h-3.5" />
              Avbryt
            </button>
            <button
              onClick={saveDraft}
              disabled={
                draftName.trim().length === 0 ||
                watchDraftPoints.length < 3 ||
                createMutation.isPending
              }
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white rounded-lg text-xs font-medium transition-colors"
            >
              <Check className="w-3.5 h-3.5" />
              {createMutation.isPending ? 'Sparar…' : 'Spara bevakning'}
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setWatchDrawing(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <MapPinPlus className="w-4 h-4" />
          Rita nytt område
        </button>
      )}

      {errorMessage && <p className="text-xs text-red-400">{errorMessage}</p>}

      {demoMode && (
        <p className="text-xs text-amber-400/80">
          Demo-läge: bevakningarna sparas bara i din webbläsare och händelser beräknas mot
          exempeldatat.
        </p>
      )}

      <div className="space-y-3">
        {watches.length === 0 && (
          <p className="text-xs text-slate-500">Inga bevakade områden ännu.</p>
        )}
        {watches.map((watch) => {
          const props = watch.properties;
          const events = eventsByWatch.get(props.id);
          const eventCount = events
            ? (events.project_events?.length ?? 0) + (events.plan_events?.length ?? 0)
            : 0;
          const seenLabel = formatSeen(props.last_seen_at);
          return (
            <div key={props.id} className="bg-slate-900/50 rounded-lg p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm text-slate-200 font-medium flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: WATCH_COLOR }}
                    />
                    {props.name}
                    {eventCount > 0 && (
                      <span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold">
                        {eventCount}
                      </span>
                    )}
                  </p>
                  {events && (
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {events.project_count} projekt · {events.plan_count} detaljplaner i området
                    </p>
                  )}
                  {seenLabel && (
                    <p className="text-[11px] text-slate-600">Senast sett: {seenLabel}</p>
                  )}
                </div>
                <button
                  onClick={() => deleteMutation.mutate(props.id)}
                  disabled={deleteMutation.isPending}
                  className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-red-400 transition-colors"
                  title="Ta bort bevakningen"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {events && <WatchEventList events={events} />}

              {eventCount > 0 && (
                <button
                  onClick={() => markSeenMutation.mutate(props.id)}
                  disabled={markSeenMutation.isPending}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs transition-colors"
                >
                  <Check className="w-3.5 h-3.5" />
                  Markera som sett
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
