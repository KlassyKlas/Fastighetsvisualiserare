/**
 * Synk mellan storen och adressfältets query-sträng (delbara länkar).
 *
 * Ingen hook: URL:en måste tillämpas synkront före första renderingen,
 * annars körs varje query två gånger (först med standardfiltren, sedan
 * med länkens). Mönstret är main.tsx:s `useUiStore.subscribe`.
 *
 * Skrivningen sker med replaceState — aldrig pushState: bakåtknappen ska
 * inte bläddra genom filterklick, och StrictMode dubbelkör effekter.
 * Hash-delen rörs inte; den ägs av Mapbox (kartvyn).
 *
 * Modulen gör ingenting vid import — storen importeras i node-tester utan
 * window. `win` skickas in så att synken kan testas med en stubb.
 */
import {
  parseUrlState,
  sameSelection,
  selectedUrlSelection,
  serializeUrlState,
  urlStateFromStore,
} from '@/lib/urlState';
import { useUiStore } from '@/store/uiStore';

/** Det lilla av window som synken använder. */
export interface UrlSyncWindow {
  location: { pathname: string; search: string; hash: string };
  history: {
    state: unknown;
    replaceState: (data: unknown, unused: string, url: string) => void;
  };
  addEventListener: (type: 'popstate', listener: () => void) => void;
  removeEventListener: (type: 'popstate', listener: () => void) => void;
}

/** Filterklick kommer i skurar (reglaget, kryssrutor) — en skrivning per vila räcker. */
export const URL_SYNC_DEBOUNCE_MS = 250;

/** Den aktiva synkens omedelbara skrivning — för flushUrlSync. */
let activeFlush: (() => void) | null = null;

/**
 * Anropas en gång från main.tsx före createRoot. Returnerar en
 * avregistreringsfunktion (används inte i appen, men gör modulen testbar).
 */
export function startUrlSync(win: UrlSyncWindow = window): () => void {
  // Senast tillämpade eller skrivna query-sträng — popstate med samma
  // sträng hoppas över (se lyssnaren nedan).
  let lastSearch = win.location.search;

  const apply = () => {
    lastSearch = win.location.search;
    const { state, selection } = parseUrlState(lastSearch);
    const store = useUiStore.getState();
    store.applyUrlState(state);
    // applyUrlState behåller det valda objektet när länken avser samma —
    // då finns inget att hämta (popstate till en adress med samma val ska
    // varken hämta om eller zooma dit igen).
    const alreadySelected = sameSelection(selection, selectedUrlSelection(useUiStore.getState()));
    store.setPendingSelection(alreadySelected ? null : selection);
  };
  apply();

  let timer: ReturnType<typeof setTimeout> | null = null;

  const write = () => {
    if (timer != null) {
      clearTimeout(timer);
      timer = null;
    }
    const search = serializeUrlState(urlStateFromStore(useUiStore.getState()));
    if (search === win.location.search) return;
    win.history.replaceState(
      win.history.state,
      '',
      `${win.location.pathname}${search}${win.location.hash}`,
    );
    lastSearch = search;
  };

  const schedule = () => {
    if (timer != null) clearTimeout(timer);
    timer = setTimeout(write, URL_SYNC_DEBOUNCE_MS);
  };

  // Bakåt/framåt mellan poster med olika query-sträng. Mapbox skriver
  // hashen med replaceState (ingen popstate) — popstate kommer bara från
  // användarens egen hash-navigering (manuell redigering, bakåt/framåt
  // mellan hash-poster), och då är query-strängen oförändrad. Den hoppas
  // över: en tillämpning är inte gratis, den byter ut filter, lager och
  // startpunkt mot nya objekt (startpunkten mot en avrundad kopia med
  // generisk etikett, vilket dessutom hämtar om isokronerna).
  const onPopState = () => {
    if (win.location.search === lastSearch) return;
    apply();
  };

  const unsubscribe = useUiStore.subscribe(schedule);
  win.addEventListener('popstate', onPopState);
  activeFlush = write;

  return () => {
    unsubscribe();
    win.removeEventListener('popstate', onPopState);
    if (timer != null) clearTimeout(timer);
    if (activeFlush === write) activeFlush = null;
  };
}

/**
 * Skriv en väntande URL-ändring omedelbart — inför kopiering av länken,
 * så att det som kopieras är vyn just nu och inte den för 250 ms sedan.
 * Ingen effekt om synken inte startats.
 */
export function flushUrlSync(): void {
  activeFlush?.();
}
