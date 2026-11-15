/**
 * Basemap tile sources, mirrored from analogatlas/config.py so the map shows
 * the same imagery the index was built from (ARCHITECTURE.md §2).
 *
 * Both are served in EPSG:4326 (plain lat/lon), which is why the map uses
 * Leaflet's EPSG4326 CRS: Trek's zoom-0 grid is 2x1 tiles, exactly Leaflet's.
 */
import type { Body } from "./types";

export interface Basemap {
  kind: "xyz" | "wms";
  url: string;
  /** WMS only */
  layers?: string;
  maxNativeZoom: number;
  attribution: string;
}

export const BASEMAPS: Record<Body, Basemap> = {
  moon: {
    kind: "xyz",
    // LROC WAC global mosaic via NASA Moon Trek WMTS (config.MOON_LAYERS["img"])
    url:
      "https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/" +
      "default/default028mm/{z}/{y}/{x}.jpg",
    maxNativeZoom: 8,
    attribution: "LROC WAC mosaic: NASA/GSFC/ASU, via NASA Moon Trek",
  },
  moon_polar: {
    kind: "xyz",
    // LOLA polar hillshade via Trek's south polar tile tree
    // (config.MOON_SP_LAYERS["shade"]). There is no WAC polar mosaic, and the
    // pole is half in genuine shadow, so hillshade is the honest basemap here.
    url:
      "https://trek.nasa.gov/tiles/Moon/SP/LRO_LOLA_Shade_SPole75_30mp_v04/1.0.0/" +
      "default/default028mm/{z}/{y}/{x}.png",
    maxNativeZoom: 6,
    attribution: "LOLA polar hillshade: NASA/GSFC/MIT, via NASA Moon Trek",
  },
  mars: {
    kind: "xyz",
    // Viking colour mosaic via NASA Mars Trek WMTS: the imagery the Mars
    // index is built from (docs/MARS-PLAN.md).
    url:
      "https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/" +
      "default/default028mm/{z}/{y}/{x}.jpg",
    maxNativeZoom: 7,
    attribution: "Viking MDIM 2.1 colour mosaic: NASA/JPL/USGS, via NASA Mars Trek",
  },
  earth: {
    kind: "wms",
    // Blue Marble via NASA GIBS WMS (config.GIBS_WMS, config.EARTH_LAYERS["img"])
    url: "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi",
    layers: "BlueMarble_NextGeneration",
    maxNativeZoom: 8,
    attribution: "Blue Marble: NASA Earth Observatory, via NASA GIBS",
  },
};
