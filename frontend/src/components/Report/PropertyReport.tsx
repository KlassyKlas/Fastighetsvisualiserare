import { useQuery } from '@tanstack/react-query';
import { Printer, X } from 'lucide-react';
import { desoLookupQuery, nearbyProjectsQuery, proximityScoresQuery } from '@/api/queries';
import {
  MAPBOX_TOKEN,
  PROJECT_TYPE_LABELS,
  PROPERTY_TYPE_LABELS,
  STATUS_LABELS,
} from '@/config/map';
import { EMPTY_FILTERS } from '@/domain';
import { formatArea, formatCurrency, formatDistance, formatPercent } from '@/lib/format';
import { geometryAnchor } from '@/lib/isochrone';
import { useUiStore } from '@/store/uiStore';

const numberFormat = new Intl.NumberFormat('sv-SE');
const dateFormat = new Intl.DateTimeFormat('sv-SE', { dateStyle: 'long', timeStyle: 'short' });

/** Närliggande projekt inom denna radie tas med i rapporten. */
const NEARBY_MAX_DISTANCE_M = 5000;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 break-inside-avoid">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 border-b border-slate-300 pb-1 mb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

function FactRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (value == null) return null;
  return (
    <div className="flex justify-between gap-4 py-1 border-b border-slate-100 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-900 text-right">{value}</span>
    </div>
  );
}

/**
 * Utskriftsvänlig objektsrapport för en fastighet. Exporten sker via
 * webbläsarens utskriftsdialog (Skriv ut → Spara som PDF) — print-CSS i
 * index.css ser till att bara rapporten skrivs ut.
 */
