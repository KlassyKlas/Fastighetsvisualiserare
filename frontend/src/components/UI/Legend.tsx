import {
  PROPERTY_TYPE_COLORS,
  PROPERTY_TYPE_LABELS,
  SCORE_GRADIENT,
  STATUS_COLORS,
  STATUS_LABELS,
} from '@/config/map';
import { useUiStore } from '@/store/uiStore';

const statusEntries = Object.entries(STATUS_COLORS);
const propertyEntries = Object.entries(PROPERTY_TYPE_COLORS);

export default function Legend() {
  const scoreColoring = useUiStore((s) => s.scoreColoring);

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

      {scoreColoring ? (
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
    </div>
  );
}
