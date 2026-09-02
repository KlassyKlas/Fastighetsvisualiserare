import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PropertyFeature } from '@/domain';
import { useUiStore } from '@/store/uiStore';
import { flushUrlSync, startUrlSync, URL_SYNC_DEBOUNCE_MS, type UrlSyncWindow } from './urlSync';

const initialState = useUiStore.getState();

interface StubWindow extends UrlSyncWindow {
  /** Varje replaceState-anrop: history.state-argumentet och adressen. */
  replaceCalls: { data: unknown; url: string }[];
  firePopState: () => void;
}

function splitUrl(url: string): { pathname: string; search: string; hash: string } {
  const hashIndex = url.indexOf('#');
  const hash = hashIndex >= 0 ? url.slice(hashIndex) : '';
  const rest = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
  const queryIndex = rest.indexOf('?');
  return {
    pathname: queryIndex >= 0 ? rest.slice(0, queryIndex) : rest,
    search: queryIndex >= 0 ? rest.slice(queryIndex) : '',
    hash,
  };
}

/** window-stubb för node: replaceState byter adress utan att avfyra något, som i webbläsaren. */
function stubWindow(url: string): StubWindow {
  const listeners = new Set<() => void>();
  const win: StubWindow = {
    location: splitUrl(url),
    history: {
      state: { mapbox: 'bevaras' },
      replaceState(data, _unused, next) {
        win.location = splitUrl(next);
        win.replaceCalls.push({ data, url: next });
      },
    },
    addEventListener: (_type, listener) => void listeners.add(listener),
    removeEventListener: (_type, listener) => void listeners.delete(listener),
    replaceCalls: [],
    firePopState: () => listeners.forEach((listener) => listener()),
  };
  return win;
}

/** En vald fastighet med det id som länken bär — resten är ointressant för synken. */
function property(id: number): PropertyFeature {
  return {
    type: 'Feature',
    geometry: null,
    properties: { id, designation: `Test ${id}:1` },
  } as unknown as PropertyFeature;
}

const stops: (() => void)[] = [];

function start(win: UrlSyncWindow): () => void {
  const stop = startUrlSync(win);
  stops.push(stop);
  return stop;
}

beforeEach(() => {
  vi.useFakeTimers();
  useUiStore.setState(initialState, true);
});

afterEach(() => {
  stops.splice(0).forEach((stop) => stop());
  vi.useRealTimers();
});

