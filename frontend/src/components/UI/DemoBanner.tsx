import { TriangleAlert } from 'lucide-react';
import { useUiStore } from '@/store/uiStore';

/**
 * Synlig indikator för demo-läget. Den gamla appen föll tyst tillbaka på
 * exempeldata när backend inte nåddes — det här gör läget omöjligt att missa.
 */
export default function DemoBanner() {
  const demoMode = useUiStore((s) => s.demoMode);

  if (!demoMode) return null;

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 bg-amber-500/15 backdrop-blur-sm border border-amber-500/40 text-amber-300 rounded-lg px-4 py-2 text-sm shadow-lg">
      <TriangleAlert className="w-4 h-4 flex-shrink-0" />
      <span>
        <strong>Demo-läge:</strong> backend nås inte — visar exempeldata. Närhetsanalys och
        synkronisering är avstängda.
      </span>
    </div>
  );
}
