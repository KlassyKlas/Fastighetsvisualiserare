import { useQuery } from '@tanstack/react-query';
import { CircleAlert, RefreshCw } from 'lucide-react';
import { impactZonesQuery, projectsQuery, propertiesQuery } from '@/api/queries';
import { useUiStore } from '@/store/uiStore';

/**
 * Synligt fel-läge för kartans tre dataströmmar. HTTP-fel (backend uppe
 * men svarar fel) hamnar i TanStack Querys error-state — utan den här
 * komponenten skulle kartan bara bli tyst tom.
 *
 * Delar cache-poster med MapContainer/SearchPanel, så inga extra anrop görs.
 */
export default function ErrorBanner() {
  const filters = useUiStore((s) => s.filters);
  const projects = useQuery(projectsQuery(filters));
  const properties = useQuery(propertiesQuery(filters));
  const zones = useQuery(impactZonesQuery(filters));

  const failed = [projects, properties, zones].filter((query) => query.isError);
  if (failed.length === 0) return null;

  const detail = failed
    .map((query) => {
      const error = query.error as { detail?: unknown } | Error | null;
      if (error && typeof error === 'object' && 'detail' in error) {
        return String(error.detail);
      }
      return error instanceof Error ? error.message : null;
    })
    .find(Boolean);

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3 bg-red-500/15 backdrop-blur-sm border border-red-500/40 text-red-300 rounded-lg px-4 py-2 text-sm shadow-lg">
      <CircleAlert className="w-4 h-4 flex-shrink-0" />
      <span>
        <strong>Kunde inte hämta data från backend.</strong>
        {detail ? ` ${detail}` : ''}
      </span>
      <button
        onClick={() => failed.forEach((query) => query.refetch())}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-200 text-xs font-medium transition-colors"
      >
        <RefreshCw className="w-3 h-3" />
        Försök igen
      </button>
    </div>
  );
}
