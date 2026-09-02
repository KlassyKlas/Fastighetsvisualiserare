import { Calendar, FileText, Landmark, MapPin, Tag, Timer, X } from 'lucide-react';
import { FALLBACK_COLOR, PLAN_STATUS_COLORS, SOURCE_LABELS } from '@/config/map';
import { capitalizeFirst, formatDate } from '@/lib/format';
import { geometryAnchor } from '@/lib/isochrone';
import { useUiStore } from '@/store/uiStore';

export default function DetailPlanDetails() {
  const selectedDetailPlan = useUiStore((s) => s.selectedDetailPlan);
  const clearSelection = useUiStore((s) => s.clearSelection);
  const setIsochroneOrigin = useUiStore((s) => s.setIsochroneOrigin);
  const setSidebarTab = useUiStore((s) => s.setSidebarTab);

  if (!selectedDetailPlan) return null;

  const props = selectedDetailPlan.properties;
  const statusColor = (props.status && PLAN_STATUS_COLORS[props.status]) || FALLBACK_COLOR;
  const isochroneAnchor = geometryAnchor(selectedDetailPlan.geometry);
  const metadata = (props.metadata_json ?? {}) as Record<string, unknown>;

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
              {props.status ? capitalizeFirst(props.status) : 'Okänd status'}
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
        {props.plan_number && (
          <div className="flex items-center gap-3 py-2">
            <Tag className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Planbeteckning</p>
              <p className="text-sm text-slate-200">{props.plan_number}</p>
            </div>
          </div>
        )}

        {props.purpose && (
          <div className="flex items-start gap-3 py-2">
            <FileText className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-slate-500">Syfte</p>
              <p className="text-sm text-slate-300 leading-relaxed">{props.purpose}</p>
            </div>
          </div>
        )}

        {props.municipality && (
          <div className="flex items-center gap-3 py-2">
            <MapPin className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Kommun</p>
              <p className="text-sm text-slate-200">{props.municipality}</p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 py-2">
          <Calendar className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-500">Laga kraft</p>
            <p className="text-sm text-slate-200">{formatDate(props.adopted_date)}</p>
          </div>
        </div>

        {typeof metadata.plantyp === 'string' && (
          <div className="flex items-center gap-3 py-2">
            <Landmark className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Plantyp</p>
              <p className="text-sm text-slate-200">{capitalizeFirst(metadata.plantyp)}</p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 py-2">
          <FileText className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-500">Källa</p>
            <p className="text-sm text-slate-200">{SOURCE_LABELS[props.source] ?? props.source}</p>
          </div>
        </div>
      </div>

      {isochroneAnchor && (
        <button
          onClick={() => {
            setIsochroneOrigin({ ...isochroneAnchor, label: props.name });
            setSidebarTab('analysis');
          }}
          className="w-full mt-6 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Timer className="w-4 h-4" />
          Restider härifrån
        </button>
      )}

      <button
        onClick={clearSelection}
        className="w-full mt-3 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
      >
        Stäng
      </button>
    </div>
  );
}
