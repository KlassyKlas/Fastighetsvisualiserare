import { describe, expect, it } from 'vitest';
import { FALLBACK_COLOR, ISOCHRONE_PALETTE } from '@/config/map';
import {
  buildIsochroneUrl,
  contourColorExpression,
  geometryAnchor,
  isochroneColorByMinute,
  MAX_ISOCHRONE_CONTOURS,
  normalizeMinutes,
  toggleMinute,
} from './isochrone';

describe('normalizeMinutes', () => {
  it('sorterar, dedupliserar och filtrerar bort ogiltiga värden', () => {
    expect(normalizeMinutes([30, 10, 30, 0, 61, 10.5, 20])).toEqual([10, 20, 30]);
  });

  it('tom lista förblir tom', () => {
    expect(normalizeMinutes([])).toEqual([]);
  });
});

describe('toggleMinute', () => {
  it('lägger till en restid sorterat', () => {
    expect(toggleMinute([10, 30], 20)).toEqual([10, 20, 30]);
  });

  it('tar bort en redan vald restid', () => {
    expect(toggleMinute([10, 20, 30], 20)).toEqual([10, 30]);
  });

  it('lämnar urvalet orört vid fyra valda konturer', () => {
    const full = [5, 10, 15, 20];
    expect(full).toHaveLength(MAX_ISOCHRONE_CONTOURS);
    expect(toggleMinute(full, 30)).toEqual(full);
  });

  it('tillåter borttag även vid fullt urval', () => {
    expect(toggleMinute([5, 10, 15, 20], 5)).toEqual([10, 15, 20]);
  });
});

describe('buildIsochroneUrl', () => {
  const origin = { longitude: 18.07, latitude: 59.33 };

  it('bygger korrekt URL med lng,lat-ordning och stigande konturer', () => {
    const url = new URL(buildIsochroneUrl(origin, 'walking', [30, 10], 'tok'));
    expect(url.origin).toBe('https://api.mapbox.com');
    expect(url.pathname).toBe('/isochrone/v1/mapbox/walking/18.070000,59.330000');
    expect(url.searchParams.get('contours_minutes')).toBe('10,30');
    expect(url.searchParams.get('polygons')).toBe('true');
    expect(url.searchParams.get('access_token')).toBe('tok');
  });

  it('kastar utan giltiga konturer', () => {
    expect(() => buildIsochroneUrl(origin, 'driving', [], 'tok')).toThrow();
    expect(() => buildIsochroneUrl(origin, 'driving', [999], 'tok')).toThrow();
  });

  it('kastar vid fler än fyra konturer', () => {
    expect(() => buildIsochroneUrl(origin, 'cycling', [5, 10, 15, 20, 30], 'tok')).toThrow();
  });
});

describe('isochroneColorByMinute', () => {
  it('ger kortast restid palettens första färg', () => {
    expect(isochroneColorByMinute([30, 10])).toEqual({
      10: ISOCHRONE_PALETTE[0],
      30: ISOCHRONE_PALETTE[1],
    });
  });
});

describe('contourColorExpression', () => {
  it('matchar på numeriska konturvärden med fallback sist', () => {
    expect(contourColorExpression([20, 10])).toEqual([
      'match',
      ['get', 'contour'],
      10,
      ISOCHRONE_PALETTE[0],
      20,
      ISOCHRONE_PALETTE[1],
      FALLBACK_COLOR,
    ]);
  });
});

describe('geometryAnchor', () => {
  it('returnerar punktens koordinater direkt', () => {
    expect(geometryAnchor({ type: 'Point', coordinates: [18, 59] })).toEqual({
      longitude: 18,
      latitude: 59,
    });
  });

  it('returnerar mittpunkten av en polygons omslutande rektangel', () => {
    const anchor = geometryAnchor({
      type: 'Polygon',
      coordinates: [
        [
          [18, 59],
          [20, 59],
          [20, 61],
          [18, 61],
          [18, 59],
        ],
      ],
    });
    expect(anchor).toEqual({ longitude: 19, latitude: 60 });
  });

  it('hanterar GeometryCollection rekursivt', () => {
    const anchor = geometryAnchor({
      type: 'GeometryCollection',
      geometries: [
        { type: 'Point', coordinates: [10, 50] },
        { type: 'Point', coordinates: [12, 52] },
      ],
    });
    expect(anchor).toEqual({ longitude: 11, latitude: 51 });
  });

  it('returnerar null för saknad geometri', () => {
    expect(geometryAnchor(null)).toBeNull();
    expect(geometryAnchor(undefined)).toBeNull();
  });
});
