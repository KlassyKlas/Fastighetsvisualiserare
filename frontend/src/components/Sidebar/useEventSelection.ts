import { useCallback } from 'react';
import { focusGeometry } from '@/lib/mapBridge';
import { useUiStore } from '@/store/uiStore';
import type { EventSelection } from './EventList';

/**
 * Klick på en händelserad: öppna detaljpanelen och zooma kartan dit.
 * Delas av bevakningarna och "Nytt sedan senast" så att beteendet är
 * identiskt. Geometri kan saknas (/changes filtrerar inte på den) —
 * focusGeometry gör då ingenting och bara detaljpanelen öppnas.
 */
export function useEventSelection(): (selection: EventSelection) => void {
  const setSelectedProject = useUiStore((s) => s.setSelectedProject);
  const setSelectedDetailPlan = useUiStore((s) => s.setSelectedDetailPlan);

  return useCallback(
    (selection: EventSelection) => {
      if (selection.kind === 'project') {
        setSelectedProject(selection.feature);
      } else {
        setSelectedDetailPlan(selection.feature);
      }
      focusGeometry(selection.feature.geometry);
    },
    [setSelectedDetailPlan, setSelectedProject],
  );
}