export default function PropertyReport() {
  const reportProperty = useUiStore((s) => s.reportProperty);
  const setReportProperty = useUiStore((s) => s.setReportProperty);
  const demoMode = useUiStore((s) => s.demoMode);

  const props = reportProperty?.properties;
  const propertyId = props ? Number(props.id) : NaN;
  const anchor = geometryAnchor(reportProperty?.geometry);

  // Poängen hämtas OFILTRERAT — rapporten ska vara stabil oavsett vilka
  // kartfilter som råkar vara aktiva när den skapas.
  const { data: scoreData } = useQuery({
    ...proximityScoresQuery(EMPTY_FILTERS),
    enabled: reportProperty != null,
  });
  const { data: nearbyData } = useQuery({
    ...nearbyProjectsQuery(Number.isFinite(propertyId) ? propertyId : 0, NEARBY_MAX_DISTANCE_M),
    enabled: reportProperty != null && Number.isFinite(propertyId) && !demoMode,
  });
  const { data: desoData } = useQuery({
    ...desoLookupQuery(anchor?.longitude ?? 0, anchor?.latitude ?? 0),
    enabled: reportProperty != null && anchor != null && !demoMode,
  });

  if (!reportProperty || !props) return null;

  const scoreFeature = scoreData?.features.find((f) => f.properties.id === props.id);
  const contributions = scoreFeature?.properties.contributions ?? [];
  const nearbyProjects = nearbyData?.projects ?? [];
  const deso = desoData?.properties;

  const staticMapUrl =
    MAPBOX_TOKEN && anchor
      ? `https://api.mapbox.com/styles/v1/mapbox/light-v11/static/pin-s+2563eb(${anchor.longitude.toFixed(5)},${anchor.latitude.toFixed(5)})/${anchor.longitude.toFixed(5)},${anchor.latitude.toFixed(5)},13.5,0/700x320@2x?access_token=${MAPBOX_TOKEN}`
      : null;

  return (
    <div className="print-report fixed inset-0 z-50 overflow-y-auto bg-slate-200/95">
      <div className="max-w-3xl mx-auto my-6 print:my-0 bg-white text-slate-900 rounded-lg print:rounded-none shadow-xl print:shadow-none">
        {/* Verktygsrad — följer inte med till utskriften */}
        <div className="flex items-center justify-between gap-2 px-6 py-3 border-b border-slate-200 print:hidden">
          <p className="text-sm text-slate-500">Objektsrapport</p>
          <div className="flex gap-2">
            <button
              onClick={() => window.print()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Printer className="w-4 h-4" />
              Skriv ut / spara som PDF
            </button>
            <button
              onClick={() => setReportProperty(null)}
              className="flex items-center gap-2 px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-sm transition-colors"
            >
              <X className="w-4 h-4" />
              Stäng
            </button>
          </div>
        </div>

        <div className="px-8 py-6">
          <header className="mb-6">
            <p className="text-xs uppercase tracking-widest text-slate-400 mb-1">
              Objektsrapport · Fastighetsvisualiseraren
            </p>
            <h1 className="text-2xl font-bold leading-tight">{props.designation}</h1>
            <p className="text-sm text-slate-500 mt-1">
              {[props.address, [props.postal_code, props.city].filter(Boolean).join(' ')]
                .filter(Boolean)
                .join(', ') || [props.municipality, props.county].filter(Boolean).join(', ')}
            </p>
            <p className="text-xs text-slate-400 mt-2">
              Genererad {dateFormat.format(new Date())}
              {demoMode ? ' · baserad på exempeldata (demo-läge)' : ''}
            </p>
          </header>

          {staticMapUrl && (
            <img
              src={staticMapUrl}
              alt={`Karta över ${props.designation}`}
              className="w-full rounded border border-slate-200 mb-6 break-inside-avoid"
            />
          )}

          <Section title="Fastighetsfakta">
            <div className="grid grid-cols-2 gap-x-8">
              <div>
                <FactRow
                  label="Fastighetstyp"
                  value={
                    (props.property_type && PROPERTY_TYPE_LABELS[props.property_type]) ??
                    props.property_type
                  }
                />
                <FactRow
                  label="Kommun"
                  value={[props.municipality, props.county].filter(Boolean).join(', ') || null}
                />
                <FactRow
                  label="Tomtarea"
                  value={props.area_sqm != null ? formatArea(props.area_sqm) : null}
                />
                <FactRow
                  label="Bostadsarea"
                  value={props.living_area_sqm != null ? formatArea(props.living_area_sqm) : null}
                />
                <FactRow label="Byggår" value={props.building_year?.toString()} />
              </div>
              <div>
                <FactRow
                  label="Taxeringsvärde"
                  value={
                    props.assessed_value_sek != null
                      ? formatCurrency(props.assessed_value_sek)
                      : 'Ej angivet'
                  }
                />
                <FactRow label="Ägare" value={props.owner_name ?? 'Okänd'} />
                <FactRow label="Org.nr" value={props.owner_org_number} />
                <FactRow label="Detaljplan" value={props.zoning} />
              </div>
            </div>
          </Section>

          <Section title="Närhetspoäng">
            {scoreFeature ? (
              <>
                <p className="text-sm mb-3">
                  <span className="text-3xl font-bold text-blue-700">
                    {numberFormat.format(scoreFeature.properties.score)}
                  </span>{' '}
                  <span className="text-slate-500">
                    poäng · plats {scoreFeature.properties.rank} av{' '}
                    {scoreData?.numberMatched ?? '–'} i analysen
                  </span>
                </p>
                {contributions.length > 0 && (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-slate-500 border-b border-slate-300">
                        <th className="py-1 pr-2 font-medium">Projekt</th>
                        <th className="py-1 pr-2 font-medium">Typ</th>
                        <th className="py-1 pr-2 font-medium">Status</th>
                        <th className="py-1 pr-2 font-medium text-right">Avstånd</th>
                        <th className="py-1 font-medium text-right">Poäng</th>
                      </tr>
                    </thead>
                    <tbody>
                      {contributions.map((c) => (
                        <tr key={c.project_id} className="border-b border-slate-100">
                          <td className="py-1 pr-2">{c.name}</td>
                          <td className="py-1 pr-2 text-slate-500">
                            {(c.project_type && PROJECT_TYPE_LABELS[c.project_type]) ?? '–'}
                          </td>
                          <td className="py-1 pr-2 text-slate-500">
                            {(c.status && STATUS_LABELS[c.status]) ?? '–'}
                          </td>
                          <td className="py-1 pr-2 text-right">{formatDistance(c.distance_m)}</td>
                          <td className="py-1 text-right font-medium">
                            {numberFormat.format(c.points)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            ) : (
              <p className="text-sm text-slate-500">
                Fastigheten har inga poänggivande projekt inom analysens sökradie.
              </p>
            )}
          </Section>

          <Section title={`Närliggande projekt (inom ${formatDistance(NEARBY_MAX_DISTANCE_M)})`}>
            {demoMode ? (
              <p className="text-sm text-slate-500">
                Närhetsanalysen körs i PostGIS och kräver att backend är igång (demo-läge).
              </p>
            ) : nearbyProjects.length > 0 ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-300">
                    <th className="py-1 pr-2 font-medium">Projekt</th>
                    <th className="py-1 pr-2 font-medium">Status</th>
                    <th className="py-1 pr-2 font-medium text-right">Avstånd</th>
                    <th className="py-1 font-medium text-right">Inom påverkansradie</th>
                  </tr>
                </thead>
                <tbody>
                  {nearbyProjects.map((item) => (
                    <tr key={item.project.id} className="border-b border-slate-100">
                      <td className="py-1 pr-2">{item.project.name}</td>
                      <td className="py-1 pr-2 text-slate-500">
                        {(item.project.status && STATUS_LABELS[item.project.status]) ?? '–'}
                      </td>
                      <td className="py-1 pr-2 text-right">{formatDistance(item.distance_m)}</td>
                      <td className="py-1 text-right">
                        {item.within_impact_radius ? 'Ja' : 'Nej'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-slate-500">
                Inga infrastrukturprojekt inom {formatDistance(NEARBY_MAX_DISTANCE_M)}.
              </p>
            )}
          </Section>

          <Section title="Områdesstatistik (DeSO)">
            {demoMode ? (
              <p className="text-sm text-slate-500">
                Områdesuppslaget körs i PostGIS och kräver att backend är igång (demo-läge).
              </p>
            ) : deso ? (
              <>
                <div className="grid grid-cols-2 gap-x-8">
                  <div>
                    <FactRow
                      label={`Befolkning${deso.population_year ? ` (${deso.population_year})` : ''}`}
                      value={deso.population != null ? numberFormat.format(deso.population) : null}
                    />
                    <FactRow
                      label="Befolkningstäthet"
                      value={
                        deso.population_density != null
                          ? `${numberFormat.format(Math.round(deso.population_density))} inv/km²`
                          : null
                      }
                    />
                  </div>
                  <div>
                    <FactRow
                      label="Medelinkomst (netto)"
                      value={
                        deso.mean_income_sek != null ? formatCurrency(deso.mean_income_sek) : null
                      }
                    />
                    <FactRow
                      label="Eftergymnasial utbildning"
                      value={
                        deso.higher_education_share != null
                          ? formatPercent(deso.higher_education_share)
                          : null
                      }
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  DeSO {deso.deso_code}
                  {deso.municipality ? ` · ${deso.municipality}` : ''} · Källa: SCB
                </p>
              </>
            ) : (
              <p className="text-sm text-slate-500">
                Ingen områdesstatistik — synkronisera SCB-källan under Lager.
              </p>
            )}
          </Section>

          <footer className="mt-8 pt-3 border-t border-slate-200 text-xs text-slate-400">
            <p>
              Källor: Trafikverket (trafikinformation och nationell plan), Lantmäteriet
              (detaljplaner), SCB (demografi per DeSO). Närhetspoängen är en transparent
              modellberäkning — se bidragen ovan — och utgör inte investeringsrådgivning.
            </p>
          </footer>
        </div>
      </div>
    </div>
  );
}
