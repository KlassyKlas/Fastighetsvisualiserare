import { describe, expect, it } from 'vitest';
import { DEFAULT_LAYER_VISIBILITY, YEAR_MAX, YEAR_MIN } from '@/config/map';
import { useUiStore } from '@/store/uiStore';
import {
  DEFAULT_URL_STATE,
  ISOCHRONE_URL_LABEL,
  parseUrlState,
  sameSelection,
  selectedUrlSelection,
  serializeUrlState,
  urlStateFromStore,
  type UrlState,
  type UrlStateSource,
} from './urlState';

/** Alla fält satta till något annat än standard. */
const FULL_STATE: UrlState = {
  filters: {
    statuses: ['planerad', 'pågående'],
    projectTypes: ['väg', 'järnväg'],
    municipalities: ['Stockholm', 'Upplands Väsby'],
    minValue: 1_000_000,
    maxValue: 50_000_000,
    year: 2030,
    owner: 'Vasakronan AB',
  },
  scoreColoring: true,
  layers: { ...DEFAULT_LAYER_VISIBILITY, detailPlans: true, terrain: false },
  demographicsMetric: 'income',
  mapStyle: 'satellite',
  sidebarTab: 'analysis',
  selection: { kind: 'property', id: 12 },
  isochrone: {
    origin: { longitude: 18.07, latitude: 59.33, label: 'Kungsträdgården' },
    profile: 'cycling',
    minutes: [10, 20, 30],
  },
};

describe('serializeUrlState', () => {
  it('standardläget ger en tom sträng', () => {
    expect(serializeUrlState(DEFAULT_URL_STATE)).toBe('');
  });

  it('använder specens parameternamn och läsbara listor', () => {
    const search = serializeUrlState(FULL_STATE);
    expect(search.startsWith('?')).toBe(true);
    for (const expected of [
      'status=planerad,p%C3%A5g%C3%A5ende',
      'typ=v%C3%A4g,j%C3%A4rnv%C3%A4g',
      'kommun=Stockholm,Upplands+V%C3%A4sby',
      'agare=Vasakronan+AB',
      'minvarde=1000000',
      'maxvarde=50000000',
      'ar=2030',
      'poang=1',
      'lager=infrastructure,properties,impactZones,detailPlans,watches,buildings3d',
      'metrik=income',
      'stil=satellite',
      'flik=analysis',
      'fastighet=12',
      'restid=18.07,59.33,cycling,10-20-30',
    ]) {
      expect(search).toContain(expected);
    }
  });

  it('skriver bara parametrar som avviker från standard', () => {
    expect(
      serializeUrlState({
        ...DEFAULT_URL_STATE,
        filters: { ...DEFAULT_URL_STATE.filters, year: 2030 },
      }),
    ).toBe('?ar=2030');
    expect(serializeUrlState({ ...DEFAULT_URL_STATE, mapStyle: 'satellite' })).toBe(
      '?stil=satellite',
    );
  });

  it('detaljfliken är underförstådd vid val och utelämnas utan val', () => {
    expect(
      serializeUrlState({
        ...DEFAULT_URL_STATE,
        sidebarTab: 'details',
        selection: { kind: 'project', id: 3 },
      }),
    ).toBe('?projekt=3');
    expect(serializeUrlState({ ...DEFAULT_URL_STATE, sidebarTab: 'details' })).toBe('');
    // En annan flik än detaljer trots val skrivs ut
    expect(
      serializeUrlState({
        ...DEFAULT_URL_STATE,
        sidebarTab: 'search',
        selection: { kind: 'detailPlan', id: 5 },
      }),
    ).toBe('?flik=search&detaljplan=5');
  });

  it('lager skrivs som fullständig lista över påslagna — tomt när alla är av', () => {
    const allOff = Object.fromEntries(
      Object.keys(DEFAULT_LAYER_VISIBILITY).map((key) => [key, false]),
    ) as unknown as UrlState['layers'];
    expect(serializeUrlState({ ...DEFAULT_URL_STATE, layers: allOff })).toBe('?lager=');
  });

  it('avrundar startpunktens koordinater till sex decimaler', () => {
    const search = serializeUrlState({
      ...DEFAULT_URL_STATE,
      isochrone: {
        origin: { longitude: 18.123456789, latitude: 59.3300000001, label: 'X' },
        profile: 'walking',
        minutes: [30, 10],
      },
    });
    expect(search).toBe('?restid=18.123457,59.33,walking,10-30');
  });

  it('startpunkt utan valda minuter skrivs med tom minutdel och överlever rundresan', () => {
    const state: UrlState = {
      ...DEFAULT_URL_STATE,
      isochrone: {
        origin: { longitude: 18.07, latitude: 59.33, label: 'X' },
        profile: 'walking',
        minutes: [],
      },
    };
    const search = serializeUrlState(state);
    expect(search).toBe('?restid=18.07,59.33,walking,');
    expect(parseUrlState(search).state.isochrone).toEqual({
      origin: { longitude: 18.07, latitude: 59.33, label: ISOCHRONE_URL_LABEL },
      profile: 'walking',
      minutes: [],
    });
  });

  it('"flik utan val" följer standardfliken i defaults åt båda hållen', () => {
    const defaults: UrlState = { ...DEFAULT_URL_STATE, sidebarTab: 'layers' };
    expect(serializeUrlState({ ...defaults, sidebarTab: 'details' }, defaults)).toBe('');
    expect(parseUrlState('?flik=details', defaults).state.sidebarTab).toBe('layers');
    expect(parseUrlState('', defaults).state.sidebarTab).toBe('layers');
    // Sökfliken avviker nu från standard och måste skrivas ut
    expect(serializeUrlState({ ...defaults, sidebarTab: 'search' }, defaults)).toBe('?flik=search');
  });

  it('defaults med satta skalära filter: null skrivs som tomt värde och tolkas tillbaka', () => {
    const defaults: UrlState = {
      ...DEFAULT_URL_STATE,
      filters: { ...DEFAULT_URL_STATE.filters, owner: 'Fabege AB', year: 2030 },
    };
    const cleared: UrlState = {
      ...defaults,
      filters: { ...defaults.filters, owner: null, year: null },
    };

    const search = serializeUrlState(cleared, defaults);
    expect(search).toBe('?agare=&ar=');
    expect(parseUrlState(search, defaults).state).toEqual(cleared);

    // Utan parametrar gäller standarden; lika standard skrivs inte
    expect(parseUrlState('', defaults).state).toEqual(defaults);
    expect(serializeUrlState(defaults, defaults)).toBe('');
    // Ogiltigt värde är fortfarande "ignorera", inte "rensa"
    expect(parseUrlState('?ar=1999', defaults).state.filters.year).toBe(2030);
  });
});

