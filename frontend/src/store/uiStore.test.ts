import { beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_LAYER_VISIBILITY } from '@/config/map';
import { EMPTY_FILTERS } from '@/domain';
import { readChangesSeenAt } from '@/lib/changesSeen';
import { ISOCHRONE_URL_LABEL, parseUrlState } from '@/lib/urlState';
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

  it('applyUrlState ersätter filter och lager helt — det länken inte nämner blir standard', () => {
    useUiStore.getState().toggleStatus('planerad');
    useUiStore.getState().setOwnerFilter('Vasakronan AB');
    useUiStore.getState().toggleLayer('terrain');
    useUiStore.getState().setScoreColoring(true);

    useUiStore.getState().applyUrlState(parseUrlState('?ar=2030&flik=watches').state);

    const state = useUiStore.getState();
    expect(state.filters).toEqual({ ...EMPTY_FILTERS, year: 2030 });
    expect(state.filters.owner).toBeNull();
    expect(state.layers).toEqual(DEFAULT_LAYER_VISIBILITY);
    expect(state.scoreColoring).toBe(false);
    expect(state.sidebarTab).toBe('watches');
  });

  it('applyUrlState sätter restidsanalysen ur länken men rör inte väljarläget', () => {
    useUiStore.getState().setIsochronePicking(true);
    useUiStore.getState().applyUrlState(parseUrlState('?restid=18.07,59.33,driving,15-45').state);

    const state = useUiStore.getState();
    expect(state.isochroneOrigin).toMatchObject({ longitude: 18.07, latitude: 59.33 });
    expect(state.isochroneProfile).toBe('driving');
    expect(state.isochroneMinutes).toEqual([15, 45]);
    // Transient state utanför länken lämnas som det är
    expect(state.isochronePicking).toBe(true);

    // Utan restid i länken stängs analysen men profil och minuter behålls (som clearIsochrone)
    useUiStore.getState().applyUrlState(parseUrlState('').state);
    expect(useUiStore.getState().isochroneOrigin).toBeNull();
    expect(useUiStore.getState().isochroneProfile).toBe('driving');
    expect(useUiStore.getState().isochroneMinutes).toEqual([15, 45]);
  });

  it('applyUrlState behåller startpunkten och dess etikett när länken avser samma punkt', () => {
    const origin = { longitude: 18.0712345678, latitude: 59.33, label: 'Kungsträdgården' };
    useUiStore.getState().setIsochroneOrigin(origin);

    // Länkens sex decimaler är samma punkt — objektet (och namnet) behålls,
    // profil och minuter följer länken
    useUiStore.getState().applyUrlState(parseUrlState('?restid=18.071235,59.33,cycling,10').state);
    let state = useUiStore.getState();
    expect(state.isochroneOrigin).toBe(origin);
    expect(state.isochroneProfile).toBe('cycling');
    expect(state.isochroneMinutes).toEqual([10]);

    // En annan punkt ersätter — med länkens generiska etikett
    useUiStore.getState().applyUrlState(parseUrlState('?restid=18.08,59.33,cycling,10').state);
    state = useUiStore.getState();
    expect(state.isochroneOrigin).toEqual({
      longitude: 18.08,
      latitude: 59.33,
      label: ISOCHRONE_URL_LABEL,
    });
  });

  it('applyUrlState släpper valet när länken saknar det eller avser ett annat objekt', () => {
    const property = {
      type: 'Feature',
      geometry: null,
      properties: { id: 12, designation: 'Test 1:1' },
    } as never;

    // Samma objekt i länken: valet och detaljfliken behålls
    useUiStore.getState().setSelectedProperty(property);
    useUiStore.getState().applyUrlState(parseUrlState('?fastighet=12').state);
    expect(useUiStore.getState().selectedProperty).toBe(property);
    expect(useUiStore.getState().sidebarTab).toBe('details');

    // Ett annat objekt: det valda släpps (UrlSelectionLoader hämtar länkens)
    useUiStore.getState().applyUrlState(parseUrlState('?projekt=3').state);
    expect(useUiStore.getState().selectedProperty).toBeNull();
    expect(useUiStore.getState().sidebarTab).toBe('details');

    // Inget val i länken: allt valt släpps och fliken följer länken
    useUiStore.getState().setSelectedProperty(property);
    useUiStore.getState().applyUrlState(parseUrlState('').state);
    const state = useUiStore.getState();
    expect(state.selectedProperty).toBeNull();
    expect(state.selectedProject).toBeNull();
    expect(state.selectedDetailPlan).toBeNull();
    expect(state.sidebarTab).toBe('search');
  });

  it('pendingSelection sätts och rensas', () => {
    expect(useUiStore.getState().pendingSelection).toBeNull();
    useUiStore.getState().setPendingSelection({ kind: 'project', id: 3 });
    expect(useUiStore.getState().pendingSelection).toEqual({ kind: 'project', id: 3 });
    useUiStore.getState().setPendingSelection(null);
    expect(useUiStore.getState().pendingSelection).toBeNull();
  });

  it('ett val användaren gör släpper det som väntar ur länken', () => {
    const property = {
      type: 'Feature',
      geometry: null,
      properties: { id: 12, designation: 'Test 1:1' },
    } as never;

    useUiStore.getState().setPendingSelection({ kind: 'project', id: 3 });
    useUiStore.getState().setSelectedProperty(property);
    expect(useUiStore.getState().pendingSelection).toBeNull();

    // Att avmarkera släpper inget — länkens objekt får fortfarande visas
    useUiStore.getState().setPendingSelection({ kind: 'project', id: 3 });
    useUiStore.getState().setSelectedProperty(null);
    expect(useUiStore.getState().pendingSelection).toEqual({ kind: 'project', id: 3 });
  });
});
