import { useMemo } from 'react';
import { Search, MapPin, Building2, TrainFront } from 'lucide-react';
import clsx from 'clsx';
import { useStore } from '@/store/useStore';
import { useInfrastructure, useProperties } from '@/hooks/useData';
import type { Feature } from 'geojson';

export default function SearchPanel() {
  const { searchQuery, setSearchQuery, setSelectedProject, setSelectedProperty } =
    useStore();
  const { data: infraData } = useInfrastructure();
  const { data: propData } = useProperties();

  const results = useMemo(() => {
    if (!searchQuery || searchQuery.length < 2) return [];

    const query = searchQuery.toLowerCase();
    const items: { feature: Feature; type: 'infrastructure' | 'property'; label: string; sub: string }[] = [];

    if (infraData) {
      for (const f of infraData.features) {
        const props = f.properties;
        if (!props) continue;
        const match =
          props.name?.toLowerCase().includes(query) ||
          props.description?.toLowerCase().includes(query) ||
          props.project_type?.toLowerCase().includes(query);
        if (match) {
          items.push({
            feature: f,
            type: 'infrastructure',
            label: props.name,
            sub: props.project_type + ' - ' + props.status,
          });
        }
      }
    }

    if (propData) {
      for (const f of propData.features) {
        const props = f.properties;
        if (!props) continue;
        const match =
          props.designation?.toLowerCase().includes(query) ||
          props.address?.toLowerCase().includes(query) ||
          props.city?.toLowerCase().includes(query) ||
          props.municipality?.toLowerCase().includes(query) ||
          props.owner_name?.toLowerCase().includes(query);
        if (match) {
          items.push({
            feature: f,
            type: 'property',
            label: props.designation,
            sub: props.address + ', ' + props.city,
          });
        }
      }
    }

    return items;
  }, [searchQuery, infraData, propData]);

  const handleSelect = (item: (typeof results)[number]) => {
    if (item.type === 'infrastructure') {
      setSelectedProject(item.feature);
    } else {
      setSelectedProperty(item.feature);
    }
  };

  return (
    <div className="p-4">
      {/* Search input */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Sok fastighet, adress eller projekt..."
          className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
        />
      </div>

      {/* Results */}
      {searchQuery.length >= 2 && results.length === 0 && (
        <p className="text-slate-500 text-sm text-center py-6">
          Inga resultat hittades
        </p>
      )}

      {results.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-slate-500 mb-2">
            {results.length} resultat
          </p>
          {results.map((item, i) => (
            <button
              key={`${item.type}-${item.feature.properties?.id ?? i}`}
              onClick={() => handleSelect(item)}
              className="w-full flex items-start gap-3 p-3 rounded-lg hover:bg-slate-700/50 transition-colors text-left"
            >
              <div
                className={clsx(
                  'mt-0.5 p-1.5 rounded',
                  item.type === 'infrastructure'
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-teal-500/20 text-teal-400',
                )}
              >
                {item.type === 'infrastructure' ? (
                  <TrainFront className="w-3.5 h-3.5" />
                ) : (
                  <Building2 className="w-3.5 h-3.5" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">
                  {item.label}
                </p>
                <p className="text-xs text-slate-500 truncate">{item.sub}</p>
              </div>
              <MapPin className="w-3.5 h-3.5 text-slate-600 mt-1 flex-shrink-0" />
            </button>
          ))}
        </div>
      )}

      {/* Empty state */}
      {(!searchQuery || searchQuery.length < 2) && (
        <div className="text-center py-8">
          <Search className="w-8 h-8 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Sok bland fastigheter och infrastrukturprojekt</p>
          <p className="text-slate-600 text-xs mt-1">
            Ange minst 2 tecken for att soka
          </p>
        </div>
      )}
    </div>
  );
}
