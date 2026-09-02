import clsx from 'clsx';
import { STATUS_LABELS } from '@/config/map';
import type {
  DetailPlanFeature,
  DetailPlanWatchEvent,
  ProjectFeature,
  ProjectWatchEvent,
  WatchEventKind,
} from '@/domain';

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
        'inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide flex-shrink-0',
        EVENT_KIND_STYLES[kind],
      )}
    >
      {EVENT_KIND_LABELS[kind]}
    </span>
  );
}

/** Det som väljs när en händelserad klickas — full API-feature. */
export type EventSelection =
  { kind: 'project'; feature: ProjectFeature } | { kind: 'plan'; feature: DetailPlanFeature };

interface EventRowProps {
  title: string;
  subtitle: string;
  kind: WatchEventKind;
  hasGeometry: boolean;
  onClick?: () => void;
}

function EventRow({ title, subtitle, kind, hasGeometry, onClick }: EventRowProps) {
  const content = (
    <>
      <div className="min-w-0 text-left">
        <p className="text-xs text-slate-200 leading-snug">{title}</p>
        <p className="text-[11px] text-slate-500">
          {subtitle}
          {/* /changes kräver ingen geometri (till skillnad från bevakningarna) —
              raden är klickbar ändå, men kartan kan inte zooma dit. */}
          {!hasGeometry && <span className="text-slate-600"> · saknar geometri</span>}
        </p>
      </div>
      <EventKindBadge kind={kind} />
    </>
  );
  const className = 'w-full flex items-start justify-between gap-2 bg-slate-900/60 rounded p-2';
  if (!onClick) {
    return <div className={className}>{content}</div>;
  }
  return (
    <button
      onClick={onClick}
      className={clsx(className, 'hover:bg-slate-700/60 transition-colors')}
      title={hasGeometry ? 'Visa i detaljpanelen och zooma dit' : 'Visa i detaljpanelen'}
    >
      {content}
    </button>
  );
}

interface EventListProps {
  // Kontraktet markerar listfälten som valfria (default_factory) —
  // backend skickar dem alltid, men typerna kräver ?? [].
  projectEvents?: ProjectWatchEvent[];
  planEvents?: DetailPlanWatchEvent[];
  /** Utan onSelect renderas raderna som ren text (inte klickbara). */
  onSelect?: (selection: EventSelection) => void;
}

/**
 * Händelselista delad mellan bevakningarna (per område) och "Nytt sedan
 * senast" (globalt) — samma utseende, samma badge, samma klickbeteende.
 */
export default function EventList({
  projectEvents = [],
  planEvents = [],
  onSelect,
}: EventListProps) {
  if (projectEvents.length === 0 && planEvents.length === 0) {
    return <p className="text-xs text-slate-500">Inget nytt sedan du senast tittade.</p>;
  }
  return (
    <div className="space-y-1.5">
      {projectEvents.map((event) => {
        // Kontraktets feature är löst typad GeoJSON; egenskaperna är identiska.
        const feature = event.project as unknown as ProjectFeature;
        const props = feature.properties;
        return (
          <EventRow
            key={`project-${props.id}`}
            title={props.name}
            subtitle={`Infrastrukturprojekt${
              props.status ? ` · ${STATUS_LABELS[props.status] ?? props.status}` : ''
            }`}
            kind={event.event_kind}
            hasGeometry={feature.geometry != null}
            onClick={onSelect ? () => onSelect({ kind: 'project', feature }) : undefined}
          />
        );
      })}
      {planEvents.map((event) => {
        const feature = event.plan as unknown as DetailPlanFeature;
        const props = feature.properties;
        return (
          <EventRow
            key={`plan-${props.id}`}
            title={props.name}
            subtitle={`Detaljplan${props.status ? ` · ${props.status}` : ''}`}
            kind={event.event_kind}
            hasGeometry={feature.geometry != null}
            onClick={onSelect ? () => onSelect({ kind: 'plan', feature }) : undefined}
          />
        );
      })}
    </div>
  );
}
