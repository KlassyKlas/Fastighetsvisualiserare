import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { Building2, MapPin, Search, TrainFront, Users, X } from 'lucide-react';
import { useMemo } from 'react';
import { ownersQuery, projectsQuery, propertiesQuery } from '@/api/queries';
import type { OwnerSummary, ProjectFeature, PropertyCollection, PropertyFeature } from '@/domain';
import { focusBounds, focusGeometry } from '@/lib/mapBridge';
import { holdingsLabel, holdingsTotal, toBounds } from '@/lib/owners';
import { useUiStore } from '@/store/uiStore';

type SearchHit =
  | { type: 'infrastructure'; feature: ProjectFeature; label: string; sub: string }
  | { type: 'property'; feature: PropertyFeature; label: string; sub: string };

/**
 * Ägarkortet överst i ägarvyn. Antal och summa räknas ur samma mängd —
 * fastighetslistan, som bär alla aktiva filter (även värdefiltret).
 * Ägaraggregatet från PostGIS saknar värdefiltret och är bara reserv
 * när listan trunkerats; se holdingsTotal.
 */
function OwnerCard({
  owner,
  propertyData,
  isPending,
  isError,
  summary,
  searching,
  valueFiltered,
}: {
  owner: string;
  propertyData: PropertyCollection | undefined;
  isPending: boolean;
  isError: boolean;
  summary: OwnerSummary | undefined;
  searching: boolean;
  valueFiltered: boolean;
}) {
  const setOwnerFilter = useUiStore((s) => s.setOwnerFilter);
  const count = propertyData?.numberMatched ?? propertyData?.features.length ?? 0;
  const total = propertyData ? holdingsTotal(propertyData, summary, valueFiltered) : null;
  // Kortet bär innehavets status (laddning/fel) — det är den enda ägarrutan
  // som syns även under pågående sökning, och listan under renderas först
  // när datat finns. Felfallet behövs: ett HTTP-fel (backend uppe men
  // svarar 4xx/5xx) får ingen demo-fallback och skulle annars se ut som
  // en evig laddning. Finns gammalt data kvar efter ett misslyckat
  // omförsök visas det hellre än felet.
  const failed = isError && !propertyData;
  const status = isPending
    ? 'Hämtar innehavet…'
    : failed
      ? 'Kunde inte hämta innehavet från backend.'
      : holdingsLabel(count, total);

  return (
    <div className="bg-slate-900/50 rounded-lg p-3 mb-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3 min-w-0">
          <Users className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-200 leading-snug">
              Visar allt {owner} äger
            </p>
            <p className={clsx('text-xs mt-0.5', failed ? 'text-red-400' : 'text-slate-500')}>
              {status}
            </p>
            {searching && (
              <p className="text-[11px] text-slate-500 mt-1">
                Fastighetsträffar begränsas till ägarens innehav; projekt söks som vanligt.
              </p>
            )}
          </div>
        </div>
        <button
          onClick={() => setOwnerFilter(null)}
          className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs transition-colors flex-shrink-0"
          title="Rensa ägarfiltret"
        >
          <X className="w-3.5 h-3.5" />
          Rensa
        </button>
      </div>
    </div>
  );
}

/** Ägarens fastigheter — visas när sökfältet är tomt i ägarvyn. */
function OwnerHoldings({
  propertyData,
  onSelect,
}: {
  propertyData: PropertyCollection | undefined;
  onSelect: (feature: PropertyFeature) => void;
}) {
  // Laddning och fel visas i ägarkortet ovanför — här finns inget att lista.
  if (!propertyData) return null;
  const features = propertyData.features;
  const truncated =
    propertyData.numberReturned != null &&
    propertyData.numberMatched != null &&
    propertyData.numberReturned < propertyData.numberMatched;

  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
        <Building2 className="w-3.5 h-3.5" />
        Fastigheter
      </h3>
      {features.length === 0 && (
        <p className="text-xs text-slate-500">Inga fastigheter matchar filtren.</p>
      )}
      {features.length > 0 && (
        <div className="space-y-1">
          {features.map((feature) => {
            const props = feature.properties;
            return (
              <button
                key={props.id}
                onClick={() => onSelect(feature)}
                className="w-full flex items-start gap-3 p-3 rounded-lg hover:bg-slate-700/50 transition-colors text-left"
              >
                <div className="mt-0.5 p-1.5 rounded bg-teal-500/20 text-teal-400">
                  <Building2 className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{props.designation}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {[props.address, props.city].filter(Boolean).join(', ') || props.municipality}
                  </p>
                </div>
                <MapPin className="w-3.5 h-3.5 text-slate-600 mt-1 flex-shrink-0" />
              </button>
            );
          })}
        </div>
      )}
      {truncated && (
        <p className="text-[11px] text-slate-500 mt-2">
          Visar {propertyData.numberReturned} av {propertyData.numberMatched} fastigheter.
        </p>
      )}
    </div>
  );
}

