import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { Building2, MapPin, Search, TrainFront } from 'lucide-react';
import { useMemo } from 'react';
import { projectsQuery, propertiesQuery } from '@/api/queries';
import type { ProjectFeature, PropertyFeature } from '@/domain';
import { focusGeometry } from '@/lib/mapBridge';
import { useUiStore } from '@/store/uiStore';

type SearchHit =
  | { type: 'infrastructure'; feature: ProjectFeature; label: string; sub: string }
  | { type: 'property'; feature: PropertyFeature; label: string; sub: string };

export default function SearchPanel() {
  const searchQuery = useUiStore((s) => s.searchQuery);
  const filters = useUiStore((s) => s.filters);
  const setSearchQuery = useUiStore((s) => s.setSearchQuery);
  const setSelectedProject = useUiStore((s) => s.setSelectedProject);
  const setSelectedProperty = useUiStore((s) => s.setSelectedProperty);

  const { data: projectData } = useQuery(projectsQuery(filters));
  const { data: propertyData } = useQuery(propertiesQuery(filters));

  const results = useMemo<SearchHit[]>(() => {
    if (!searchQuery || searchQuery.length < 2) return [];

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
  }, [searchQuery, projectData, propertyData]);

  const handleSelect = (hit: SearchHit) => {
    if (hit.type === 'infrastructure') {
      setSelectedProject(hit.feature);
    } else {
      setSelectedProperty(hit.feature);
    }
    focusGeometry(hit.feature.geometry);
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

      {searchQuery.length >= 2 && results.length === 0 && (
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

      {(!searchQuery || searchQuery.length < 2) && (
        <div className="text-center py-8">
          <Search className="w-8 h-8 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Sök bland fastigheter och infrastrukturprojekt</p>
          <p className="text-slate-600 text-xs mt-1">Ange minst 2 tecken för att söka</p>
        </div>
      )}
    </div>
  );
}
