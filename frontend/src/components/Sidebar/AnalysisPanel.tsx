import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { Info, Palette } from 'lucide-react';
import { proximityScoresQuery } from '@/api/queries';
import { formatDistance } from '@/lib/format';
import { useUiStore } from '@/store/uiStore';
import Toggle from '../UI/Toggle';
import type { PropertyFeature, ProximityScoreFeature } from '@/domain';

function scoreChipClasses(score: number, maxScore: number): string {
  const ratio = maxScore > 0 ? score / maxScore : 0;
  if (ratio > 0.66) return 'bg-amber-500/20 text-amber-300';
  if (ratio > 0.33) return 'bg-sky-500/20 text-sky-300';
  return 'bg-slate-600/40 text-slate-300';
}

export default function AnalysisPanel() {
  const filters = useUiStore((s) => s.filters);
  const demoMode = useUiStore((s) => s.demoMode);
  const scoreColoring = useUiStore((s) => s.scoreColoring);
  const setScoreColoring = useUiStore((s) => s.setScoreColoring);
  const setSelectedProperty = useUiStore((s) => s.setSelectedProperty);

  const { data, isPending, isError } = useQuery(proximityScoresQuery(filters));

  const features = data?.features ?? [];
  const maxScore = features.length > 0 ? features[0].properties.score : 0;

  const handleSelect = (feature: ProximityScoreFeature) => {
    // ProximityScoreProps är en utökning av PropertyProps —
    // detaljpanelen fungerar rakt av.
    setSelectedProperty(feature as unknown as PropertyFeature);
  };

  return (
    <div className="p-4 space-y-4">
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
          Närhetspoäng
        </h3>
        <p className="text-xs text-slate-500 leading-relaxed">
          Fastigheter rankade efter närhet till infrastrukturprojekt, viktat på projekttyp, status,
          avstånd, budget och tid till färdigställande. Klicka på ett bidrag i detaljpanelen för att
          förstå poängen.
        </p>
      </div>

      <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-slate-900/50">
        <div className="flex items-center gap-3">
          <Palette className="w-4 h-4 text-slate-400" />
          <span className="text-sm text-slate-200">Färga kartan efter poäng</span>
        </div>
        <Toggle checked={scoreColoring} onChange={() => setScoreColoring(!scoreColoring)} />
      </div>

      {demoMode && (
        <p className="flex items-start gap-2 text-xs text-amber-400/80">
          <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          Demo-läge: poängen är förberäknade ur exempeldatat och påverkas inte av filtren.
        </p>
      )}

      {isPending && <p className="text-xs text-slate-500">Beräknar närhetspoäng…</p>}
      {isError && <p className="text-xs text-slate-500">Kunde inte hämta poängen från backend.</p>}

      {features.length > 0 && (
        <div className="space-y-1">
          {features.map((feature) => {
            const props = feature.properties;
            const topContribution = props.contributions?.[0];
            return (
              <button
                key={props.id}
                onClick={() => handleSelect(feature)}
                className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-slate-700/50 transition-colors text-left"
              >
                <span className="w-6 text-center text-xs font-semibold text-slate-500 flex-shrink-0">
                  {props.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{props.designation}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {topContribution
                      ? `${topContribution.name} · ${formatDistance(topContribution.distance_m)}`
                      : props.municipality}
                  </p>
                </div>
                <span
                  className={clsx(
                    'px-2 py-0.5 rounded-full text-xs font-semibold flex-shrink-0',
                    scoreChipClasses(props.score, maxScore),
                  )}
                >
                  {props.score.toFixed(0)}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {!isPending && !isError && features.length === 0 && (
        <p className="text-xs text-slate-500">
          Inga fastigheter inom {formatDistance(data?.max_distance_m ?? 5000)} från något projekt
          som matchar filtren.
        </p>
      )}
    </div>
  );
}
