/**
 * Tile imagery for any tile, straight from NASA's public tile services.
 *
 * The index was built from 85 km chips cut out of NASA Moon Trek and GIBS
 * (analogatlas/tiles.py). Shipping those chips would mean ~1 GB of images, so
 * the browser rebuilds the same view from the same services instead:
 *
 *  - Earth: one GIBS WMS GetMap over the tile's box, the same request
 *    tiles._fetch_earth makes (hillshade uses GIBS's ASTER GDEM relief layer;
 *    the index's own Earth hillshade came from Earth Engine).
 *  - Moon: the Trek WMTS tiles covering a box that is square in kilometres,
 *    positioned and clipped, which is what tiles._fetch_moon does on the server.
 *  - Moon south pole: the same, on Trek's polar stereographic tile tree. Only
 *    hillshade there: the NAC mosaic covers 85.5-90°S and is half dark.
 */
import {
  EARTH_TILE_DEG_LAT, MOON_TILE_DEG, MOON_ZOOM, SP_EXTENT_M, SP_ORIGIN_M, TILE_KM, spForward,
} from "./geo";
import type { Body, Layer } from "./types";

const TILE_PX = 256;

const GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi";
const EARTH_LAYERS: Record<Layer, string> = {
  img: "BlueMarble_NextGeneration",
  shade: "ASTER_GDEM_Greyscale_Shaded_Relief",
};
const TREK = "https://trek.nasa.gov/tiles/Moon";
const MOON_LAYERS: Record<Layer, string> = {
  img: `${TREK}/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg`,
  shade: `${TREK}/EQ/LRO_LOLA_Shade_Global_256ppd_v06/1.0.0/default/default028mm/{z}/{y}/{x}.png`,
};
const POLAR_SHADE =
  `${TREK}/SP/LRO_LOLA_Shade_SPole75_30mp_v04/1.0.0/default/default028mm/{z}/{y}/{x}.png`;
/** Polar chips use zoom 4: 137 km tiles, so at most 2x2 tiles per 85 km chip. */
const POLAR_CHIP_ZOOM = 4;

/** Anything with a position, and optionally the tile's own box or polar cell. */
export interface TileLike {
  lat: number;
  lon: number;
  lat_min?: number | null;
  lat_max?: number | null;
  lon_min?: number | null;
  lon_max?: number | null;
  /** moon_polar only: [x_m, y_m, size_m] */
  xy?: [number, number, number] | null;
  x_m?: number | null;
  y_m?: number | null;
  size_m?: number | null;
}

