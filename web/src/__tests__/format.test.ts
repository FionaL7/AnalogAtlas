import { describe, expect, it } from "vitest";

import { coords, groupBreakdown, newFirst, percent, verdict } from "../lib/format";
import { mockTwins } from "../lib/mocks";
import type { AnalogHit } from "../lib/types";

describe("percent", () => {
  it("formats a 0-1 match as a whole percent", () => {
    expect(percent(0.912)).toBe("91%");
    expect(percent(0)).toBe("0%");
    expect(percent(1)).toBe("100%");
  });

  it("does not turn a missing value into 0%", () => {
    expect(percent(null)).toBe("—");
    expect(percent(undefined)).toBe("—");
    expect(percent(NaN)).toBe("—");
  });
});

describe("verdict", () => {
  it("separates Earth's limits from a merely poor match", () => {
    expect(verdict(0)).toBe("cannot-reproduce");
    expect(verdict(0.05)).toBe("breaks");
  });

  it("treats a null match as not comparable, not as a failure", () => {
    expect(verdict(null)).toBe("no-equivalent");
  });

  it("holds at and above the threshold", () => {
    expect(verdict(0.6)).toBe("holds");
    expect(verdict(0.59)).toBe("partial");
  });
});

describe("groupBreakdown", () => {
  const groups = groupBreakdown(mockTwins("moon_6_0_90", "earth_-77.50_+162.00").breakdown);

  it("puts every Earth's-limits row in its own can't-reproduce group", () => {
    expect(groups["cannot-reproduce"].map((r) => r.dimension)).toEqual([
      "Atmosphere", "Gravity", "Radiation", "Magnetic field", "Day/night cycle", "Regolith dust",
    ]);
  });

  it("groups by kind, so a real 0% comparison is a breakdown, not an Earth limit", () => {
    const g = groupBreakdown([
      { dimension: "Dryness", moon: "-", earth: "-", match: 0, note: "", kind: "compare" },
      { dimension: "Gravity", moon: "-", earth: "-", match: 0, note: "", kind: "earth_limit" },
    ]);
    expect(g.breaks.map((r) => r.dimension)).toEqual(["Dryness"]);
    expect(g["cannot-reproduce"].map((r) => r.dimension)).toEqual(["Gravity"]);
  });

  it("still groups rows from an older API that sends no kind", () => {
    const g = groupBreakdown([
      { dimension: "Atmosphere", moon: "-", earth: "-", match: 0, note: "" },
      { dimension: "Rock cover", moon: "-", earth: "-", match: null, note: "" },
    ]);
    expect(g["cannot-reproduce"].map((r) => r.dimension)).toEqual(["Atmosphere"]);
    expect(g["no-equivalent"].map((r) => r.dimension)).toEqual(["Rock cover"]);
  });

  it("keeps a null-match dimension out of both holds and breaks", () => {
    expect(groups["no-equivalent"].map((r) => r.dimension)).toEqual(["Surface rock cover"]);
    expect(groups.holds.every((r) => r.match !== null)).toBe(true);
    expect(groups.breaks.every((r) => r.match !== null && r.match > 0)).toBe(true);
  });

  it("loses no rows", () => {
    const rows = mockTwins("a", "b").breakdown;
    const total = Object.values(groups).reduce((n, g) => n + g.length, 0);
    expect(total).toBe(rows.length);
  });

  it("sorts the strong matches into holds", () => {
    expect(groups.holds.map((r) => r.dimension)).toContain("Median slope");
    expect(groups.breaks.map((r) => r.dimension)).toContain("Surface temperature swing");
  });
});

describe("newFirst", () => {
  const hit = (tile_id: string, known: string | null): AnalogHit => ({
    tile_id, lat: 0, lon: 0, score: 0.5, visual_cos_scaled: 0.5, physical: 0.5,
    known_analog: known, tile_url: "",
  });

  it("leads with candidates that are not known analog sites", () => {
    const sorted = newFirst([hit("a", "Atacama"), hit("b", null), hit("c", "Death Valley"), hit("d", null)]);
    expect(sorted.map((h) => h.tile_id)).toEqual(["b", "d", "a", "c"]);
  });

  it("does not mutate the input", () => {
    const input = [hit("a", "Atacama"), hit("b", null)];
    newFirst(input);
    expect(input.map((h) => h.tile_id)).toEqual(["a", "b"]);
  });
});

describe("coords", () => {
  it("writes hemispheres, not signs", () => {
    expect(coords(-77.5, 162)).toBe("77.50°S 162.00°E");
    expect(coords(35.03, -111.02)).toBe("35.03°N 111.02°W");
  });
});
