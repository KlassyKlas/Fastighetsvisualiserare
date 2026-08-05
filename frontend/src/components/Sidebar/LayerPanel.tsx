import { useMutation, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import {
  Box,
  Building2,
  CircleDot,
  Map,
  Mountain,
  RefreshCw,
  Satellite,
  TrainFront,
} from 'lucide-react';
import { useState } from 'react';
import { syncTrafikverket } from '@/api/queries';
import type { LayerVisibility } from '@/domain';
import { useUiStore } from '@/store/uiStore';
import Toggle from '../UI/Toggle';

const layerItems: {
  key: keyof LayerVisibility;
  label: string;
  icon: typeof TrainFront;
}[] = [
  { key: 'infrastructure', label: 'Infrastrukturprojekt', icon: TrainFront },
  { key: 'properties', label: 'Fastigheter', icon: Building2 },
  { key: 'impactZones', label: 'Påverkansområden', icon: CircleDot },
  { key: 'buildings3d', label: '3D-byggnader', icon: Box },
  { key: 'terrain', label: 'Terräng', icon: Mountain },
];

export default function LayerPanel() {
  const layers = useUiStore((s) => s.layers);
  const toggleLayer = useUiStore((s) => s.toggleLayer);
  const mapStyle = useUiStore((s) => s.mapStyle);
  const setMapStyle = useUiStore((s) => s.setMapStyle);
  const demoMode = useUiStore((s) => s.demoMode);

  const queryClient = useQueryClient();
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const syncMutation = useMutation({
    mutationFn: syncTrafikverket,
    onSuccess: (result) => {
      const truncatedNote = result.truncated ? ' — ofullständig hämtning, kör igen' : '';
      setSyncMessage(
        `${result.upserted} objekt synkroniserade (${result.fetched} hämtade, ${result.skipped} överhoppade)${truncatedNote}`,
      );
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['impact-zones'] });
    },
    onError: (error) => {
      const detail =
        typeof error === 'object' && error !== null && 'detail' in error
          ? String((error as { detail: unknown }).detail)
          : 'Kunde inte synkronisera. Kontrollera att backend körs.';
      setSyncMessage(detail);
    },
  });

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Kartlager
        </h3>
        <div className="space-y-2">
          {layerItems.map((item) => (
            <div
              key={item.key}
              className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-700/30 transition-colors"
            >
              <div className="flex items-center gap-3">
                <item.icon className="w-4 h-4 text-slate-400" />
                <span className="text-sm text-slate-200">{item.label}</span>
              </div>
              <Toggle checked={layers[item.key]} onChange={() => toggleLayer(item.key)} />
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Kartstil
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setMapStyle('dark')}
            className={clsx(
              'flex flex-col items-center gap-2 p-3 rounded-lg border transition-colors',
              mapStyle === 'dark'
                ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                : 'border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-600',
            )}
          >
            <Map className="w-5 h-5" />
            <span className="text-xs font-medium">Mörk</span>
          </button>
          <button
            onClick={() => setMapStyle('satellite')}
            className={clsx(
              'flex flex-col items-center gap-2 p-3 rounded-lg border transition-colors',
              mapStyle === 'satellite'
                ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                : 'border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-600',
            )}
          >
            <Satellite className="w-5 h-5" />
            <span className="text-xs font-medium">Satellit</span>
          </button>
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Synkronisering
        </h3>
        <button
          onClick={() => {
            setSyncMessage(null);
            syncMutation.mutate();
          }}
          disabled={syncMutation.isPending || demoMode}
          className={clsx(
            'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors',
            syncMutation.isPending || demoMode
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-500 text-white',
          )}
        >
          <RefreshCw className={clsx('w-4 h-4', syncMutation.isPending && 'animate-spin')} />
          {syncMutation.isPending ? 'Synkroniserar…' : 'Hämta från Trafikverket'}
        </button>
        {demoMode && (
          <p className="text-xs text-amber-400/80 mt-2 text-center">
            Synkronisering kräver att backend körs (demo-läge).
          </p>
        )}
        {syncMessage && <p className="text-xs text-slate-400 mt-2 text-center">{syncMessage}</p>}
      </div>
    </div>
  );
}