/** A piece of one source tile, placed in a unit square (0-1 on each axis). */
export interface ChipPiece {
  url: string;
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface Chip {
  pieces: ChipPiece[];
  /** What the picture is, in words, for alt text and captions. */
  source: string;
  /** The layer actually shown; the pole falls back to hillshade. */
  layer: Layer;
}

const fill = (tpl: string, z: number, y: number, x: number) =>
  tpl.replace("{z}", String(z)).replace("{y}", String(y)).replace("{x}", String(x));

const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

function earthChip(t: TileLike, layer: Layer): Chip {
  const half = EARTH_TILE_DEG_LAT / 2;
  const cos = Math.max(Math.cos((t.lat * Math.PI) / 180), 0.05);
  const latMin = num(t.lat_min) ?? t.lat - half;
  const latMax = num(t.lat_max) ?? t.lat + half;
  const lonMin = num(t.lon_min) ?? t.lon - half / cos;
  const lonMax = num(t.lon_max) ?? t.lon + half / cos;
  const q = new URLSearchParams({
    SERVICE: "WMS", REQUEST: "GetMap", VERSION: "1.3.0", STYLES: "",
    LAYERS: EARTH_LAYERS[layer], CRS: "EPSG:4326",
    BBOX: [latMin, lonMin, latMax, lonMax].map((v) => v.toFixed(4)).join(","),
    WIDTH: String(TILE_PX), HEIGHT: String(TILE_PX),
    FORMAT: "image/jpeg",
  });
  return {
    pieces: [{ url: `${GIBS_WMS}?${q}`, left: 0, top: 0, width: 1, height: 1 }],
    source: layer === "img" ? "Blue Marble, NASA GIBS" : "ASTER GDEM shaded relief, NASA GIBS",
    layer,
  };
}

/** Place every source tile that overlaps a pixel box [x0,x1]×[y0,y1]. */
function piecesFor(
  x0: number, x1: number, y0: number, y1: number,
  url: (row: number, col: number) => string | null,
): ChipPiece[] {
  const w = x1 - x0;
  const h = y1 - y0;
  const out: ChipPiece[] = [];
  for (let r = Math.floor(y0 / TILE_PX); r <= Math.floor((y1 - 1e-9) / TILE_PX); r++) {
    for (let c = Math.floor(x0 / TILE_PX); c <= Math.floor((x1 - 1e-9) / TILE_PX); c++) {
      const u = url(r, c);
      if (!u) continue;
      out.push({
        url: u,
        left: (c * TILE_PX - x0) / w,
        top: (r * TILE_PX - y0) / h,
        width: TILE_PX / w,
        height: TILE_PX / h,
      });
    }
  }
  return out;
}

function moonChip(t: TileLike, layer: Layer): Chip {
  // Trek EQ: 2^(z+1) x 2^z tiles of MOON_TILE_DEG. A chip TILE_KM tall spans
  // one tile of latitude and 1/cos(lat) tiles of longitude (#27).
  const dpp = MOON_TILE_DEG / TILE_PX;
  const halfLat = MOON_TILE_DEG / 2;
  const halfLon = halfLat / Math.max(Math.cos((t.lat * Math.PI) / 180), 0.05);
  const across = 2 ** (MOON_ZOOM + 1);
  const rows = 2 ** MOON_ZOOM;
  const pieces = piecesFor(
    (t.lon - halfLon + 180) / dpp, (t.lon + halfLon + 180) / dpp,
    (90 - (t.lat + halfLat)) / dpp, (90 - (t.lat - halfLat)) / dpp,
    (r, c) => (r < 0 || r >= rows ? null
      : fill(MOON_LAYERS[layer], MOON_ZOOM, r, ((c % across) + across) % across)),
  );
  return {
    pieces,
    source: layer === "img" ? "LROC WAC mosaic, NASA Moon Trek" : "LOLA hillshade, NASA Moon Trek",
    layer,
  };
}

function polarChip(t: TileLike): Chip {
  const x = num(t.xy?.[0]) ?? num(t.x_m);
  const y = num(t.xy?.[1]) ?? num(t.y_m);
  const size = num(t.xy?.[2]) ?? num(t.size_m) ?? TILE_KM * 1000;
  const [cx, cy] = x !== null && y !== null ? [x, y] : spForward(t.lat, t.lon);
  const mpp = SP_EXTENT_M / 2 ** POLAR_CHIP_ZOOM / TILE_PX;
  const [ox, oy] = SP_ORIGIN_M;
  const h = size / 2;
  const n = 2 ** POLAR_CHIP_ZOOM;
  const pieces = piecesFor(
    (cx - h - ox) / mpp, (cx + h - ox) / mpp,
    (oy - (cy + h)) / mpp, (oy - (cy - h)) / mpp,
    (r, c) => (r < 0 || r >= n || c < 0 || c >= 2 * n ? null
      : fill(POLAR_SHADE, POLAR_CHIP_ZOOM, r, c)),
  );
  return { pieces, source: "LOLA polar hillshade, NASA Moon Trek", layer: "shade" };
}

export function chipFor(body: Body, tile: TileLike, layer: Layer = "img"): Chip {
  if (body === "earth") return earthChip(tile, layer);
  if (body === "moon_polar") return polarChip(tile);
  return moonChip(tile, layer);
}

/** Which body a report card's lunar record belongs to. */
export const lunarBodyOf = (rec: Record<string, unknown>): Body =>
  typeof rec.x_m === "number" || String(rec.tile_id ?? "").startsWith("moonsp_")
    ? "moon_polar" : "moon";
