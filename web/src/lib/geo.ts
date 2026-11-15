/**
 * Grid and projection constants shared by the map and the tile chips, with no
 * Leaflet import, so pages without a map don't pull Leaflet into their bundle.
 *
 * Mirrors analogatlas/config.py and analogatlas/tiles.py. The Python grid and
 * these numbers must agree, or a chip shows the wrong piece of ground.
 */

/** config.MOON_RADIUS_M */
export const MOON_RADIUS_M = 1_737_400;
/** config.MOON_SP_EXTENT_M — the polar matrix is one tile tall at zoom 0. */
export const SP_EXTENT_M = 2_191_860;
/** config.MOON_SP_ORIGIN_M — top-left corner of the polar tile matrix, in metres. */
export const SP_ORIGIN_M: [number, number] = [-1_095_930, 1_095_930];
/** config.MOON_POLAR_MAX_LAT — the edge of the LOLA/PGDA polar products. */
export const POLAR_MAX_LAT = -75;

/** config.MOON_ZOOM and MOON_TILE_DEG: the equatorial Moon grid. */
export const MOON_ZOOM = 6;
export const MOON_TILE_DEG = 180 / 2 ** MOON_ZOOM;
/** The Mars grid: Trek zoom-7 tiles, 1.406° = ~83 km (docs/MARS-PLAN.md). */
export const MARS_ZOOM = 7;
export const MARS_TILE_DEG = 180 / 2 ** MARS_ZOOM;
/** config.TILE_KM: every tile, on every body, is this wide on the ground. */
export const TILE_KM = MOON_TILE_DEG * ((2 * Math.PI * MOON_RADIUS_M) / 1000 / 360);
/** config.EARTH_TILE_DEG_LAT */
export const EARTH_TILE_DEG_LAT = TILE_KM / ((2 * Math.PI * 6_371_000) / 1000 / 360);

const DEG = Math.PI / 180;

/** tiles.sp_forward: lat/lon in degrees -> (x, y) metres from the south pole. */
export function spForward(lat: number, lon: number): [number, number] {
  const rho = 2 * MOON_RADIUS_M * Math.tan(Math.PI / 4 + (lat * DEG) / 2);
  return [rho * Math.sin(lon * DEG), rho * Math.cos(lon * DEG)];
}

/** tiles.sp_inverse */
export function spInverse(x: number, y: number): [number, number] {
  const rho = Math.hypot(x, y);
  return [(2 * Math.atan(rho / (2 * MOON_RADIUS_M))) / DEG - 90, Math.atan2(x, y) / DEG];
}
