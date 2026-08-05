import { Calendar, FileText, MapPin, Radio, Tag, Wallet, X } from 'lucide-react';
import {
  FALLBACK_COLOR,
  PROJECT_TYPE_LABELS,
  SOURCE_LABELS,
  STATUS_COLORS,
  STATUS_LABELS,
} from '@/config/map';
import { formatDate, formatSek } from '@/lib/format';
import { useUiStore } from '@/store/uiStore';

export default function ProjectDetails() {
  const selectedProject = useUiStore((s) => s.selectedProject);
  const clearSelection = useUiStore((s) => s.clearSelection);

  if (!selectedProject) return null;

  const props = selectedProject.properties;
  const statusColor = (props.status && STATUS_COLORS[props.status]) || FALLBACK_COLOR;

  return (
    <div className="p-4">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-slate-100 leading-tight">{props.name}</h2>
          <div className="flex items-center gap-2 mt-2">
            <span
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              style={{ backgroundColor: statusColor + '20', color: statusColor }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full mr-1.5"
                style={{ backgroundColor: statusColor }}
              />
              {(props.status && STATUS_LABELS[props.status]) ?? props.status ?? 'Okänd'}
            </span>
          </div>
        </div>
        <button
          onClick={clearSelection}
          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
          title="Stäng"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-4">
        <div className="flex items-center gap-3 py-2">
          <Tag className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-500">Projekttyp</p>
            <p className="text-sm text-slate-200">
              {(props.project_type && PROJECT_TYPE_LABELS[props.project_type]) ??
                props.project_type ??
                'Okänd'}
            </p>
          </div>
        </div>

        {props.description && (
          <div className="flex items-start gap-3 py-2">
            <FileText className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-slate-500">Beskrivning</p>
              <p className="text-sm text-slate-300 leading-relaxed">{props.description}</p>
            </div>
          </div>
        )}

        {props.budget_sek != null && (
          <div className="flex items-center gap-3 py-2">
            <Wallet className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Budget</p>
              <p className="text-sm text-slate-200 font-medium">{formatSek(props.budget_sek)}</p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 py-2">
          <Calendar className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-500">Tidplan</p>
            <p className="text-sm text-slate-200">
              {formatDate(props.start_date)} &ndash; {formatDate(props.end_date)}
            </p>
          </div>
        </div>

        {props.impact_radius_m != null && (
          <div className="flex items-center gap-3 py-2">
            <Radio className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Påverkansradie</p>
              <p className="text-sm text-slate-200">
                {new Intl.NumberFormat('sv-SE').format(props.impact_radius_m)} m
              </p>
            </div>
          </div>
        )}

        {props.source && (
          <div className="flex items-center gap-3 py-2">
            <MapPin className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Källa</p>
              <p className="text-sm text-slate-200">{SOURCE_LABELS[props.source] ?? props.source}</p>
            </div>
          </div>
        )}
      </div>

      <button
        onClick={clearSelection}
        className="w-full mt-6 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
      >
        Stäng
      </button>
    </div>
  );
}
