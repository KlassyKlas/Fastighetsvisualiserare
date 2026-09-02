import { beforeEach, describe, expect, it } from 'vitest';
import { readChangesSeenAt } from '@/lib/changesSeen';
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

  it('setOwnerFilter sätter bara ägarfiltret och lämnar övriga filter orörda', () => {
    useUiStore.getState().toggleStatus('planerad');
    useUiStore.getState().setFilters({ municipalities: ['Solna'], year: 2030 });

    useUiStore.getState().setOwnerFilter('Vasakronan AB');
    expect(useUiStore.getState().filters).toMatchObject({
      owner: 'Vasakronan AB',
      statuses: ['planerad'],
      municipalities: ['Solna'],
      year: 2030,
    });

    useUiStore.getState().setOwnerFilter(null);
    expect(useUiStore.getState().filters.owner).toBeNull();
    expect(useUiStore.getState().filters.municipalities).toEqual(['Solna']);
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
    useUiStore.getState().setIsochroneOrigin({ longitude: 18, latitude: 59, label: 'Testpunkt' });

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

  it('ändringsperioden är senaste besöket som standard och kan bytas', () => {
    expect(useUiStore.getState().changesPeriod).toBe('visit');
    useUiStore.getState().setChangesPeriod('sync');
    expect(useUiStore.getState().changesPeriod).toBe('sync');
  });

  it('utan localStorage (node) startar besöksmarkören som null', () => {
    // vitest kör i node: globalThis.localStorage saknas och läsningen får inte kasta
    expect(useUiStore.getState().changesSeenAt).toBeNull();
  });

  it('markChangesSeen sätter markören till nu och skriver localStorage', () => {
    const store = new Map<string, string>();
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => void store.set(key, value),
        removeItem: (key: string) => void store.delete(key),
        clear: () => store.clear(),
      },
    });
    try {
      const before = Date.now();
      useUiStore.getState().markChangesSeen();
      const seenAt = useUiStore.getState().changesSeenAt;
      expect(seenAt).not.toBeNull();
      expect(Date.parse(seenAt!)).toBeGreaterThanOrEqual(before);
      expect(readChangesSeenAt()).toBe(seenAt);
    } finally {
      Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: undefined });
    }
  });

  it('markChangesSeen fungerar även utan localStorage', () => {
    useUiStore.getState().markChangesSeen();
    expect(useUiStore.getState().changesSeenAt).not.toBeNull();
  });
});
