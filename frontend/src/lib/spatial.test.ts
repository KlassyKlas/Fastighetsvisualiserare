import { describe, expect, it } from 'vitest';
import type { Geometry, Position } from 'geojson';
import {
  geometryIntersectsMultiPolygon,
  pointInPolygon,
  pointInRing,
  segmentsIntersect,
} from './spatial';

/** Kvadrat 0,0 → 10,10 */
const SQUARE: Position[][] = [
  [
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10],
    [0, 0],
  ],
];

/** Kvadraten med ett hål 4,4 → 6,6 */
const SQUARE_WITH_HOLE: Position[][] = [
  SQUARE[0],
  [
    [4, 4],
    [6, 4],
    [6, 6],
    [4, 6],
    [4, 4],
  ],
];

const AREA = [SQUARE];

describe('pointInRing', () => {
  it('punkt innanför', () => {
    expect(pointInRing([5, 5], SQUARE[0])).toBe(true);
  });
  it('punkt utanför', () => {
    expect(pointInRing([15, 5], SQUARE[0])).toBe(false);
  });
});

describe('pointInPolygon', () => {
  it('punkt i hålet räknas som utanför', () => {
    expect(pointInPolygon([5, 5], SQUARE_WITH_HOLE)).toBe(false);
  });
  it('punkt mellan hål och ytterkant är innanför', () => {
    expect(pointInPolygon([2, 2], SQUARE_WITH_HOLE)).toBe(true);
  });
});

describe('segmentsIntersect', () => {
  it('korsande sträckor', () => {
    expect(segmentsIntersect([0, 0], [10, 10], [0, 10], [10, 0])).toBe(true);
  });
  it('parallella sträckor', () => {
    expect(segmentsIntersect([0, 0], [10, 0], [0, 1], [10, 1])).toBe(false);
  });
  it('kolinjära överlappande sträckor', () => {
    expect(segmentsIntersect([0, 0], [5, 0], [3, 0], [8, 0])).toBe(true);
  });
});

describe('geometryIntersectsMultiPolygon', () => {
  it('punkt i området', () => {
    const point: Geometry = { type: 'Point', coordinates: [5, 5] };
    expect(geometryIntersectsMultiPolygon(point, AREA)).toBe(true);
  });

  it('punkt utanför området', () => {
    const point: Geometry = { type: 'Point', coordinates: [20, 20] };
    expect(geometryIntersectsMultiPolygon(point, AREA)).toBe(false);
  });

  it('linje som korsar området utan hörn innanför', () => {
    const line: Geometry = {
      type: 'LineString',
      coordinates: [
        [-5, 5],
        [15, 5],
      ],
    };
    expect(geometryIntersectsMultiPolygon(line, AREA)).toBe(true);
  });

  it('linje helt utanför', () => {
    const line: Geometry = {
      type: 'LineString',
      coordinates: [
        [20, 20],
        [30, 30],
      ],
    };
    expect(geometryIntersectsMultiPolygon(line, AREA)).toBe(false);
  });

  it('polygon som omsluter hela området', () => {
    const big: Geometry = {
      type: 'Polygon',
      coordinates: [
        [
          [-10, -10],
          [20, -10],
          [20, 20],
          [-10, 20],
          [-10, -10],
        ],
      ],
    };
    expect(geometryIntersectsMultiPolygon(big, AREA)).toBe(true);
  });

  it('multipolygon där ett delskifte träffar', () => {
    const mp: Geometry = {
      type: 'MultiPolygon',
      coordinates: [
        [
          [
            [30, 30],
            [40, 30],
            [40, 40],
            [30, 40],
            [30, 30],
          ],
        ],
        [
          [
            [4, 4],
            [6, 4],
            [6, 6],
            [4, 6],
            [4, 4],
          ],
        ],
      ],
    };
    expect(geometryIntersectsMultiPolygon(mp, AREA)).toBe(true);
  });

  it('null-geometri', () => {
    expect(geometryIntersectsMultiPolygon(null, AREA)).toBe(false);
  });
});
