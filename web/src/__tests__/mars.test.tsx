/** Mars pages on the static export (#41): the field guide, the guides index,
 * the portfolio and the traps page must speak about Mars, not the Moon. */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import type { MapPaneProps } from "../components/map/MapPane";
import * as api from "../lib/api";
import { mockTwins } from "../lib/mocks";

vi.mock("../components/map/LeafletMap", () => ({
  default: ({ markers }: MapPaneProps) => <div role="region" aria-label="map">{markers.length} markers</div>,
}));

const EARTH_ID = "earth_-24.08_-69.92";
const SRC_ID = "mars_7_51_183";

const trap = {
  src_body: "mars", src_tile_id: SRC_ID, src_lat: 18.4, src_lon: 77.7,
  earth_tile_id: "earth_+75.50_-40.00", earth_lat: 75.5, earth_lon: -40,
  visual_cos: 0.9, visual_pct: 0.998, visual_rank: 1, physics_rank: 4200, model_score_pct: 0.1,
  known_analog: null,
  breakers: [{ id: "ice", label: "Ice sheet, not rock", environment: true,
               reason: "97% permanent ice. This part of Mars is dry rock and dust" }],
};

const FILES: Record<string, unknown> = {
  "/data/sites.json": [
    { id: "haworth", body: "moon_polar", name: "Haworth", lat: -87.45, lon: -5.17, is_base_region: true },
    { id: "tycho", body: "moon", name: "Tycho crater", lat: -43.31, lon: -11.36 },
    { id: "jezero-crater", body: "mars", name: "Jezero crater", lat: 18.41, lon: 77.69,
      blurb: "Perseverance rover site: a river delta with carbonates." },
  ],
  "/data/tiles/mars.json": [{
    tile_id: SRC_ID, lat: 18.4, lon: 77.7, bbox: [77, 17.7, 78.4, 19.1], slope_med: 1.8,
    relief_km: 0.9, thermal_inertia: 310, albedo: 0.18, dust_index: 0.96, weh_pct: 4, hydrous_count: 12,
  }],
  "/data/analogs/jezero-crater.json": {
    src_tile: { tile_id: SRC_ID, lat: 18.4, lon: 77.7 },
    results: [{ tile_id: EARTH_ID, lat: -24.08, lon: -69.92, score: 1, visual_cos_scaled: 0.93,
                physical: 0.88, known_analog: null, model_score: 0.97, tile_url: "" }],
  },
  [`/data/twins/jezero-crater__${EARTH_ID}.json`]: mockTwins(SRC_ID, EARTH_ID),
  "/data/traps.json": {
    stats: [{ src_body: "mars", lookalikes_checked: 436000, traps: 130800, trap_rate: 0.3,
              by_reason: { vegetation: 90000, ice: 20000 } }],
    traps: [trap], by_site: { "jezero-crater": [trap] },
  },
  "/data/portfolio/jezero-crater.json": {
    site_id: "jezero-crater", site_name: "Jezero crater", body: "mars",
    src_tile: { tile_id: SRC_ID, lat: 18.4, lon: 77.7 }, polar: false,
    dimensions: [
      { id: "material", label: "Surface material", note: "", moon: "310 tiu (sand and crusted soil)",
        threshold: 0.6, earth_best: 0.9, earth_best_only: false, covered_by: "earth_a" },
      { id: "brightness", label: "Surface brightness", note: "", moon: "albedo 0.18",
        threshold: 0.6, earth_best: 0.9, earth_best_only: false, covered_by: "earth_a" },
    ],
    sites: [{ order: 1, tile_id: "earth_a", lat: -24.08, lon: -69.92, known_analog: null,
              covers: ["material", "brightness"], adds: ["material", "brightness"], scores: {} }],
    uncovered: [], best_single_site: { tile_id: "earth_a", covers: 2 }, candidates: 9000,
  },
};

function serve(files: Record<string, unknown>) {
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const body = files[String(url)];
    return Promise.resolve(body === undefined
      ? new Response("not found", { status: 404 })
      : new Response(JSON.stringify(body), { status: 200 }));
  });
}

const at = (path: string) =>
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

beforeEach(() => api._resetStaticCache());
afterEach(() => vi.restoreAllMocks());

describe("Mars pages", () => {
  it("Field guide: Mars facts from the tile, no lunar radar section", async () => {
    serve(FILES);
    at("/sites/jezero-crater");
    expect(await screen.findByRole("heading", { name: "Jezero crater" })).toBeInTheDocument();
    expect(screen.getByText(/Mars landing or exploration site/)).toBeInTheDocument();

    const fact = async (label: string) =>
      (await screen.findByText(label)).closest("div") as HTMLElement;
    expect(await fact("Thermal inertia")).toHaveTextContent("310");
    expect(await fact("Brightness (albedo)")).toHaveTextContent("0.18");
    expect(await fact("Water-equivalent hydrogen")).toHaveTextContent("4%");
    expect(await fact("Water-altered minerals")).toHaveTextContent("12");
    expect(await fact("Median slope")).toHaveTextContent(/1\.8°.*MOLA/);

    // Radar roughness is a Mini-RF measurement of the Moon; a Mars guide must not show it.
    expect(screen.queryByText("Radar roughness")).not.toBeInTheDocument();
    expect(screen.queryByText(/Mini-RF/)).not.toBeInTheDocument();
    // ...nor the polar illumination facts.
    expect(screen.queryByText("Permanent shadow")).not.toBeInTheDocument();
  });

  it("Field guide: the candidate's Mars field tests, portfolio wording and traps", async () => {
    serve(FILES);
    at("/sites/jezero-crater");
    expect(await screen.findByText("Life detection at low biomass")).toBeInTheDocument();
    expect(screen.getByText(/Holds on .*surface material/)).toBeInTheDocument();

    expect(await screen.findByText("Smallest set of Earth sites")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "On Mars" })).toBeInTheDocument();
    expect(screen.getByText(/ice only where the Mars site has ground ice/)).toBeInTheDocument();
    expect(screen.getByText("310 tiu (sand and crusted soil)")).toBeInTheDocument();

    expect(screen.getByText(/Lookalikes to avoid/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Mars tile at/ })).toBeInTheDocument();
  });

  it("Field guides index: Mars sites in their own group, not under the Moon", async () => {
    serve(FILES);
    at("/sites");
    const mars = (await screen.findByRole("heading", { name: "Mars landing and exploration sites" }))
      .closest("section") as HTMLElement;
    expect(within(mars).getByRole("link", { name: /Jezero crater/ })).toHaveAttribute("href", "/sites/jezero-crater");
    expect(within(mars).getByText(/1 traps/)).toBeInTheDocument();
    const moon = screen.getByRole("heading", { name: "Other Moon sites" }).closest("section") as HTMLElement;
    expect(within(moon).getByRole("link", { name: /Tycho/ })).toBeInTheDocument();
    expect(within(moon).queryByRole("link", { name: /Jezero/ })).not.toBeInTheDocument();
  });

  it("Traps: Mars has its own headline rate and can be filtered", async () => {
    serve(FILES);
    at("/traps");
    expect(await screen.findByRole("heading", { name: "Mars, 60°S–60°N" })).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Mars, 60°S–60°N" })).toBeInTheDocument();
    expect(screen.getByText(/This part of Mars is dry rock and dust/)).toBeInTheDocument();
  });
});
