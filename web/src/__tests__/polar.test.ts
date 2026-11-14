/**
 * The polar pane's projection has to agree with the Python grid
 * (analogatlas/tiles.py sp_forward/sp_inverse) or tiles land in the wrong
 * place. These are the same checks as tests/test_polar.py.
 */
import L from "leaflet";
import { describe, expect, it } from "vitest";

import {
  CRS_MOON_SOUTH_POLAR,
  SP_EXTENT_M,
  SouthPolarProjection,
  polarCellCorners,
} from "../lib/polar";
import { isPolar } from "../lib/types";

describe("south polar projection", () => {
  it("puts the pole at the origin", () => {
    const p = SouthPolarProjection.project(new L.LatLng(-90, 0));
    expect(p.x).toBeCloseTo(0, 6);
    expect(p.y).toBeCloseTo(0, 6);
  });

  it("matches the products' 457440 m edge radius at 75 degrees south", () => {
    const p = SouthPolarProjection.project(new L.LatLng(-75, 0));
    expect(Math.hypot(p.x, p.y)).toBeCloseTo(457_440, -3);
  });

  it("round-trips latitude and longitude", () => {
    for (const [lat, lon] of [
      [-75, 0],
      [-80, 129.78],
      [-85.5, -88.34],
      [-89.9, 31],
    ]) {
      const back = SouthPolarProjection.unproject(
        SouthPolarProjection.project(new L.LatLng(lat, lon)),
      );
      expect(back.lat).toBeCloseTo(lat, 9);
      expect(((back.lng - lon + 540) % 360) - 180).toBeCloseTo(0, 9);
    }
  });

  it("puts 0 degrees east on the +y axis, like the LOLA products", () => {
    const p = SouthPolarProjection.project(new L.LatLng(-80, 0));
    expect(p.x).toBeCloseTo(0, 6);
    expect(p.y).toBeGreaterThan(0);
    const q = SouthPolarProjection.project(new L.LatLng(-80, 90));
    expect(q.x).toBeGreaterThan(0);
    expect(q.y).toBeCloseTo(0, 6);
  });
});

/** `L.CRS` is typed as a namespace, so `transformation` is not on the type. */
const crsTransformation = () =>
  (CRS_MOON_SOUTH_POLAR as unknown as { transformation: L.Transformation }).transformation;

describe("CRS_MOON_SOUTH_POLAR", () => {
  it("maps the tile-matrix origin to pixel (0, 0) at zoom 0", () => {
    const origin = crsTransformation().transform(
      new L.Point(-SP_EXTENT_M / 2, SP_EXTENT_M / 2),
      CRS_MOON_SOUTH_POLAR.scale(0),
    );
    expect(origin.x).toBeCloseTo(0, 6);
    expect(origin.y).toBeCloseTo(0, 6);
  });

  it("makes one zoom-0 tile span the full extent", () => {
    const corner = crsTransformation().transform(
      new L.Point(SP_EXTENT_M / 2, -SP_EXTENT_M / 2),
      CRS_MOON_SOUTH_POLAR.scale(0),
    );
    expect(corner.x).toBeCloseTo(256, 6);
    expect(corner.y).toBeCloseTo(256, 6);
  });

  it("measures distance in planar metres", () => {
    const d = CRS_MOON_SOUTH_POLAR.distance(new L.LatLng(-90, 0), new L.LatLng(-89, 0));
    // 1 degree from the pole is ~30.3 km of ground
    expect(d / 1000).toBeGreaterThan(25);
    expect(d / 1000).toBeLessThan(35);
  });
});

describe("polarCellCorners", () => {
  it("returns four corners that enclose the cell centre", () => {
    const corners = polarCellCorners([0, 300_000, 85_284]);
    expect(corners).toHaveLength(4);
    const projected = corners.map((c) => SouthPolarProjection.project(c));
    expect(Math.min(...projected.map((p) => p.x))).toBeCloseTo(-42_642, -2);
    expect(Math.max(...projected.map((p) => p.x))).toBeCloseTo(42_642, -2);
    expect(Math.min(...projected.map((p) => p.y))).toBeCloseTo(257_358, -2);
    expect(Math.max(...projected.map((p) => p.y))).toBeCloseTo(342_642, -2);
  });

  it("handles the cell containing the pole, where longitude is meaningless", () => {
    const corners = polarCellCorners([0, 0, 85_284]);
    expect(corners.every((c) => Number.isFinite(c.lat) && Number.isFinite(c.lng))).toBe(true);
  });
});

describe("isPolar", () => {
  it("routes only the south pole to the polar pane", () => {
    expect(isPolar("moon_polar")).toBe(true);
    expect(isPolar("moon")).toBe(false);
    expect(isPolar("earth")).toBe(false);
  });
});
