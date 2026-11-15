/** Tile chips must show the same 85 km of ground the index was built from. */
import { describe, expect, it } from "vitest";

import { chipFor, sourceBodyOf, type ChipPiece } from "../lib/chips";
import { spForward } from "../lib/geo";

/** The pieces must tile the unit square with no gap at any edge. */
function covers(pieces: ChipPiece[]) {
  expect(pieces.length).toBeGreaterThan(0);
  expect(Math.min(...pieces.map((p) => p.left))).toBeLessThanOrEqual(1e-9);
  expect(Math.min(...pieces.map((p) => p.top))).toBeLessThanOrEqual(1e-9);
  expect(Math.max(...pieces.map((p) => p.left + p.width))).toBeGreaterThanOrEqual(1 - 1e-9);
  expect(Math.max(...pieces.map((p) => p.top + p.height))).toBeGreaterThanOrEqual(1 - 1e-9);
}

describe("chipFor", () => {
  it("asks GIBS for the Earth tile's own box, lat first (WMS 1.3.0 EPSG:4326)", () => {
    const chip = chipFor("earth", {
      lat: -24.5, lon: -69.9, lat_min: -24.88, lat_max: -24.12, lon_min: -70.32, lon_max: -69.48,
    });
    expect(chip.pieces).toHaveLength(1);
    const url = new URL(chip.pieces[0].url);
    expect(url.searchParams.get("BBOX")).toBe("-24.8800,-70.3200,-24.1200,-69.4800");
    expect(url.searchParams.get("LAYERS")).toBe("BlueMarble_NextGeneration");
  });

  it("uses ASTER relief for the Earth terrain layer", () => {
    const url = new URL(chipFor("earth", { lat: 10, lon: 10 }, "shade").pieces[0].url);
    expect(url.searchParams.get("LAYERS")).toBe("ASTER_GDEM_Greyscale_Shaded_Relief");
  });

  it("widens a Moon chip by 1/cos(lat) so it is square on the ground (#27)", () => {
    const eq = chipFor("moon", { lat: 1.40625, lon: 0.5 });
    const high = chipFor("moon", { lat: 57.65625, lon: 0.5 });
    covers(eq.pieces);
    covers(high.pieces);
    // a source tile is narrower in the chip at 57.7° than at the equator
    expect(high.pieces[0].width).toBeLessThan(eq.pieces[0].width * 0.6);
    expect(eq.pieces[0].url).toMatch(/LRO_WAC_Mosaic_Global_303ppd_v02\/1\.0\.0\/default\/default028mm\/6\//);
  });

  it("wraps Moon tile columns across the date line", () => {
    const chip = chipFor("moon", { lat: 0, lon: 179.9 });
    covers(chip.pieces);
    const cols = chip.pieces.map((p) => Number(p.url.match(/\/(\d+)\.jpg$/)![1]));
    expect(cols).toContain(0);
    expect(cols).toContain(127);
  });

  it("cuts polar chips from the polar stereographic tree, hillshade only", () => {
    const [x, y] = spForward(-85.98, -1.67);
    const chip = chipFor("moon_polar", { lat: -85.98, lon: -1.67, xy: [x, y, 85_000] }, "img");
    expect(chip.layer).toBe("shade");
    expect(chip.pieces.length).toBeLessThanOrEqual(4);
    covers(chip.pieces);
    expect(chip.pieces[0].url).toContain("/Moon/SP/LRO_LOLA_Shade_SPole75");
  });

  it("cuts Mars chips from Mars Trek at zoom 7, square on the ground", () => {
    const eq = chipFor("mars", { lat: 0.7, lon: 0.5 });
    const high = chipFor("mars", { lat: 49.02, lon: -171.85 }, "shade");
    covers(eq.pieces);
    covers(high.pieces);
    expect(eq.pieces[0].url).toMatch(/\/Mars\/EQ\/Mars_Viking_MDIM21_ClrMosaic_global_232m\/1\.0\.0\/default\/default028mm\/7\//);
    expect(high.pieces[0].url).toContain("Mars_MOLA_blend200ppx_HRSC_Shade");
    expect(high.source).toMatch(/Mars Trek/);
    // 1/cos(49°) wider in longitude, so each source tile is narrower in the chip
    expect(high.pieces[0].width).toBeLessThan(eq.pieces[0].width * 0.7);
    // zoom 7 has 256 columns and 128 rows
    for (const p of [...eq.pieces, ...high.pieces]) {
      const [, row, col] = p.url.match(/\/7\/(\d+)\/(\d+)\.jpg$/)!;
      expect(Number(row)).toBeLessThan(128);
      expect(Number(col)).toBeLessThan(256);
    }
  });

  it("finds the same polar chip from lat/lon alone", () => {
    const [x, y] = spForward(-87.45, -5.17);
    const a = chipFor("moon_polar", { lat: -87.45, lon: -5.17 });
    const b = chipFor("moon_polar", { lat: 0, lon: 0, xy: [x, y, 85_000] });
    expect(a.pieces.map((p) => p.url)).toEqual(b.pieces.map((p) => p.url));
  });
});

describe("sourceBodyOf", () => {
  it("tells a polar report-card record from an equatorial one", () => {
    expect(sourceBodyOf({ tile_id: "moonsp_3_4", x_m: 1 })).toBe("moon_polar");
    expect(sourceBodyOf({ tile_id: "moon_6_1_2" })).toBe("moon");
  });

  it("recognises a Mars record by its body or its tile id", () => {
    expect(sourceBodyOf({ tile_id: "mars_7_51_183" })).toBe("mars");
    expect(sourceBodyOf({ tile_id: "x", body: "mars" })).toBe("mars");
  });
});
