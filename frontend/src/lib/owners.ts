/**
 * Ägarvyn utan backend: speglar aggregeringen i
 * `app/services/properties.py::list_owners` (GROUP BY owner_name) över
 * exempeldatat, så att demo-läget visar samma ägarlista som PostGIS
 * skulle ge. Mot riktig backend används aldrig den här beräkningen.
 *
 * Sortering: kommunerna sorteras i kodpunktsordning på båda sidor
 * (backend använder Pythons sorted(), här Array.prototype.sort utan
 * jämförare) — å/ä/ö hamnar därmed efter z i båda. Ägarnas ORDER BY
 * owner_name görs däremot i databasen med DESS collation; demo-lägets
 * kodpunktsordning är approximativ där (skillnaden syns bara mellan
 * ägare med lika många fastigheter).
 */
import {
  EMPTY_FILTERS,
  type FilterState,
  type OwnerSummary,
  type OwnerSummaryList,
  type PropertyCollection,
  type PropertyFeature,
} from '@/domain';
import { applyPropertyFilters } from '@/lib/filters';
import { formatCurrency, formatNumber } from '@/lib/format';
import { geometryBounds, type Bounds } from '@/lib/geometry';

/** API:ts standardtak för ägarlistan — demo-läget trunkerar likadant. */
export const OWNERS_LIMIT = 50;

/** SQL:s SUM: NULL ignoreras och resultatet är NULL bara när alla saknar värde. */
function sqlSum(values: (number | null | undefined)[]): number | null {
  let sum: number | null = null;
  for (const value of values) {
    if (value == null) continue;
    sum = (sum ?? 0) + value;
  }
  return sum;
}

/** SQL:s MIN över text: NULL ignoreras; strängjämförelse i kodpunktsordning. */
function sqlMin(values: (string | null | undefined)[]): string | null {
  let min: string | null = null;
  for (const value of values) {
    if (value == null) continue;
    if (min == null || value < min) min = value;
  }
  return min;
}

/** Union av rektanglar — motsvarar ST_Extent över gruppens geometrier. */
function unionBounds(features: PropertyFeature[]): Bounds | null {
  let union: Bounds | null = null;
  for (const feature of features) {
    const bounds = geometryBounds(feature.geometry);
    if (!bounds) continue;
    union = union
      ? [
          Math.min(union[0], bounds[0]),
          Math.min(union[1], bounds[1]),
          Math.max(union[2], bounds[2]),
          Math.max(union[3], bounds[3]),
        ]
      : bounds;
  }
  return union;
}

function compareCodePoints(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Summan av taxeringsvärden med SQL-semantik (null när alla saknar värde). */
export function sumAssessedValue(features: PropertyFeature[]): number | null {
  return sqlSum(features.map((f) => f.properties.assessed_value_sek));
}

/**
 * Ägare grupperade på exakt owner_name, störst innehav först. Bara
 * kommunfiltret tillämpas — backendens ägarfråga tar inte värdefiltret,
 * och det speglas här. Fastigheter utan ägare ingår inte
 * (`owner_name IS NOT NULL`).
 */
export function summarizeOwners(
  collection: PropertyCollection,
  filters?: Pick<FilterState, 'municipalities'>,
  limit = OWNERS_LIMIT,
): OwnerSummaryList {
  const filtered = applyPropertyFilters(collection, {
    ...EMPTY_FILTERS,
    municipalities: filters?.municipalities ?? [],
  });

  const groups = new Map<string, PropertyFeature[]>();
  for (const feature of filtered.features) {
    const owner = feature.properties.owner_name;
    if (owner == null) continue;
    const group = groups.get(owner);
    if (group) {
      group.push(feature);
    } else {
      groups.set(owner, [feature]);
    }
  }

  const owners: OwnerSummary[] = [...groups.entries()].map(([ownerName, features]) => ({
    owner_name: ownerName,
    owner_org_number: sqlMin(features.map((f) => f.properties.owner_org_number)),
    property_count: features.length,
    total_area_sqm: sqlSum(features.map((f) => f.properties.area_sqm)),
    total_assessed_value_sek: sumAssessedValue(features),
    // array_agg(DISTINCT …) FILTER (WHERE municipality IS NOT NULL), sorterad
    municipalities: [
      ...new Set(
        features
          .map((f) => f.properties.municipality)
          .filter((municipality): municipality is string => municipality != null),
      ),
    ].sort(),
    extent: unionBounds(features),
  }));

  owners.sort(
    (a, b) => b.property_count - a.property_count || compareCodePoints(a.owner_name, b.owner_name),
  );

  return {
    owners: owners.slice(0, limit),
    numberMatched: owners.length,
    numberReturned: Math.min(owners.length, limit),
  };
}

/**
 * API:ts `extent` är en generisk number[] i kontraktet — kartbryggan vill
 * ha en garanterad fyrtupel. null för saknad, felformad eller icke-finit
 * utbredning, så att focusBounds då gör ingenting.
 */
export function toBounds(extent: number[] | null | undefined): Bounds | null {
  if (!extent || extent.length !== 4 || !extent.every(Number.isFinite)) return null;
  return [extent[0], extent[1], extent[2], extent[3]];
}

/**
 * Summan på ägarkortet. Antalet där räknas ur fastighetslistan, som bär
 * värdefiltret — ägaraggregatet (`list_owners`) gör det inte, så de två
 * får inte blandas: med aktivt värdefilter skulle kortet annars kunna
 * säga "1 fastighet · 630 000 000 kr" (summan för två). Är listan
 * komplett (taket är 2000, så i praktiken alltid) summeras den direkt;
 * aggregatet används bara när listan trunkerats och inget värdefilter är
 * aktivt — då är det den enda fullständiga summan som finns. Trunkerad
 * OCH värdefiltrerad lista ger de laddade fastigheternas summa (en
 * undre gräns); trunkeringsraden under listan visar då att inte alla
 * är laddade.
 */
export function holdingsTotal(
  propertyData: PropertyCollection,
  summary: OwnerSummary | undefined,
  valueFiltered: boolean,
): number | null {
  const { numberReturned, numberMatched } = propertyData;
  const complete =
    numberReturned == null || numberMatched == null || numberReturned >= numberMatched;
  if (!complete && !valueFiltered && summary) {
    return summary.total_assessed_value_sek ?? null;
  }
  return sumAssessedValue(propertyData.features);
}

/** "1 fastighet" / "12 fastigheter". */
export function propertyCountLabel(count: number): string {
  return count === 1 ? '1 fastighet' : `${formatNumber(count)} fastigheter`;
}

/** "2 fastigheter · 630 000 000 kr" — taxeringsvärdet utelämnas när det saknas. */
export function holdingsLabel(count: number, totalValueSek: number | null | undefined): string {
  const parts = [propertyCountLabel(count)];
  if (totalValueSek != null) parts.push(formatCurrency(totalValueSek));
  return parts.join(' · ');
}
