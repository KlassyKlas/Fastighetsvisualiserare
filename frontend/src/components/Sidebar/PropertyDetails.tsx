import { X, MapPin, User, Landmark, Ruler, Home, Calendar, Grid3X3 } from 'lucide-react';
import { useStore } from '@/store/useStore';
import { PROPERTY_TYPE_COLORS, PROPERTY_TYPE_LABELS } from '@/config/map';

function formatCurrency(sek: number): string {
  return new Intl.NumberFormat('sv-SE').format(sek) + ' kr';
}

function formatArea(sqm: number): string {
  return new Intl.NumberFormat('sv-SE').format(sqm) + ' m\u00B2';
}

export default function PropertyDetails() {
  const { selectedProperty, clearSelection } = useStore();

  if (!selectedProperty) return null;

  const props = selectedProperty.properties ?? {};
  const typeColor = PROPERTY_TYPE_COLORS[props.property_type] ?? '#6b7280';

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-slate-100 leading-tight">
            {props.designation}
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            {props.address}, {props.postal_code} {props.city}
          </p>
          <div className="mt-2">
            <span
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
              style={{
                backgroundColor: typeColor + '20',
                color: typeColor,
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full mr-1.5"
                style={{ backgroundColor: typeColor }}
              />
              {PROPERTY_TYPE_LABELS[props.property_type] ?? props.property_type}
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

      <div className="space-y-5">
        {/* Owner section */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Agare
          </h3>
          <div className="bg-slate-900/50 rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-3">
              <User className="w-4 h-4 text-slate-500 flex-shrink-0" />
              <div>
                <p className="text-sm text-slate-200">{props.owner_name}</p>
                {props.owner_org_number && (
                  <p className="text-xs text-slate-500">
                    Org.nr: {props.owner_org_number}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Valuation section */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Vardering
          </h3>
          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-3">
              <Landmark className="w-4 h-4 text-slate-500 flex-shrink-0" />
              <div>
                <p className="text-xs text-slate-500">Taxeringsvarde</p>
                <p className="text-sm text-slate-200 font-medium">
                  {props.assessed_value_sek != null
                    ? formatCurrency(props.assessed_value_sek)
                    : 'Ej angivet'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Property data section */}
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
                  <p className="text-sm text-slate-200">
                    {formatArea(props.area_sqm)}
                  </p>
                </div>
              </div>
            )}

            {props.living_area_sqm != null && (
              <div className="flex items-center gap-3">
                <Home className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <div>
                  <p className="text-xs text-slate-500">Bostadsarea</p>
                  <p className="text-sm text-slate-200">
                    {formatArea(props.living_area_sqm)}
                  </p>
                </div>
              </div>
            )}

            {props.building_year != null && (
              <div className="flex items-center gap-3">
                <Calendar className="w-4 h-4 text-slate-500 flex-shrink-0" />
                <div>
                  <p className="text-xs text-slate-500">Byggar</p>
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

        {/* Location */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Plats
          </h3>
          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-3">
              <MapPin className="w-4 h-4 text-slate-500 flex-shrink-0" />
              <div>
                <p className="text-sm text-slate-200">
                  {props.municipality}, {props.county}
                </p>
              </div>
            </div>
          </div>
        </div>
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
