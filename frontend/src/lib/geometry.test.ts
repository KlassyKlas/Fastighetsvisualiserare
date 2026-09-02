import { describe, expect, it } from 'vitest';
import { geometryBounds } from './geometry';

describe('geometryBounds', () => {
  it('punkt ger degenererad rektangel', () => {
    expect(geometryBounds({ type: 'Point', coordinates: [18, 59] })).toEqual([18, 59, 18, 59]);
  });

  it('linje ger rektangeln kring alla hörn', () => {
    expect(
      geometryBounds({
        type: 'LineString',
        coordinates: [
          [17.88, 59.39],
          [17.84, 59.3],
          [17.85, 59.25],
        ],
      }),
    ).toEqual([17.84, 59.25, 17.88, 59.39]);
  });

  it('multilinje räknar alla delsträckor', () => {
    expect(
      geometryBounds({
        type: 'MultiLineString',
        coordinates: [
          [
            [1, 2],
            [3, 4],
          ],
          [[5, 6]],
        ],
      }),
    ).toEqual([1, 2, 5, 6]);
  });

  it('polygon med hål räknar alla ringar', () => {
    expect(
      geometryBounds({
        type: 'Polygon',
        coordinates: [
          [
            [0, 0],
            [10, 0],
            [10, 10],
            [0, 10],
            [0, 0],
          ],
          [
            [4, 4],
            [6, 4],
            [6, 6],
            [4, 6],
            [4, 4],
          ],
        ],
      }),
    ).toEqual([0, 0, 10, 10]);
  });

  it('multipolygon spänner över alla delskiften', () => {
    expect(
      geometryBounds({
        type: 'MultiPolygon',
        coordinates: [
          [
            [
              [0, 0],
              [1, 0],
              [1, 1],
              [0, 1],
              [0, 0],
            ],
          ],
          [
            [
              [5, 5],
              [6, 5],
              [6, 7],
              [5, 7],
              [5, 5],
            ],
          ],
        ],
      }),
    ).toEqual([0, 0, 6, 7]);
  });

  it('GeometryCollection följs rekursivt', () => {
    expect(
      geometryBounds({
        type: 'GeometryCollection',
        geometries: [
          { type: 'Point', coordinates: [10, 50] },
          {
            type: 'MultiPoint',
            coordinates: [
              [12, 52],
              [11, 49],
            ],
          },
        ],
      }),
    ).toEqual([10, 49, 12, 52]);
  });

  it('saknad eller tom geometri ger null', () => {
    expect(geometryBounds(null)).toBeNull();
    expect(geometryBounds(undefined)).toBeNull();
    expect(geometryBounds({ type: 'MultiPoint', coordinates: [] })).toBeNull();
    expect(geometryBounds({ type: 'GeometryCollection', geometries: [] })).toBeNull();
  });
});
