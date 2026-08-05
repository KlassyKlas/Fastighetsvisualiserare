import { useState } from 'react';
import {
  Map,
  Satellite,
  RefreshCw,
  TrainFront,
  Building2,
  CircleDot,
  Box,
  Mountain,
} from 'lucide-react';
import clsx from 'clsx';
import { useStore } from '@/store/useStore';
import { syncTrafikverket } from '@/services/api';
import type { LayerVisibility } from '@/types';

const layerItems: {
  key: keyof LayerVisibility;
  label: string;
  icon: typeof TrainFront;
}[] = [
  { key: 'infrastructure', label: 'Infrastrukturprojekt', icon: TrainFront },
  { key: 'properties', label: 'Fastigheter', icon: Building2 },
  { key: 'impactZones', label: 'Paverkansomraden', icon: CircleDot },
  { key: 'buildings3d', label: '3D-byggnader', icon: Box },
  { key: 'terrain', label: 'Terrang', icon: Mountain },
];

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      onClick={onChange}
      className={clsx(
        'relative w-10 h-5 rounded-full transition-colors flex-shrink-0',
        checked ? 'bg-blue-500' : 'bg-slate-600',
      )}
    >
      <div
        className={clsx(
          'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-sm',
          checked ? 'translate-x-5' : 'translate-x-0.5',
        )}
      />
    </button>
  );
}

export default function LayerPanel() {
  const { layers, toggleLayer, mapStyle, setMapStyle } = useStore();
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await syncTrafikverket();
      setSyncResult(`${result.count} projekt synkroniserade`);
    } catch {
      setSyncResult('Kunde inte synkronisera. Kontrollera att backend kors.');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="p-4 space-y-6">
      {/* Map layers section */}
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
              <Toggle
                checked={layers[item.key]}
                onChange={() => toggleLayer(item.key)}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Map style section */}
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
            <span className="text-xs font-medium">Mork</span>
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

      {/* Sync section */}
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Synkronisering
        </h3>
        <button
          onClick={handleSync}
          disabled={syncing}
          className={clsx(
            'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors',
            syncing
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-500 text-white',
          )}
        >
          <RefreshCw
            className={clsx('w-4 h-4', syncing && 'animate-spin')}
          />
          {syncing ? 'Synkroniserar...' : 'Hamta fran Trafikverket'}
        </button>
        {syncResult && (
          <p className="text-xs text-slate-400 mt-2 text-center">
            {syncResult}
          </p>
        )}
      </div>
    </div>
  );
}
