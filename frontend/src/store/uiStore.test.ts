import { beforeEach, describe, expect, it } from 'vitest';
import { useUiStore } from './uiStore';

const initialState = useUiStore.getState();

beforeEach(() => {
  useUiStore.setState(initialState, true);
});

describe('uiStore', () => {
  it('togglar lagersynlighet', () => {
    expect(useUiStore.getState().layers.terrain).toBe(true);
    useUiStore.getState().toggleLayer('terrain');
    expect(useUiStore.getState().layers.terrain).toBe(false);
  });

  it('togglar statusfilter av och på', () => {
    useUiStore.getState().toggleStatus('planerad');
    expect(useUiStore.getState().filters.statuses).toEqual(['planerad']);
    useUiStore.getState().toggleStatus('planerad');
    expect(useUiStore.getState().filters.statuses).toEqual([]);
  });

  it('val av projekt rensar vald fastighet och öppnar detaljfliken', () => {
    const feature = {
      type: 'Feature',
      geometry: null,
      properties: { id: 1, name: 'Test', source: 'manual', impact_radius_m: 1000 },
    } as never;

    useUiStore.getState().setSelectedProperty(feature);
    useUiStore.getState().setSelectedProject(feature);

    const state = useUiStore.getState();
    expect(state.selectedProject).not.toBeNull();
    expect(state.selectedProperty).toBeNull();
    expect(state.sidebarTab).toBe('details');
  });

  it('clearSelection nollställer valen och går till sök', () => {
    useUiStore.getState().setSelectedProject({
      type: 'Feature',
      geometry: null,
      properties: { id: 1, name: 'Test', source: 'manual', impact_radius_m: 1000 },
    } as never);
    useUiStore.getState().clearSelection();

    const state = useUiStore.getState();
    expect(state.selectedProject).toBeNull();
    expect(state.sidebarTab).toBe('search');
  });

  it('demoMode kan sättas och läsas', () => {
    expect(useUiStore.getState().demoMode).toBe(false);
    useUiStore.getState().setDemoMode(true);
    expect(useUiStore.getState().demoMode).toBe(true);
  });
});
