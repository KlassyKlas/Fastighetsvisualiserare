import { CalendarClock, X } from 'lucide-react';
import { useUiStore } from '@/store/uiStore';

const YEAR_MIN = 2005;
const YEAR_MAX = 2040;
const DEFAULT_YEAR = 2026;

/**
 * Tidsreglage: visa kartan som den ser ut ett visst år — vilka projekt
 * är aktiva och vilka påverkanszoner gäller. Tajming är halva affären.
 */
export default function TimelineBar() {
  const year = useUiStore((s) => s.filters.year);
  const setFilters = useUiStore((s) => s.setFilters);

  // I "Alla år"-läget står reglaget redan på standardåret — webbläsaren
  // avfyrar då ingen change-händelse om interaktionen landar på samma
  // värde, så själva beröringen måste aktivera filtret.
  const activate = () => {
    if (year == null) {
      setFilters({ year: DEFAULT_YEAR });
    }
  };

  return (
    <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 flex items-center gap-3 bg-slate-800/90 backdrop-blur-sm border border-slate-700 rounded-xl px-4 py-1.5 shadow-lg">
      <CalendarClock className="w-4 h-4 text-slate-400 flex-shrink-0" />
      <input
        type="range"
        min={YEAR_MIN}
        max={YEAR_MAX}
        value={year ?? DEFAULT_YEAR}
        onChange={(e) => setFilters({ year: Number(e.target.value) })}
        onPointerDown={activate}
        onKeyDown={activate}
        className="w-44 accent-blue-500"
        aria-label="Visa projekt aktiva under år"
        aria-valuetext={year != null ? `År ${year}` : 'Alla år'}
      />
      <span
        className={
          year != null ? 'text-xs font-medium text-blue-400 w-16' : 'text-xs text-slate-500 w-16'
        }
      >
        {year != null ? `År ${year}` : 'Alla år'}
      </span>
      {year != null && (
        <button
          onClick={() => setFilters({ year: null })}
          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
          title="Visa alla år"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
