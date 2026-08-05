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

  it('val av detaljplan rensar övriga val och öppnar detaljfliken', () => {
    const feature = {
      type: 'Feature',
      geometry: null,
      properties: { id: 1, external_id: 'x', name: 'Plan', source: 'manual' },
    } as never;

    useUiStore.getState().setSelectedProperty(feature);
    useUiStore.getState().setSelectedDetailPlan(feature);

    const state = useUiStore.getState();
    expect(state.selectedDetailPlan).not.toBeNull();
    expect(state.selectedProperty).toBeNull();
    expect(state.sidebarTab).toBe('details');

    useUiStore.getState().clearSelection();
    expect(useUiStore.getState().selectedDetailPlan).toBeNull();
  });

  it('demografimetriken kan bytas', () => {
    expect(useUiStore.getState().demographicsMetric).toBe('population');
    useUiStore.getState().setDemographicsMetric('income');
    expect(useUiStore.getState().demographicsMetric).toBe('income');
  });

  it('toggleIsochroneMinute stannar vid fyra konturer', () => {
    useUiStore.setState({ isochroneMinutes: [5, 10, 15, 20] });
    useUiStore.getState().toggleIsochroneMinute(30);
    expect(useUiStore.getState().isochroneMinutes).toEqual([5, 10, 15, 20]);
    useUiStore.getState().toggleIsochroneMinute(5);
    expect(useUiStore.getState().isochroneMinutes).toEqual([10, 15, 20]);
  });

  it('setIsochroneOrigin avslutar väljarläget', () => {
    useUiStore.getState().setIsochronePicking(true);
    useUiStore
      .getState()
      .setIsochroneOrigin({ longitude: 18, latitude: 59, label: 'Testpunkt' });

    const state = useUiStore.getState();
    expect(state.isochroneOrigin?.label).toBe('Testpunkt');
    expect(state.isochronePicking).toBe(false);
  });

  it('clearIsochrone nollställer startpunkten men behåller inställningarna', () => {
    useUiStore.getState().setIsochroneProfile('driving');
    useUiStore.getState().setIsochroneOrigin({ longitude: 18, latitude: 59, label: 'X' });
    useUiStore.getState().clearIsochrone();

    const state = useUiStore.getState();
    expect(state.isochroneOrigin).toBeNull();
    expect(state.isochronePicking).toBe(false);
    expect(state.isochroneProfile).toBe('driving');
    expect(state.isochroneMinutes).toEqual([10, 20, 30]);
  });
});
