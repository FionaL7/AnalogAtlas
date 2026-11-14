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