/** Topplista över ägare — ersätter tomvyn när varken sökterm eller ägarfilter finns. */
function OwnerList({ onSelect }: { onSelect: (owner: OwnerSummary) => void }) {
  // Smal selector: ägarfrågan nycklar bara på kommunerna, så årsreglaget
  // och statusklick ska inte rendera om topplistan.
  const municipalities = useUiStore((s) => s.filters.municipalities);
  const demoMode = useUiStore((s) => s.demoMode);
  const { data, isPending, isError } = useQuery(ownersQuery({ municipalities }));
  const owners = data?.owners ?? [];

  return (
    <div>
      <p className="text-xs text-slate-600 mb-4">Ange minst 2 tecken för att söka</p>

      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
        <Users className="w-3.5 h-3.5" />
        Ägare
      </h3>

      {demoMode && (
        <p className="text-xs text-amber-400/80 mb-2">
          Demo-läge: ägarlistan beräknas ur exempeldatat.
        </p>
      )}

      {isPending && <p className="text-xs text-slate-500">Hämtar ägare…</p>}
      {isError && <p className="text-xs text-red-400">Kunde inte hämta ägarlistan från backend.</p>}
      {data && owners.length === 0 && (
        <p className="text-xs text-slate-500">Inga ägare matchar filtren.</p>
      )}

      {owners.length > 0 && (
        <div className="space-y-1">
          {owners.map((owner) => {
            const municipalities = owner.municipalities ?? [];
            return (
              <button
                key={owner.owner_name}
                onClick={() => onSelect(owner)}
                className="w-full flex items-start gap-3 p-3 rounded-lg hover:bg-slate-700/50 transition-colors text-left"
                title={`Visa allt ${owner.owner_name} äger`}
              >
                <div className="mt-0.5 p-1.5 rounded bg-violet-500/20 text-violet-400">
                  <Users className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{owner.owner_name}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {holdingsLabel(owner.property_count, owner.total_assessed_value_sek)}
                  </p>
                  {municipalities.length > 0 && (
                    <p className="text-[11px] text-slate-600 truncate">
                      {municipalities.join(', ')}
                    </p>
                  )}
                </div>
                <MapPin className="w-3.5 h-3.5 text-slate-600 mt-1 flex-shrink-0" />
              </button>
            );
          })}
        </div>
      )}

      {data && data.numberReturned < data.numberMatched && (
        <p className="text-[11px] text-slate-500 mt-2">
          Visar {data.numberReturned} av {data.numberMatched} ägare.
        </p>
      )}
    </div>
  );
}