describe('parseUrlState', () => {
  it('tom sträng ger standardläget utan val', () => {
    const { state, selection } = parseUrlState('');
    expect(state).toEqual(DEFAULT_URL_STATE);
    expect(selection).toBeNull();
  });

  it('rundresa: alla fält överlever serialisering och tolkning', () => {
    const { state, selection } = parseUrlState(serializeUrlState(FULL_STATE));
    expect(state).toEqual({
      ...FULL_STATE,
      isochrone: {
        ...FULL_STATE.isochrone,
        // Objektets namn följer inte med länken — startpunkten får en generisk etikett
        origin: { ...FULL_STATE.isochrone!.origin, label: ISOCHRONE_URL_LABEL },
      },
    });
    expect(selection).toEqual({ kind: 'property', id: 12 });
  });

  it('avkodar å/ä/ö och mellanslag i ägare och kommun (båda kodningsformerna)', () => {
    const encoded = parseUrlState('?agare=Vasakronan%20AB&kommun=Upplands%20V%C3%A4sby,Sk%C3%A5re');
    expect(encoded.state.filters.owner).toBe('Vasakronan AB');
    expect(encoded.state.filters.municipalities).toEqual(['Upplands Väsby', 'Skåre']);

    const raw = parseUrlState('?agare=Fabege+AB&kommun=Skåre');
    expect(raw.state.filters.owner).toBe('Fabege AB');
    expect(raw.state.filters.municipalities).toEqual(['Skåre']);
  });

  it('ignorerar okända enumvärden och okända parametrar', () => {
    const { state } = parseUrlState(
      '?status=foo,planerad,planerad&typ=bar&metrik=x&stil=y&flik=z&poang=kanske&okand=1',
    );
    expect(state.filters.statuses).toEqual(['planerad']);
    expect(state.filters.projectTypes).toEqual([]);
    expect(state.demographicsMetric).toBe(DEFAULT_URL_STATE.demographicsMetric);
    expect(state.mapStyle).toBe(DEFAULT_URL_STATE.mapStyle);
    expect(state.sidebarTab).toBe(DEFAULT_URL_STATE.sidebarTab);
    expect(state.scoreColoring).toBe(false);
  });

  it('ignorerar ogiltiga tal och år utanför reglagets gränser', () => {
    const { state, selection } = parseUrlState(
      '?ar=1999&minvarde=abc&maxvarde=-5&fastighet=0&projekt=1.5&detaljplan=-3',
    );
    expect(state.filters.year).toBeNull();
    expect(state.filters.minValue).toBeNull();
    expect(state.filters.maxValue).toBeNull();
    expect(selection).toBeNull();

    expect(parseUrlState(`?ar=${YEAR_MIN}`).state.filters.year).toBe(YEAR_MIN);
    expect(parseUrlState(`?ar=${YEAR_MAX}`).state.filters.year).toBe(YEAR_MAX);
    expect(parseUrlState(`?ar=${YEAR_MAX + 1}`).state.filters.year).toBeNull();
    expect(parseUrlState('?minvarde=0&maxvarde=250000').state.filters).toMatchObject({
      minValue: 0,
      maxValue: 250_000,
    });
  });

  it('högst ett val: fastighet vinner över projekt som vinner över detaljplan', () => {
    expect(parseUrlState('?detaljplan=5&projekt=3&fastighet=12').selection).toEqual({
      kind: 'property',
      id: 12,
    });
    expect(parseUrlState('?detaljplan=5&projekt=3').selection).toEqual({
      kind: 'project',
      id: 3,
    });
    expect(parseUrlState('?detaljplan=5').selection).toEqual({ kind: 'detailPlan', id: 5 });
    // Ett ogiltigt id diskvalificerar bara sig självt
    expect(parseUrlState('?fastighet=abc&projekt=3').selection).toEqual({
      kind: 'project',
      id: 3,
    });
  });

  it('fliken details utan val blir sök; ett val utan flik öppnar detaljer', () => {
    expect(parseUrlState('?flik=details').state.sidebarTab).toBe('search');
    expect(parseUrlState('?flik=details&projekt=3').state.sidebarTab).toBe('details');
    expect(parseUrlState('?projekt=3').state.sidebarTab).toBe('details');
    expect(parseUrlState('?projekt=3&flik=watches').state.sidebarTab).toBe('watches');
  });

  it('lager: listan är komplett — onämnda lager är av, okända nycklar ignoreras', () => {
    const { state } = parseUrlState('?lager=properties,terrain,foo');
    expect(state.layers).toEqual({
      ...Object.fromEntries(Object.keys(DEFAULT_LAYER_VISIBILITY).map((key) => [key, false])),
      properties: true,
      terrain: true,
    });
    expect(Object.values(parseUrlState('?lager=').state.layers).every((on) => !on)).toBe(true);
    expect(parseUrlState('?annat=1').state.layers).toEqual(DEFAULT_LAYER_VISIBILITY);
  });

  it('restid: minuter normaliseras och begränsas till fyra, etiketten är generisk', () => {
    const { state } = parseUrlState('?restid=18.07,59.33,walking,30-10-30-0-61-45-20-15');
    expect(state.isochrone).toEqual({
      origin: { longitude: 18.07, latitude: 59.33, label: ISOCHRONE_URL_LABEL },
      profile: 'walking',
      minutes: [10, 15, 20, 30],
    });
  });

  it('restid: hela parametern ignoreras när någon del är ogiltig', () => {
    for (const restid of [
      '18.07,59.33,walking', // för få delar
      '181,59.33,walking,10', // longitud utanför intervallet
      '18.07,91,walking,10', // latitud utanför intervallet
      '18.07,59.33,flying,10', // okänd profil
      '18.07,59.33,walking,abc', // inga giltiga minuter
      '18.07,59.33,walking,0-61', // bara ogiltiga minuter
      ',59.33,walking,10', // tom longitud
    ]) {
      expect(parseUrlState(`?restid=${restid}`).state.isochrone, restid).toBeNull();
    }
  });

  it('restid: tom minutdel är giltig — startpunkt utan valda restider', () => {
    expect(parseUrlState('?restid=18.07,59.33,cycling,').state.isochrone).toEqual({
      origin: { longitude: 18.07, latitude: 59.33, label: ISOCHRONE_URL_LABEL },
      profile: 'cycling',
      minutes: [],
    });
  });

  it('kastar aldrig på trasig indata', () => {
    expect(() => parseUrlState('?%E0%A4%A&status=%&ar=%ZZ')).not.toThrow();
    expect(() => parseUrlState('garbage&&==?')).not.toThrow();
    expect(parseUrlState('garbage&&==?').state).toEqual(DEFAULT_URL_STATE);
  });
});

