/**
 * Klientsidiga geometritester — används ENBART i demo-läget för att
 * spegla backendens ST_Intersects-semantik (bevakade områden). Mot
 * riktig backend görs all spatial analys i PostGIS.
 *
 * Testerna arbetar i plana WGS84-koordinater, precis som ST_Intersects
 * över geometry (inte geography) — samma semantik som backendens
 * händelsefråga i app/services/watches.py.
 */
import type { Geometry, Position } from 'geojson';

type Ring = Position[];
type PolygonCoords = Ring[];
type MultiPolygonCoords = PolygonCoords[];

/** Ray casting: ligger punkten innanför ringen? Kantpunkter räknas som inne. */
export function pointInRing(point: Position, ring: Ring): boolean {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** Punkt i polygon: innanför yttre ringen och inte i något hål. */
export function pointInPolygon(point: Position, polygon: PolygonCoords): boolean {
  if (polygon.length === 0 || !pointInRing(point, polygon[0])) return false;
  return polygon.slice(1).every((hole) => !pointInRing(point, hole));
}

/** Skär (eller nuddar) sträckorna p1–p2 och p3–p4 varandra? */
export function segmentsIntersect(p1: Position, p2: Position, p3: Position, p4: Position): boolean {
  const orientation = (a: Position, b: Position, c: Position): number => {
    const value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]);
    if (value === 0) return 0;
    return value > 0 ? 1 : 2;
  };
  const onSegment = (a: Position, b: Position, c: Position): boolean =>
    b[0] <= Math.max(a[0], c[0]) &&
    b[0] >= Math.min(a[0], c[0]) &&
    b[1] <= Math.max(a[1], c[1]) &&
    b[1] >= Math.min(a[1], c[1]);

  const o1 = orientation(p1, p2, p3);
  const o2 = orientation(p1, p2, p4);
  const o3 = orientation(p3, p4, p1);
  const o4 = orientation(p3, p4, p2);

  if (o1 !== o2 && o3 !== o4) return true;
  if (o1 === 0 && onSegment(p1, p3, p2)) return true;
  if (o2 === 0 && onSegment(p1, p4, p2)) return true;
  if (o3 === 0 && onSegment(p3, p1, p4)) return true;
  return o4 === 0 && onSegment(p3, p2, p4);
}

function lineCrossesPolygonEdge(line: Ring, polygon: PolygonCoords): boolean {
  for (const ring of polygon) {
    for (let i = 0; i < ring.length - 1; i++) {
      for (let j = 0; j < line.length - 1; j++) {
        if (segmentsIntersect(ring[i], ring[i + 1], line[j], line[j + 1])) return true;
      }
    }
  }
  return false;
}

function lineIntersectsPolygon(line: Ring, polygon: PolygonCoords): boolean {
  return (
    line.some((point) => pointInPolygon(point, polygon)) || lineCrossesPolygonEdge(line, polygon)
  );
}

function polygonIntersectsPolygon(a: PolygonCoords, b: PolygonCoords): boolean {
  // Någon punkt i den andra, eller kanterna korsas (täcker även fallet
  // där den ena helt omsluter den andra — då ligger alla hörn "inne").
  if (a[0]?.some((point) => pointInPolygon(point, b))) return true;
  if (b[0]?.some((point) => pointInPolygon(point, a))) return true;
  return lineCrossesPolygonEdge(a[0] ?? [], b);
}

/**
 * Skär geometrin bevakningsområdet (MultiPolygon)? Samma svar som
 * PostGIS ST_Intersects för de geometrityper som förekommer i appen.
 */
export function geometryIntersectsMultiPolygon(
  geometry: Geometry | null | undefined,
  area: MultiPolygonCoords,
): boolean {
  if (!geometry) return false;
  return area.some((polygon) => {
    switch (geometry.type) {
      case 'Point':
        return pointInPolygon(geometry.coordinates, polygon);
      case 'MultiPoint':
        return geometry.coordinates.some((point) => pointInPolygon(point, polygon));
      case 'LineString':
        return lineIntersectsPolygon(geometry.coordinates, polygon);
      case 'MultiLineString':
        return geometry.coordinates.some((line) => lineIntersectsPolygon(line, polygon));
      case 'Polygon':
        return polygonIntersectsPolygon(geometry.coordinates, polygon);
      case 'MultiPolygon':
        return geometry.coordinates.some((poly) => polygonIntersectsPolygon(poly, polygon));
      case 'GeometryCollection':
        return geometry.geometries.some((g) => geometryIntersectsMultiPolygon(g, [polygon]));
      default:
        return false;
    }
  });
}
