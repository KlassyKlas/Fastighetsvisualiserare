import { describe, expect, it } from 'vitest';
import { sampleProperties } from '@/data/sampleData';
import type { PropertyCollection, PropertyFeature } from '@/domain';
import { formatCurrency } from './format';
import { geometryBounds } from './geometry';
import {
  holdingsLabel,
  holdingsTotal,
  propertyCountLabel,
  sumAssessedValue,
  summarizeOwners,
  toBounds,
} from './owners';

/** Minimal fastighet för syntetiska fall — bara fälten aggregeringen läser. */
function property(
  id: number,
  overrides: Partial<PropertyFeature['properties']> & { geometry?: PropertyFeature['geometry'] },
): PropertyFeature {
  const { geometry = null, ...props } = overrides;
  return {
    type: 'Feature',
    geometry,
    properties: { id, designation: `Test ${id}`, metadata_json: {}, ...props },
  } as PropertyFeature;
}

function collection(features: PropertyFeature[]): PropertyCollection {
  return {
    type: 'FeatureCollection',
    features,
    numberMatched: features.length,
    numberReturned: features.length,
  };
}

describe('summarizeOwners', () => {
  it('grupperar exempeldatat på exakt ägarnamn med innehavets nyckeltal', () => {
    const result = summarizeOwners(sampleProperties);
    const unibail = result.owners?.find((o) => o.owner_name === 'Unibail-Rodamco-Westfield');

    expect(unibail).toBeDefined();
    expect(unibail?.property_count).toBe(2);
    expect(unibail?.owner_org_number).toBe('556079-1415');
    expect(unibail?.total_area_sqm).toBe(27_000);
    expect(unibail?.total_assessed_value_sek).toBe(630_000_000);
    expect(unibail?.municipalities).toEqual(['Solna', 'Täby']);

    // Utbredningen är unionen av båda fastigheternas rektanglar (ST_Extent)
    const bounds = sampleProperties.features
      .filter((f) => f.properties.owner_name === 'Unibail-Rodamco-Westfield')
      .map((f) => geometryBounds(f.geometry)!);
    expect(unibail?.extent).toEqual([
      Math.min(bounds[0][0], bounds[1][0]),
      Math.min(bounds[0][1], bounds[1][1]),
      Math.max(bounds[0][2], bounds[1][2]),
      Math.max(bounds[0][3], bounds[1][3]),
    ]);
  });

  it('sorterar på antal fallande, därefter ägarnamn', () => {
    const result = summarizeOwners(sampleProperties);
    const owners = result.owners ?? [];

    expect(owners[0].owner_name).toBe('Unibail-Rodamco-Westfield');
    const rest = owners.slice(1);
    expect(rest.every((o) => o.property_count === 1)).toBe(true);
    expect(rest.map((o) => o.owner_name)).toEqual([...rest.map((o) => o.owner_name)].sort());
    expect(result.numberMatched).toBe(9);
    expect(result.numberReturned).toBe(9);
  });

  it('respekterar limit men räknar alla matchande ägare', () => {
    const result = summarizeOwners(sampleProperties, undefined, 3);
    expect(result.owners).toHaveLength(3);
    expect(result.numberReturned).toBe(3);
    expect(result.numberMatched).toBe(9);
  });

  it('kommunfiltret begränsar innehavet — samma filter som fastighetslistan', () => {
    const result = summarizeOwners(sampleProperties, { municipalities: ['Solna'] });
    expect(result.owners).toHaveLength(1);
    expect(result.owners?.[0]).toMatchObject({
      owner_name: 'Unibail-Rodamco-Westfield',
      property_count: 1,
      municipalities: ['Solna'],
      total_assessed_value_sek: 350_000_000,
    });
  });

  it('utesluter fastigheter utan ägare och summerar med SQL-semantik', () => {
    const result = summarizeOwners(
      collection([
        property(1, { owner_name: 'A', area_sqm: 100, assessed_value_sek: null }),
        property(2, { owner_name: 'A', area_sqm: null, assessed_value_sek: null }),
        property(3, { owner_name: null, area_sqm: 999, assessed_value_sek: 999 }),
      ]),
    );

    expect(result.numberMatched).toBe(1);
    expect(result.owners?.[0]).toMatchObject({
      owner_name: 'A',
      property_count: 2,
      // SUM ignorerar NULL — och är NULL bara när alla saknar värde
      total_area_sqm: 100,
      total_assessed_value_sek: null,
      owner_org_number: null,
      municipalities: [],
      extent: null,
    });
  });

  it('utbredningen hoppar över fastigheter utan geometri (ST_Extent ignorerar NULL)', () => {
    const polygon: PropertyFeature['geometry'] = {
      type: 'Polygon',
      coordinates: [
        [
          [18.0, 59.3],
          [18.1, 59.3],
          [18.1, 59.4],
          [18.0, 59.4],
          [18.0, 59.3],
        ],
      ],
    };
    const result = summarizeOwners(
      collection([
        property(1, { owner_name: 'A', geometry: polygon }),
        property(2, { owner_name: 'A' }), // geometri saknas (null)
      ]),
    );

    expect(result.owners?.[0].property_count).toBe(2);
    expect(result.owners?.[0].extent).toEqual(geometryBounds(polygon));
    expect(result.owners?.[0].extent).toEqual([18.0, 59.3, 18.1, 59.4]);
  });

  it('organisationsnumret är gruppens minsta, NULL ignoreras', () => {
    const result = summarizeOwners(
      collection([
        property(1, { owner_name: 'A', owner_org_number: null }),
        property(2, { owner_name: 'A', owner_org_number: '556200-0000' }),
        property(3, { owner_name: 'A', owner_org_number: '556100-0000' }),
      ]),
    );
    expect(result.owners?.[0].owner_org_number).toBe('556100-0000');
  });

  it('kommuner sorteras i kodpunktsordning (å/ä/ö efter z, som Pythons sorted)', () => {
    const result = summarizeOwners(
      collection([
        property(1, { owner_name: 'A', municipality: 'Örebro' }),
        property(2, { owner_name: 'A', municipality: 'Ängelholm' }),
        property(3, { owner_name: 'A', municipality: 'Ystad' }),
        property(4, { owner_name: 'A', municipality: 'Ystad' }),
        property(5, { owner_name: 'A', municipality: null }),
      ]),
    );
    expect(result.owners?.[0].municipalities).toEqual(['Ystad', 'Ängelholm', 'Örebro']);
  });

  it('ägarnamn matchas exakt — "Vasakronan AB" och "Vasakronan" är olika ägare', () => {
    const result = summarizeOwners(
      collection([
        property(1, { owner_name: 'Vasakronan AB' }),
        property(2, { owner_name: 'Vasakronan' }),
        property(3, { owner_name: 'vasakronan ab' }),
      ]),
    );
    expect(result.numberMatched).toBe(3);
  });
});

