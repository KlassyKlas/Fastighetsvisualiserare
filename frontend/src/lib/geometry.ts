/**
 * Rena GeoJSON-hjälpfunktioner utan kartberoende — används av
 * kartbryggan (fitBounds), isokron-origot och ägarvyns utbredning.
 * Allt arbetar i plana WGS84-grader; inga metriska beräkningar görs
 * här (de hör hemma i PostGIS).
 */
import type { Geometry, Position } from 'geojson';

/** Omslutande rektangel [väst, syd, öst, norr] i WGS84. */
export type Bounds = [number, number, number, number];

/**
 * Alla koordinater i en geometri, oavsett typ och nästlingsdjup.
 * GeometryCollection följs rekursivt.
 */
function collectPositions(geometry: Geometry, into: Position[] = []): Position[] {
  if (geometry.type === 'GeometryCollection') {
    for (const member of geometry.geometries) {
      collectPositions(member, into);
    }
    return into;
  }
  const flatten = (coords: unknown): void => {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === 'number') {
      into.push(coords as Position);
      return;
    }
    for (const nested of coords) {
      flatten(nested);
    }
  };
  flatten(geometry.coordinates);
  return into;
}

/**
 * Omslutande rektangel för en geometri, eller null om geometrin saknas
 * eller är tom. En punkt ger en degenererad rektangel (väst = öst,
 * syd = norr) — Mapbox fitBounds hanterar det genom att zooma till maxZoom.
 */
export function geometryBounds(geometry: Geometry | null | undefined): Bounds | null {
  if (!geometry) return null;
  const positions = collectPositions(geometry);
  if (positions.length === 0) return null;

  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const [lng, lat] of positions) {
    west = Math.min(west, lng);
    east = Math.max(east, lng);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  return [west, south, east, north];
}
