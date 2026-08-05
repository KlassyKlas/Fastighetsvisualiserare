import {
  PROPERTY_TYPE_COLORS,
  PROPERTY_TYPE_LABELS,
  STATUS_COLORS,
  STATUS_LABELS,
} from '@/config/map';

const statusEntries = Object.entries(STATUS_COLORS);
const propertyEntries = Object.entries(PROPERTY_TYPE_COLORS);

export default function Legend() {
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
    </div>
  );
}
