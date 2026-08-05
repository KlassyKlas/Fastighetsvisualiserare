import { useQuery } from '@tanstack/react-query';
import { proximityScoresQuery } from '@/api/queries';
import {
  ISOCHRONE_PROFILE_LABELS,
  PROPERTY_TYPE_COLORS,
  PROPERTY_TYPE_LABELS,
  SCORE_GRADIENT,
  STATUS_COLORS,
  STATUS_LABELS,
} from '@/config/map';
import { isochroneColorByMinute } from '@/lib/isochrone';
import { useUiStore } from '@/store/uiStore';

const statusEntries = Object.entries(STATUS_COLORS);
const propertyEntries = Object.entries(PROPERTY_TYPE_COLORS);

export default function Legend() {
  const scoreColoring = useUiStore((s) => s.scoreColoring);
  const filters = useUiStore((s) => s.filters);
  const isochroneOrigin = useUiStore((s) => s.isochroneOrigin);
  const isochroneProfile = useUiStore((s) => s.isochroneProfile);
  const isochroneMinutes = useUiStore((s) => s.isochroneMinutes);
  // Gradienten visas först när poängdatat faktiskt renderas på kartan —
  // samma villkor som MapContainer, via samma cachade query.
  const { data: scoreData } = useQuery({
    ...proximityScoresQuery(filters),
    enabled: scoreColoring,
  });
  const showScoreGradient = scoreColoring && scoreData != null;
  // Färgerna är deterministiska utifrån minutvalen — legenden kan visas
  // direkt när en startpunkt finns, även medan zonerna hämtas.
  const isochroneEntries =
    isochroneOrigin != null ? Object.entries(isochroneColorByMinute(isochroneMinutes)) : [];

  return (
    <div className="absolute bottom-6 right-4 z-10 bg-slate-800/90 backdrop-blur-sm border border-slate-700 rounded-lg p-3 shadow-lg min-w-[160px]">
      <div className="mb-3">
        <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Infrastruktur
        </h4>
        <div className="space-y-1">
          {statusEntries.map(([key, color]) => (
            <div key={key} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: color }}
              />
              <span className="text-[11px] text-slate-300">
                {STATUS_LABELS[key as keyof typeof STATUS_LABELS] ?? key}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-slate-700 my-2" />

      {showScoreGradient ? (
        <div>
          <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Närhetspoäng
          </h4>
          <div
            className="h-2 rounded-full"
            style={{
              background: `linear-gradient(to right, ${SCORE_GRADIENT.low}, ${SCORE_GRADIENT.mid}, ${SCORE_GRADIENT.high})`,
            }}
          />
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-slate-500">Låg</span>
            <span className="text-[10px] text-slate-500">Hög</span>
          </div>
        </div>
      ) : (
        <div>
          <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Fastigheter
          </h4>
          <div className="space-y-1">
            {propertyEntries.map(([key, color]) => (
              <div key={key} className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded flex-shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="text-[11px] text-slate-300">
                  {PROPERTY_TYPE_LABELS[key as keyof typeof PROPERTY_TYPE_LABELS] ?? key}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {isochroneEntries.length > 0 && (
        <>
          <div className="border-t border-slate-700 my-2" />
          <div>
            <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Restid ({ISOCHRONE_PROFILE_LABELS[isochroneProfile].toLowerCase()})
            </h4>
            <div className="space-y-1">
              {isochroneEntries.map(([minute, color]) => (
                <div key={minute} className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0 border"
                    style={{ backgroundColor: color + '40', borderColor: color }}
                  />
                  <span className="text-[11px] text-slate-300">≤ {minute} min</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