export default function SearchPanel() {
  const searchQuery = useUiStore((s) => s.searchQuery);
  const filters = useUiStore((s) => s.filters);
  const setSearchQuery = useUiStore((s) => s.setSearchQuery);
  const setSelectedProject = useUiStore((s) => s.setSelectedProject);
  const setSelectedProperty = useUiStore((s) => s.setSelectedProperty);
  const setOwnerFilter = useUiStore((s) => s.setOwnerFilter);

  const owner = filters.owner;
  const searching = searchQuery.length >= 2;

  const { data: projectData } = useQuery(projectsQuery(filters));
  // Bär ägarfiltret: i ägarvyn är både sökträffar och innehavslistan
  // redan begränsade till ägaren.
  const {
    data: propertyData,
    isPending: propertiesPending,
    isError: propertiesError,
  } = useQuery(propertiesQuery(filters));
  const { data: ownerData } = useQuery({ ...ownersQuery(filters), enabled: owner != null });
  const ownerSummary = ownerData?.owners?.find((o) => o.owner_name === owner);

  const results = useMemo<SearchHit[]>(() => {
    if (!searching) return [];

    const query = searchQuery.toLowerCase();
    const hits: SearchHit[] = [];

    for (const feature of projectData?.features ?? []) {
      const props = feature.properties;
      const match =
        props.name.toLowerCase().includes(query) ||
        (props.description ?? '').toLowerCase().includes(query) ||
        (props.project_type ?? '').toLowerCase().includes(query);
      if (match) {
        hits.push({
          type: 'infrastructure',
          feature,
          label: props.name,
          sub: [props.project_type, props.status].filter(Boolean).join(' – '),
        });
      }
    }

    for (const feature of propertyData?.features ?? []) {
      const props = feature.properties;
      const match =
        props.designation.toLowerCase().includes(query) ||
        (props.address ?? '').toLowerCase().includes(query) ||
        (props.city ?? '').toLowerCase().includes(query) ||
        (props.municipality ?? '').toLowerCase().includes(query) ||
        (props.owner_name ?? '').toLowerCase().includes(query);
      if (match) {
        hits.push({
          type: 'property',
          feature,
          label: props.designation,
          sub: [props.address, props.city].filter(Boolean).join(', '),
        });
      }
    }

    return hits;
  }, [searching, searchQuery, projectData, propertyData]);

  const handleSelect = (hit: SearchHit) => {
    if (hit.type === 'infrastructure') {
      setSelectedProject(hit.feature);
    } else {
      setSelectedProperty(hit.feature);
    }
    focusGeometry(hit.feature.geometry);
  };

  const handleSelectProperty = (feature: PropertyFeature) => {
    setSelectedProperty(feature);
    focusGeometry(feature.geometry);
  };

  const handleSelectOwner = (summary: OwnerSummary) => {
    setOwnerFilter(summary.owner_name);
    focusBounds(toBounds(summary.extent));
  };

  return (
    <div className="p-4">
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Sök fastighet, adress eller projekt..."
          className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
        />
      </div>

      {owner != null && (
        <OwnerCard
          owner={owner}
          propertyData={propertyData}
          isPending={propertiesPending}
          isError={propertiesError}
          summary={ownerSummary}
          searching={searching}
          valueFiltered={filters.minValue != null || filters.maxValue != null}
        />
      )}

      {searching && results.length === 0 && (
        <p className="text-slate-500 text-sm text-center py-6">Inga resultat hittades</p>
      )}

      {results.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-slate-500 mb-2">{results.length} resultat</p>
          {results.map((hit, i) => (
            <button
              key={`${hit.type}-${hit.feature.properties.id ?? i}`}
              onClick={() => handleSelect(hit)}
              className="w-full flex items-start gap-3 p-3 rounded-lg hover:bg-slate-700/50 transition-colors text-left"
            >
              <div
                className={clsx(
                  'mt-0.5 p-1.5 rounded',
                  hit.type === 'infrastructure'
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-teal-500/20 text-teal-400',
                )}
              >
                {hit.type === 'infrastructure' ? (
                  <TrainFront className="w-3.5 h-3.5" />
                ) : (
                  <Building2 className="w-3.5 h-3.5" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">{hit.label}</p>
                <p className="text-xs text-slate-500 truncate">{hit.sub}</p>
              </div>
              <MapPin className="w-3.5 h-3.5 text-slate-600 mt-1 flex-shrink-0" />
            </button>
          ))}
        </div>
      )}

      {!searching && owner != null && (
        <OwnerHoldings propertyData={propertyData} onSelect={handleSelectProperty} />
      )}

      {!searching && owner == null && <OwnerList onSelect={handleSelectOwner} />}
    </div>
  );
}
