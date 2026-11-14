/**
 * South polar stereographic CRS for the Moon (#26).
 *
 * The pole cannot be drawn on the lat/lon map: at 85°S an equirectangular tile
 * is 6 km wide and 85 km tall, so craters smear into horizontal streaks. Trek
 * serves the polar products from a separate tile tree (`Moon/SP`) whose matrix
 * is in metres from the pole, and this is the matching Leaflet CRS.
 *
 * Mirrors `analogatlas/tiles.py: sp_forward / sp_inverse` and the
 * `MOON_SP_*` constants in `analogatlas/config.py` — the Python grid and this
 * pane must agree or tiles land in the wrong place.
 *
 * No proj4leaflet: the spherical stereographic forward/inverse is six lines,
 * and Leaflet takes a custom CRS directly.
 */
import L from "leaflet";

/** config.MOON_RADIUS_M */
export const MOON_RADIUS_M = 1_737_400;
/** config.MOON_SP_EXTENT_M — the matrix is one tile tall at zoom 0. */
export const SP_EXTENT_M = 2_191_860;
/** config.MOON_SP_ORIGIN_M — top-left corner of the tile matrix, in metres. */
export const SP_ORIGIN_M: [number, number] = [-1_095_930, 1_095_930];
/** config.MOON_POLAR_MAX_LAT — the edge of the LOLA/PGDA polar products. */
export const POLAR_MAX_LAT = -75;

const DEG = Math.PI / 180;

export const SouthPolarProjection: L.Projection = {
  project(latlng: L.LatLng): L.Point {
    // rho = 2R tan(45° + lat/2); zero at the pole, 457 km at 75°S
    const rho = 2 * MOON_RADIUS_M * Math.tan(Math.PI / 4 + (latlng.lat * DEG) / 2);
    const lam = latlng.lng * DEG;
    return new L.Point(rho * Math.sin(lam), rho * Math.cos(lam));
  },
  unproject(point: L.Point): L.LatLng {
    const rho = Math.sqrt(point.x * point.x + point.y * point.y);
    const lat = (2 * Math.atan(rho / (2 * MOON_RADIUS_M))) / DEG - 90;
    return new L.LatLng(lat, Math.atan2(point.x, point.y) / DEG);
  },
  bounds: L.bounds(
    [-SP_EXTENT_M / 2, -SP_EXTENT_M / 2],
    [SP_EXTENT_M / 2, SP_EXTENT_M / 2],
  ),
};

/**
 * Projected metres -> normalised tile-matrix units, which Leaflet then scales
 * by 256 * 2^zoom. Chosen so the matrix origin lands on pixel (0, 0):
 *   x' = (x - originX) / extent, y' = (originY - y) / extent
 */
export const CRS_MOON_SOUTH_POLAR = L.Util.extend({}, L.CRS, {
  code: "MOON:SOUTH_POLAR_STEREOGRAPHIC",
  projection: SouthPolarProjection,
  transformation: new L.Transformation(
    1 / SP_EXTENT_M,
    -SP_ORIGIN_M[0] / SP_EXTENT_M,
    -1 / SP_EXTENT_M,
    SP_ORIGIN_M[1] / SP_EXTENT_M,
  ),
  // Planar metres: the reason to use this projection at all.
  distance(a: L.LatLng, b: L.LatLng): number {
    return SouthPolarProjection.project(a).distanceTo(SouthPolarProjection.project(b));
  },
  infinite: false,
  wrapLng: undefined,
  wrapLat: undefined,
  // L.CRS is typed as a namespace rather than an instance, so the extended
  // object does not structurally match L.CRS even though Leaflet accepts it.
}) as unknown as L.CRS;

/** The four corners of a polar grid cell, as lat/lng for Leaflet to re-project. */
export function polarCellCorners(xy: [number, number, number]): L.LatLng[] {
  const [x, y, size] = xy;
  const h = size / 2;
  return ([
    [x - h, y - h],
    [x + h, y - h],
    [x + h, y + h],
    [x - h, y + h],
  ] as const).map(([px, py]) => SouthPolarProjection.unproject(new L.Point(px, py)));
}
