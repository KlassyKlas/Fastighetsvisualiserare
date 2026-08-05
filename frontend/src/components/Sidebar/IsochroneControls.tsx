import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { Bike, Car, Crosshair, Footprints, MapPin, X } from 'lucide-react';
import { isochroneQuery } from '@/api/isochrone';
import { ISOCHRONE_PROFILE_LABELS } from '@/config/map';
import { ISOCHRONE_MINUTE_CHOICES, MAX_ISOCHRONE_CONTOURS } from '@/lib/isochrone';
import { useUiStore } from '@/store/uiStore';
import type { IsochroneProfile } from '@/domain';

const PROFILE_ICONS: Record<IsochroneProfile, typeof Footprints> = {
  walking: Footprints,
  cycling: Bike,
  driving: Car,
};

const PROFILES = Object.keys(PROFILE_ICONS) as IsochroneProfile[];

/**
 * Kontroller för restidsanalysen (isokroner). Startpunkten sätts via
 * kartklick här eller via "Restider härifrån" i detaljpanelerna;
 * zonerna renderas av IsochroneLayer som delar query-cache med denna.
 */
export default function IsochroneControls() {
  const origin = useUiStore((s) => s.isochroneOrigin);
  const profile = useUiStore((s) => s.isochroneProfile);
  const minutes = useUiStore((s) => s.isochroneMinutes);
  const picking = useUiStore((s) => s.isochronePicking);
  const setProfile = useUiStore((s) => s.setIsochroneProfile);
  const toggleMinute = useUiStore((s) => s.toggleIsochroneMinute);
  const setPicking = useUiStore((s) => s.setIsochronePicking);
  const clearIsochrone = useUiStore((s) => s.clearIsochrone);

  const { isFetching, isError, error } = useQuery(isochroneQuery(origin, profile, minutes));

  const atContourLimit = minutes.length >= MAX_ISOCHRONE_CONTOURS;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
          Restidsanalys
        </h3>
        <p className="text-xs text-slate-500 leading-relaxed">
          Visa hur långt man når från en punkt inom valda restider. Zonerna beräknas av Mapbox på
          verkligt vägnät och fungerar även i demo-läge.
        </p>
      </div>

      {origin ? (
        <div className="flex items-center justify-between gap-2 py-2 px-3 rounded-lg bg-slate-900/50">
          <div className="flex items-center gap-2 min-w-0">
            <MapPin className="w-4 h-4 text-blue-400 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm text-slate-200 truncate">{origin.label}</p>
              <p className="text-[11px] text-slate-500">
                {origin.latitude.toFixed(4)}, {origin.longitude.toFixed(4)}
              </p>
            </div>
          </div>
          <button
            onClick={clearIsochrone}
            className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors flex-shrink-0"
            title="Rensa restidsanalysen"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <p className="text-xs text-slate-500">
          Ingen startpunkt vald — klicka i kartan nedan eller använd &quot;Restider härifrån&quot; i
          en fastighets- eller projektpanel.
        </p>
      )}

      <button
        onClick={() => setPicking(!picking)}
        className={clsx(
          'w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
          picking
            ? 'bg-blue-500/20 text-blue-300 border border-blue-500'
            : 'bg-slate-700 hover:bg-slate-600 text-slate-200 border border-transparent',
        )}
      >
        <Crosshair className="w-4 h-4" />
        {picking ? 'Klicka i kartan — eller avbryt' : 'Välj startpunkt i kartan'}
      </button>

      <div>
        <p className="text-[11px] text-slate-500 mb-1.5">Färdsätt</p>
        <div className="grid grid-cols-3 gap-2">
          {PROFILES.map((key) => {
            const Icon = PROFILE_ICONS[key];
            return (
              <button
                key={key}
                onClick={() => setProfile(key)}
                className={clsx(
                  'flex flex-col items-center gap-1 py-2 rounded-lg border transition-colors',
                  profile === key
                    ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                    : 'border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-600',
                )}
              >
                <Icon className="w-4 h-4" />
                <span className="text-xs font-medium">{ISOCHRONE_PROFILE_LABELS[key]}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <p className="text-[11px] text-slate-500 mb-1.5">Restider (minuter)</p>
        <div className="flex flex-wrap gap-1.5">
          {ISOCHRONE_MINUTE_CHOICES.map((minute) => {
            const selected = minutes.includes(minute);
            const disabled = !selected && atContourLimit;
            return (
              <button
                key={minute}
                onClick={() => toggleMinute(minute)}
                disabled={disabled}
                title={disabled ? `Högst ${MAX_ISOCHRONE_CONTOURS} restider åt gången` : undefined}
                className={clsx(
                  'px-2.5 py-1 rounded-full text-xs font-medium transition-colors',
                  selected
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-500'
                    : disabled
                      ? 'bg-slate-800 text-slate-600 border border-slate-700 cursor-not-allowed'
                      : 'bg-slate-800 text-slate-300 border border-slate-700 hover:border-slate-500',
                )}
              >
                {minute}
              </button>
            );
          })}
        </div>
        {atContourLimit && (
          <p className="text-[11px] text-slate-500 mt-1.5">
            Mapbox tillåter högst {MAX_ISOCHRONE_CONTOURS} restider per analys.
          </p>
        )}
        {origin != null && minutes.length === 0 && (
          <p className="text-[11px] text-amber-400/80 mt-1.5">Välj minst en restid.</p>
        )}
      </div>

      {isFetching && <p className="text-xs text-slate-500">Beräknar restidszoner…</p>}
      {isError && (
        <p className="text-xs text-red-400/90">
          Kunde inte hämta restidszoner: {error instanceof Error ? error.message : 'okänt fel'}
        </p>
      )}
    </div>
  );
}