describe('urlStateFromStore', () => {
  const feature = (id: unknown) =>
    ({ properties: { id } }) as unknown as { properties: { id: number } };

  it('storens startläge är URL-standardläget', () => {
    const initial = urlStateFromStore(useUiStore.getInitialState());
    expect(initial).toEqual(DEFAULT_URL_STATE);
    expect(serializeUrlState(initial)).toBe('');
  });

  it('tar valet från det valda objektet, annars från det som laddas', () => {
    const base = useUiStore.getInitialState();
    expect(urlStateFromStore({ ...base, selectedProperty: feature(7) }).selection).toEqual({
      kind: 'property',
      id: 7,
    });
    expect(urlStateFromStore({ ...base, selectedDetailPlan: feature('9') }).selection).toEqual({
      kind: 'detailPlan',
      id: 9,
    });
    expect(
      urlStateFromStore({ ...base, pendingSelection: { kind: 'project', id: 3 } }).selection,
    ).toEqual({ kind: 'project', id: 3 });
    // Det valda vinner över det väntande
    expect(
      urlStateFromStore({
        ...base,
        selectedProject: feature(4),
        pendingSelection: { kind: 'property', id: 12 },
      }).selection,
    ).toEqual({ kind: 'project', id: 4 });
    // Ett obrukbart id ger inget val
    expect(urlStateFromStore({ ...base, selectedProperty: feature('x') }).selection).toBeNull();
  });

  it('selectedUrlSelection ser bara det valda — inte det som laddas', () => {
    const base = useUiStore.getInitialState();
    expect(selectedUrlSelection(base)).toBeNull();
    const loading: UrlStateSource = { ...base, pendingSelection: { kind: 'project', id: 3 } };
    expect(selectedUrlSelection(loading)).toBeNull();
    expect(selectedUrlSelection({ ...base, selectedProject: feature(4) })).toEqual({
      kind: 'project',
      id: 4,
    });
  });

  it('sameSelection jämför sort och id, och null bara med null', () => {
    expect(sameSelection(null, null)).toBe(true);
    expect(sameSelection({ kind: 'property', id: 1 }, null)).toBe(false);
    expect(sameSelection(null, { kind: 'property', id: 1 })).toBe(false);
    expect(sameSelection({ kind: 'property', id: 1 }, { kind: 'property', id: 1 })).toBe(true);
    expect(sameSelection({ kind: 'property', id: 1 }, { kind: 'project', id: 1 })).toBe(false);
    expect(sameSelection({ kind: 'property', id: 1 }, { kind: 'property', id: 2 })).toBe(false);
  });

  it('restiden följer med bara när en startpunkt finns', () => {
    const base = useUiStore.getInitialState();
    expect(urlStateFromStore(base).isochrone).toBeNull();
    const origin = { longitude: 18, latitude: 59, label: 'Punkt' };
    expect(
      urlStateFromStore({
        ...base,
        isochroneOrigin: origin,
        isochroneProfile: 'driving',
        isochroneMinutes: [15],
      }).isochrone,
    ).toEqual({ origin, profile: 'driving', minutes: [15] });
  });
});