describe('sumAssessedValue', () => {
  it('är null när alla saknar värde och annars summan av de som finns', () => {
    expect(sumAssessedValue([])).toBeNull();
    expect(sumAssessedValue([property(1, { assessed_value_sek: null })])).toBeNull();
    expect(
      sumAssessedValue([
        property(1, { assessed_value_sek: 5 }),
        property(2, { assessed_value_sek: null }),
        property(3, { assessed_value_sek: 7 }),
      ]),
    ).toBe(12);
  });
});

describe('holdingsTotal', () => {
  // Ägaraggregatet räknas utan värdefilter: två fastigheter, 630 totalt
  const summary = summarizeOwners(
    collection([
      property(1, { owner_name: 'A', assessed_value_sek: 350 }),
      property(2, { owner_name: 'A', assessed_value_sek: 280 }),
    ]),
  ).owners?.[0];
  // Värdefiltrerad (eller trunkerad) lista: bara den ena är laddad
  const oneLoaded = collection([property(1, { owner_name: 'A', assessed_value_sek: 350 })]);

  it('summerar den laddade listan när den är komplett — samma mängd som antalet', () => {
    expect(summary?.total_assessed_value_sek).toBe(630);
    expect(holdingsTotal(oneLoaded, summary, false)).toBe(350);
    expect(holdingsTotal(oneLoaded, summary, true)).toBe(350);
  });

  it('använder aggregatet bara när listan trunkerats utan värdefilter', () => {
    const truncated = { ...oneLoaded, numberMatched: 2 };
    expect(holdingsTotal(truncated, summary, false)).toBe(630);
    // Med värdefilter är aggregatet fel mängd — den laddade summan används
    expect(holdingsTotal(truncated, summary, true)).toBe(350);
    expect(holdingsTotal(truncated, undefined, false)).toBe(350);
  });

  it('är null när ingen laddad fastighet har taxeringsvärde', () => {
    const noValues = collection([property(1, { owner_name: 'A', assessed_value_sek: null })]);
    expect(holdingsTotal(noValues, undefined, false)).toBeNull();
  });
});

describe('toBounds', () => {
  it('ger fyrtupel för en giltig utbredning', () => {
    expect(toBounds([17.8, 59.2, 18.2, 59.5])).toEqual([17.8, 59.2, 18.2, 59.5]);
  });

  it('avvisar saknad, felformad eller icke-finit utbredning', () => {
    expect(toBounds(null)).toBeNull();
    expect(toBounds(undefined)).toBeNull();
    expect(toBounds([])).toBeNull();
    expect(toBounds([1, 2, 3])).toBeNull();
    expect(toBounds([1, 2, 3, 4, 5])).toBeNull();
    expect(toBounds([1, 2, 3, Number.NaN])).toBeNull();
    expect(toBounds([1, 2, 3, Number.POSITIVE_INFINITY])).toBeNull();
  });
});

describe('etiketter', () => {
  it('böjer fastighet efter antal', () => {
    expect(propertyCountLabel(1)).toBe('1 fastighet');
    expect(propertyCountLabel(2)).toBe('2 fastigheter');
    expect(propertyCountLabel(0)).toBe('0 fastigheter');
  });

  it('utelämnar taxeringsvärdet när det saknas', () => {
    // Intl:s tusentalsavgränsare (hårt mellanslag) — jämför mot samma formatterare
    expect(holdingsLabel(2, 630_000_000)).toBe(`2 fastigheter · ${formatCurrency(630_000_000)}`);
    expect(holdingsLabel(1, null)).toBe('1 fastighet');
    expect(holdingsLabel(3, undefined)).toBe('3 fastigheter');
  });
});
