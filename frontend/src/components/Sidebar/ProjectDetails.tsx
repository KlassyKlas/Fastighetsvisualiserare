import { X, Calendar, MapPin, Wallet, Radio, Tag, FileText } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { sv } from 'date-fns/locale';
import { useStore } from '@/store/useStore';
import { STATUS_COLORS, STATUS_LABELS, PROJECT_TYPE_LABELS } from '@/config/map';

function formatBudget(sek: number): string {
  if (sek >= 1e9) {
    return (sek / 1e9).toFixed(1).replace('.', ',') + ' mdkr';
  }
  if (sek >= 1e6) {
    return (sek / 1e6).toFixed(1).replace('.', ',') + ' mkr';
  }
  return new Intl.NumberFormat('sv-SE').format(sek) + ' kr';
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Ej angivet';
  try {
    return format(parseISO(dateStr), 'd MMMM yyyy', { locale: sv });
  } catch {
    return dateStr;
  }
}

export default function ProjectDetails() {
  const { selectedProject, clearSelection } = useStore();

  if (!selectedProject) return null;

  const props = selectedProject.properties ?? {};
  const statusColor = STATUS_COLORS[props.status] ?? '#6b7280';

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-slate-100 leading-tight">
            {props.name}
          </h2>
          <div className="flex items-center gap-2 mt-2">
            <span
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              style={{
                backgroundColor: statusColor + '20',
                color: statusColor,
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full mr-1.5"
                style={{ backgroundColor: statusColor }}
              />
              {STATUS_LABELS[props.status] ?? props.status}
            </span>
          </div>
        </div>
        <button
          onClick={clearSelection}
          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
          title="Stang"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Info sections */}
      <div className="space-y-4">
        {/* Project type */}
        <div className="flex items-center gap-3 py-2">
          <Tag className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-500">Projekttyp</p>
            <p className="text-sm text-slate-200">
              {PROJECT_TYPE_LABELS[props.project_type] ?? props.project_type}
            </p>
          </div>
        </div>

        {/* Description */}
        {props.description && (
          <div className="flex items-start gap-3 py-2">
            <FileText className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-slate-500">Beskrivning</p>
              <p className="text-sm text-slate-300 leading-relaxed">
                {props.description}
              </p>
            </div>
          </div>
        )}

        {/* Budget */}
        {props.budget_sek != null && (
          <div className="flex items-center gap-3 py-2">
            <Wallet className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Budget</p>
              <p className="text-sm text-slate-200 font-medium">
                {formatBudget(props.budget_sek)}
              </p>
            </div>
          </div>
        )}

        {/* Timeline */}
        <div className="flex items-center gap-3 py-2">
          <Calendar className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-500">Tidplan</p>
            <p className="text-sm text-slate-200">
              {formatDate(props.start_date)} &ndash; {formatDate(props.end_date)}
            </p>
          </div>
        </div>

        {/* Impact radius */}
        {props.impact_radius_m != null && (
          <div className="flex items-center gap-3 py-2">
            <Radio className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Paverkansradie</p>
              <p className="text-sm text-slate-200">
                {new Intl.NumberFormat('sv-SE').format(props.impact_radius_m)} m
              </p>
            </div>
          </div>
        )}

        {/* Source */}
        {props.source && (
          <div className="flex items-center gap-3 py-2">
            <MapPin className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Kalla</p>
              <p className="text-sm text-slate-200 capitalize">{props.source}</p>
            </div>
          </div>
        )}
      </div>

      {/* Close button */}
      <button
        onClick={clearSelection}
        className="w-full mt-6 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
      >
        Stang
      </button>
    </div>
  );
}