describe('startUrlSync', () => {
  it('tillämpar adressen synkront vid start utan att skriva om den', () => {
    // Parametrarna i annan ordning än serialiseringens — en omskrivning skulle synas
    const win = stubWindow('/?fastighet=12&flik=analysis&stil=satellite&ar=2030');
    start(win);

    const state = useUiStore.getState();
    expect(state.filters.year).toBe(2030);
    expect(state.pendingSelection).toEqual({ kind: 'property', id: 12 });
    expect(state.sidebarTab).toBe('analysis');
    expect(state.mapStyle).toBe('satellite');

    // Tillämpningen sker före prenumerationen och utlöser ingen skrivning
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    expect(win.replaceCalls).toEqual([]);
  });

  it('skriver storeändringar debouncat med replaceState och bevarar hashen', () => {
    const win = stubWindow('/#karta=11/59.33/18.07/-17/45');
    start(win);

    useUiStore.getState().toggleStatus('planerad');
    expect(win.replaceCalls).toEqual([]);

    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS - 1);
    expect(win.replaceCalls).toEqual([]);

    vi.advanceTimersByTime(1);
    expect(win.replaceCalls).toEqual([
      { data: { mapbox: 'bevaras' }, url: '/?status=planerad#karta=11/59.33/18.07/-17/45' },
    ]);
  });

  it('flera ändringar i följd ger en enda skrivning', () => {
    const win = stubWindow('/');
    start(win);

    useUiStore.getState().toggleStatus('planerad');
    useUiStore.getState().toggleProjectType('väg');
    useUiStore.getState().setFilters({ year: 2030 });
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);

    expect(win.replaceCalls).toHaveLength(1);
    expect(win.replaceCalls[0].url).toBe('/?status=planerad&typ=v%C3%A4g&ar=2030');
  });

  it('skriver inte när adressen redan stämmer', () => {
    const win = stubWindow('/?ar=2030');
    start(win);

    // Samma värde som redan står i adressen — storen ändras, adressen inte
    useUiStore.getState().setFilters({ year: 2030 });
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);

    expect(win.replaceCalls).toEqual([]);
  });

  it('behåller valet i adressen medan objektet hämtas', () => {
    const win = stubWindow('/?fastighet=12');
    start(win);

    // Något orelaterat ändras innan UrlSelectionLoader hunnit välja objektet
    useUiStore.getState().setDemoMode(true);
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);

    expect(win.replaceCalls).toEqual([]);
    expect(win.location.search).toBe('?fastighet=12');
  });

  it('popstate tillämpar den nya adressen', () => {
    const win = stubWindow('/');
    start(win);

    win.location = { ...win.location, search: '?stil=satellite&projekt=3' };
    win.firePopState();

    const state = useUiStore.getState();
    expect(state.mapStyle).toBe('satellite');
    expect(state.pendingSelection).toEqual({ kind: 'project', id: 3 });

    // Tillämpningen ändrar storen, men adressen stämmer redan — ingen skrivning
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    expect(win.replaceCalls).toEqual([]);
  });

  it('popstate med oförändrad query-sträng rör inte storen', () => {
    const win = stubWindow('/?ar=2030#karta=11/59.33/18.07/0/0');
    start(win);
    const origin = { longitude: 18.0712345678, latitude: 59.33, label: 'Kungsträdgården' };
    useUiStore.getState().setIsochroneOrigin(origin);
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    expect(win.location.search).toBe('?ar=2030&restid=18.071235,59.33,walking,10-20-30');
    const { filters, layers } = useUiStore.getState();

    // Användarens hash-navigering (redigerad hash, bakåt mellan hash-poster):
    // bara hashen skiljer — startpunkten får varken bytas ut mot länkens
    // avrundade kopia eller tappa sin etikett
    win.location = { ...win.location, hash: '#karta=12/59.34/18.08/0/0' };
    win.firePopState();

    const state = useUiStore.getState();
    expect(state.isochroneOrigin).toBe(origin);
    expect(state.filters).toBe(filters);
    expect(state.layers).toBe(layers);
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    expect(win.replaceCalls).toHaveLength(1);
  });

  it('popstate till en adress utan val släpper valet', () => {
    const win = stubWindow('/?fastighet=12');
    start(win);

    // UrlSelectionLoader har hämtat och valt objektet
    useUiStore.getState().setSelectedProperty(property(12));
    useUiStore.getState().setPendingSelection(null);
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    expect(win.replaceCalls).toEqual([]);

    // Bakåt till en post utan val — adressen är sanning, inte det valda
    win.location = { ...win.location, search: '' };
    win.firePopState();

    const state = useUiStore.getState();
    expect(state.selectedProperty).toBeNull();
    expect(state.pendingSelection).toBeNull();
    expect(state.sidebarTab).toBe('search');

    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    expect(win.replaceCalls).toEqual([]);
    expect(win.location.search).toBe('');
  });

  it('popstate till en adress med samma val hämtar inte om det', () => {
    const win = stubWindow('/?fastighet=12');
    start(win);
    const selected = property(12);
    useUiStore.getState().setSelectedProperty(selected);
    useUiStore.getState().setPendingSelection(null);

    // T.ex. en redigerad karthash: samma val, annan stil
    win.location = { ...win.location, search: '?stil=satellite&fastighet=12' };
    win.firePopState();

    const state = useUiStore.getState();
    expect(state.selectedProperty).toBe(selected);
    expect(state.pendingSelection).toBeNull();
    expect(state.mapStyle).toBe('satellite');
    expect(state.sidebarTab).toBe('details');

    // Ett annat val i adressen ersätter det valda via pendingSelection
    win.location = { ...win.location, search: '?projekt=3' };
    win.firePopState();
    expect(useUiStore.getState().selectedProperty).toBeNull();
    expect(useUiStore.getState().pendingSelection).toEqual({ kind: 'project', id: 3 });
  });

  it('flushUrlSync skriver den väntande ändringen omedelbart', () => {
    const win = stubWindow('/');
    start(win);

    useUiStore.getState().setScoreColoring(true);
    flushUrlSync();
    expect(win.replaceCalls.map((call) => call.url)).toEqual(['/?poang=1']);

    // Den avbrutna timern får inte skriva en gång till
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    expect(win.replaceCalls).toHaveLength(1);
  });

  it('avregistreringen stoppar både skrivning, popstate och flush', () => {
    const win = stubWindow('/');
    const stop = start(win);
    stop();

    useUiStore.getState().toggleStatus('planerad');
    vi.advanceTimersByTime(URL_SYNC_DEBOUNCE_MS);
    flushUrlSync();
    expect(win.replaceCalls).toEqual([]);

    win.location = { ...win.location, search: '?stil=satellite' };
    win.firePopState();
    expect(useUiStore.getState().mapStyle).toBe('dark');
  });
});
