/** The client's two jobs: fall back to mocks with no API configured, and
 * surface the API's {"detail": ...} errors as readable messages. */
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../lib/api";
import { MOCK_SITES } from "../lib/mocks";

describe("mock mode (no VITE_API_BASE)", () => {
  it("reports itself as mock", () => {
    expect(api.apiMode()).toBe("mock");
    expect(api.isLive()).toBe(false);
  });

  it("serves search without any network call", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const out = await api.search({ body: "moon", query: "crater", k: 4 });
    expect(out.results).toHaveLength(4);
    expect(out.results[0].tile_id).toMatch(/^moon_/);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("returns analogs with the fields the UI renders, not the raw score alone", async () => {
    const out = await api.analogs({ src_body: "moon", lat: -89.5, lon: 0, k: 6 });
    expect(out.results).toHaveLength(6);
    for (const hit of out.results) {
      expect(hit.visual_cos_scaled).toBeGreaterThanOrEqual(0);
      expect(hit.visual_cos_scaled).toBeLessThanOrEqual(1);
      expect(hit.physical).toBeGreaterThanOrEqual(0);
    }
  });

  it("drops known analog sites when new_only is set", async () => {
    const out = await api.analogs({ src_body: "moon", lat: -89.5, lon: 0, k: 6, new_only: true });
    expect(out.results.length).toBeGreaterThan(0);
    expect(out.results.every((r) => r.known_analog === null)).toBe(true);
  });

  it("returns a report card whose rows all fit the contract", async () => {
    const card = await api.twins("moon_6_0_90", "earth_-77.50_+162.00");
    for (const row of card.breakdown) {
      expect(typeof row.dimension).toBe("string");
      expect(row.match === null || (row.match >= 0 && row.match <= 1)).toBe(true);
    }
  });
});

describe("static export is preferred when a site id is known", () => {
  beforeEach(() => vi.restoreAllMocks());

  const exportedAnalogs = {
    site_id: "tycho-crater",
    src_tile: { tile_id: "moon_6_53_60", lat: -43.31, lon: -11.36 },
    results: [{
      tile_id: "earth_+35.03_-111.02", lat: 35.03, lon: -111.02, score: 0.71,
      visual_cos_scaled: 0.88, physical: 0.6, known_analog: null, tile_url: "",
    }],
  };

  it("reads analogs from the export instead of calling the API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      Promise.resolve(
        String(url).endsWith("/data/analogs/tycho-crater.json")
          ? (new Response(JSON.stringify(exportedAnalogs), { status: 200 }) as Response)
          : (new Response("not found", { status: 404 }) as Response),
      ),
    );
    const out = await api.analogs(
      { src_body: "moon", lat: -43.31, lon: -11.36 }, "tycho-crater");
    expect(out.src_tile.tile_id).toBe("moon_6_53_60");
    expect(fetchMock).toHaveBeenCalledWith("/data/analogs/tycho-crater.json");
  });

  it("falls back when that site has not been exported", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not found", { status: 404 }) as Response,
    );
    // A Moon base region is deliberately not exported: it is outside the index.
    const out = await api.analogs({ src_body: "moon", lat: -89.67, lon: 129.78 }, "shackleton-rim");
    expect(out.results.length).toBeGreaterThan(0);   // mock fallback, app still runs
  });

  it("reads the report card from the export, keyed by site and tile", async () => {
    const card = { site_id: "tycho-crater", moon: {}, earth: {}, climate: null, breakdown: [] };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(card), { status: 200 }) as Response,
    );
    const out = await api.twins("moon_6_53_60", "earth_+35.03_-111.02", "tycho-crater");
    expect(out.climate).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/data/twins/tycho-crater__earth_+35.03_-111.02.json");
  });
});

describe("sites()", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("falls back to mock sites when the static export is not there yet", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not found", { status: 404 }) as Response,
    );
    await expect(api.sites()).resolves.toEqual(MOCK_SITES);
  });

  it("falls back when fetch itself fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));
    await expect(api.sites()).resolves.toEqual(MOCK_SITES);
  });

  it("prefers the static export when it exists", async () => {
    const exported = [{ id: "x", body: "moon" as const, name: "Exported site", lat: 1, lon: 2 }];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(exported), { status: 200 }) as Response,
    );
    await expect(api.sites()).resolves.toEqual(exported);
  });
});
