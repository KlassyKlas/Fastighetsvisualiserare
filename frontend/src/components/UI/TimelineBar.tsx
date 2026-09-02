import { CalendarClock, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { DEFAULT_YEAR, YEAR_MAX, YEAR_MIN } from '@/config/map';
import { useUiStore } from '@/store/uiStore';

/** Varje årssteg avfyrar tre serverfrågor (projekt, zoner, poäng) —
 * zonfrågan buffrar dessutom korridorgeometrier i databasen. Filtret
 * uppdateras därför först när draget vilat en stund. */
const COMMIT_DELAY_MS = 200;

/**
 * Tidsreglage: visa kartan som den ser ut ett visst år — vilka projekt
 * är aktiva och vilka påverkanszoner gäller. Tajming är halva affären.
 */
export default function TimelineBar() {
  const year = useUiStore((s) => s.filters.year);
  const setFilters = useUiStore((s) => s.setFilters);

  // Reglaget och etiketten följer draftYear direkt; store-filtret (och
  // därmed API-anropen) uppdateras debouncat. Ändras året utifrån
  // (t.ex. filterrensning) justeras utkastet under renderingen.
  const [draftYear, setDraftYear] = useState<number | null>(year);
  const [syncedYear, setSyncedYear] = useState<number | null>(year);
  if (year !== syncedYear) {
    setSyncedYear(year);
    setDraftYear(year);
  }

  const commitTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(commitTimer.current), []);

  const commitDebounced = (value: number) => {
    setDraftYear(value);
    window.clearTimeout(commitTimer.current);
    commitTimer.current = window.setTimeout(() => setFilters({ year: value }), COMMIT_DELAY_MS);
  };

  // I "Alla år"-läget står reglaget redan på standardåret — webbläsaren
  // avfyrar då ingen change-händelse om interaktionen landar på samma
  // värde, så själva beröringen måste aktivera filtret.
  const activate = () => {
    if (year == null && draftYear == null) {
      commitDebounced(DEFAULT_YEAR);
    }
  };

  const clear = () => {
    window.clearTimeout(commitTimer.current);
    setDraftYear(null);
    setFilters({ year: null });
  };

  return (
    <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 flex items-center gap-3 bg-slate-800/90 backdrop-blur-sm border border-slate-700 rounded-xl px-4 py-1.5 shadow-lg">
      <CalendarClock className="w-4 h-4 text-slate-400 flex-shrink-0" />
      <input
        type="range"
        min={YEAR_MIN}
        max={YEAR_MAX}
        value={draftYear ?? DEFAULT_YEAR}
        onChange={(e) => commitDebounced(Number(e.target.value))}
        onPointerDown={activate}
        onKeyDown={activate}
        className="w-44 accent-blue-500"
        aria-label="Visa projekt aktiva under år"
        aria-valuetext={draftYear != null ? `År ${draftYear}` : 'Alla år'}
      />
      <span
        className={
          draftYear != null
            ? 'text-xs font-medium text-blue-400 w-16'
            : 'text-xs text-slate-500 w-16'
        }
      >
        {draftYear != null ? `År ${draftYear}` : 'Alla år'}
      </span>
      {draftYear != null && (
        <button
          onClick={clear}
          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
          title="Visa alla år"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
