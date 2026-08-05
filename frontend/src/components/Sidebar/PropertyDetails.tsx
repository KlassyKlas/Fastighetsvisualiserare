import { useQuery } from '@tanstack/react-query';
import {
  Calendar,
  Grid3X3,
  Home,
  Landmark,
  MapPin,
  Radar,
  Ruler,
  Timer,
  User,
  X,
} from 'lucide-react';
import { nearbyProjectsQuery } from '@/api/queries';
import {
  FALLBACK_COLOR,
  PROPERTY_TYPE_COLORS,
  PROPERTY_TYPE_LABELS,
  STATUS_COLORS,
  STATUS_LABELS,
} from '@/config/map';
import { formatArea, formatCurrency, formatDistance } from '@/lib/format';
import { geometryAnchor } from '@/lib/isochrone';
import { useUiStore } from '@/store/uiStore';

/** Närliggande projekt inom denna radie visas i detaljpanelen. */
const NEARBY_MAX_DISTANCE_M = 5000;

function NearbyProjects({ propertyId }: { propertyId: number }) {
  const demoMode = useUiStore((s) => s.demoMode);
  const { data, isPending, isError } = useQuery({
    ...nearbyProjectsQuery(propertyId, NEARBY_MAX_DISTANCE_M),
    enabled: !demoMode,
  });

  if (demoMode) {
    return (
      <p className="text-xs text-slate-500">
        Närhetsanalysen körs i PostGIS och kräver att backend är igång (demo-läge).
      </p>
    );
  }
  if (isPending) {
    return <p className="text-xs text-slate-500">Analyserar närområdet…</p>;
  }
  if (isError || !data) {
    return <p className="text-xs text-slate-500">Kunde inte hämta närliggande projekt.</p>;
  }
  const projects = data.projects ?? [];
  if (projects.length === 0) {
    return (
      <p className="text-xs text-slate-500">
        Inga infrastrukturprojekt inom {formatDistance(NEARBY_MAX_DISTANCE_M)}.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {projects.map((item) => {
        const status = item.project.status;
        const color = (status && STATUS_COLORS[status]) || FALLBACK_COLOR;
        return (
          <div key={item.project.id} className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm text-slate-200 leading-snug">{item.project.name}</p>
              <span className="text-xs text-slate-400 whitespace-nowrap">
                {formatDistance(item.distance_m)}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1.5">
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                style={{ backgroundColor: color + '20', color }}
              >
                {(status && STATUS_LABELS[status]) ?? status ?? 'Okänd'}
              </span>
              {item.within_impact_radius && (
                <span className="text-[11px] text-amber-400">Inom påverkansradien</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function PropertyDetails() {
  const selectedProperty = useUiStore((s) => s.selectedProperty);
  const clearSelection = useUiStore((s) => s.clearSelection);
  const setIsochroneOrigin = useUiStore((s) => s.setIsochroneOrigin);
  const setSidebarTab = useUiStore((s) => s.setSidebarTab);

  if (!selectedProperty) return null;

  const props = selectedProperty.properties;
  const isochroneAnchor = geometryAnchor(selectedProperty.geometry);
  const typeColor =
    (props.property_type && PROPERTY_TYPE_COLORS[props.property_type]) || FALLBACK_COLOR;
  const propertyId = Number(props.id);

  return (
    <div className="p-4">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-slate-100 leading-tight">
            {props.designation}
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            {[props.address, [props.postal_code, props.city].filter(Boolean).join(' ')]
              .filter(Boolean)
              .join(', ')}
          </p>
          <div className="mt-2">
            <span
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              style={{ backgroundColor: typeColor + '20', color: typeColor }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full mr-1.5"
                style={{ backgroundColor: typeColor }}
              />
              {(props.property_type && PROPERTY_TYPE_LABELS[props.property_type]) ??
                props.property_type ??
                'Okänd'}
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

      <div className="space-y-5">
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Ägare
          </h3>
          <div className="bg-slate-900/50 rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-3">
              <User className="w-4 h-4 text-slate-500 flex-shrink-0" />
              <div>
                <p className="text-sm text-slate-200">{props.owner_name ?? 'Okänd'}</p>
                {props.owner_org_number && (
                  <p className="text-xs text-slate-500">Org.nr: {props.owner_org_number}</p>
                )}
              </div>
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Värdering
          </h3>
          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-3">
              <Landmark className="w-4 h-4 text-slate-500 flex-shrink-0" />
              <div>
                <p className="text-xs text-slate-500">Taxeringsvärde</p>
                <p className="text-sm text-slate-200 font-medium">
                  {props.assessed_value_sek != null
                    ? formatCurrency(props.assessed_value_sek)
                    : 'Ej angivet'}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Fastighetsdata
          </h3>
          <div className="bg-slate-900/50 rounded-lg p-3 space-y-3">
            {props.area_sqm != null && (
              <div className="flex items-center gap-3">
                <Ruler className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <div>
                  <p className="text-xs text-slate-500">Tomtarea</p>
                  <p className="text-sm text-slate-200">{formatArea(props.area_sqm)}</p>
                </div>
              </div>
            )}

            {props.living_area_sqm != null && (
              <div className="flex items-center gap-3">
                <Home className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <div>
                  <p className="text-xs text-slate-500">Bostadsarea</p>
                  <p className="text-sm text-slate-200">{formatArea(props.living_area_sqm)}</p>
                </div>
              </div>
            )}

            {props.building_year != null && (
              <div className="flex items-center gap-3">
                <Calendar className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <div>
                  <p className="text-xs text-slate-500">Byggår</p>
                  <p className="text-sm text-slate-200">{props.building_year}</p>
                </div>
              </div>
            )}

            {props.zoning && (
              <div className="flex items-center gap-3">
                <Grid3X3 className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <div>
                  <p className="text-xs text-slate-500">Detaljplan</p>
                  <p className="text-sm text-slate-200">{props.zoning}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Plats
          </h3>
          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-3">
              <MapPin className="w-4 h-4 text-slate-500 flex-shrink-0" />
              <div>
                <p className="text-sm text-slate-200">
                  {[props.municipality, props.county].filter(Boolean).join(', ')}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Radar className="w-3.5 h-3.5" />
            Närliggande projekt
          </h3>
          {Number.isFinite(propertyId) ? (
            <NearbyProjects propertyId={propertyId} />
          ) : (
            <p className="text-xs text-slate-500">Kunde inte identifiera fastigheten.</p>
          )}
        </div>
      </div>

      {isochroneAnchor && (
        <button
          onClick={() => {
            setIsochroneOrigin({ ...isochroneAnchor, label: props.designation });
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
