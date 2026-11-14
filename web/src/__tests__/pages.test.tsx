/** The pages that read the static export: traps, discoveries, validation,
 * field guides, data. Each must render real numbers when the file exists and
 * say so plainly when it does not. */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import type { MapPaneProps } from "../components/map/MapPane";
import * as api from "../lib/api";
import type { TrapsFile } from "../lib/types";

vi.mock("../components/map/LeafletMap", () => ({
  default: ({ markers }: MapPaneProps) => <div role="region" aria-label="map">{markers.length} markers</div>,
}));

const trap = {
  src_body: "moon_polar", src_tile_id: "moonsp_2_3", src_lat: -86, src_lon: -1.7,
  earth_tile_id: "earth_+75.50_-40.00", earth_lat: 75.5, earth_lon: -40,
  visual_cos: 0.9, visual_pct: 0.998, visual_rank: 1, physics_rank: 42, model_score_pct: 0.12,
  known_analog: null,
  breakers: [{ id: "ice", label: "Ice sheet, not rock", environment: true, reason: "97% permanent ice." }],
};

const TRAPS: TrapsFile = {
  stats: [{ src_body: "moon_polar", lookalikes_checked: 1780, traps: 1728, trap_rate: 0.9708,
            by_reason: { ice: 193, slope: 1514 } }],
  traps: [trap as TrapsFile["traps"][number]],
  by_site: { haworth: [trap as TrapsFile["traps"][number]] },
};

const SITES = [{ id: "haworth", body: "moon_polar", name: "Haworth", lat: -87.45, lon: -5.17,
                 is_base_region: true, in_index: true }];

const VALIDATION = {
  analog_model: {
    method: "PU logistic regression", note: "slightly optimistic", random_baseline_top_pct: 50,
    targets: {
      all: {
        sites_used: ["A", "B"],
        summary: {
          "Our model (shape + physics + environment)": { median_top_pct: 9.5, mean_top_pct: 12.1, in_top_5pct: 10, in_top_10pct: 17, n: 32 },
          "Image similarity only (no learning)": { median_top_pct: 22.5, mean_top_pct: 36, in_top_5pct: 4, in_top_10pct: 9, n: 32 },
        },
        per_site: [{ site: "Atacama", top_pct: 0 }],
        weights: [{ feature: "terrain shape (CLIP)", weight: 6.8 }],
      },
    },
  },
};

const ANALOGS = {
  site_id: "haworth", src_tile: { tile_id: "moonsp_2_3", lat: -86, lon: -1.7 },
  results: [{ tile_id: "earth_-77.50_+162.00", lat: -77.5, lon: 162, score: 1, visual_cos_scaled: 0.95,
              physical: 0.8, known_analog: null, model_score: 0.7, tile_url: "" }],
};

const CARD = {
  moon: { tile_id: "moonsp_2_3", lat: -86, lon: -1.7, x_m: 1, y_m: 2, size_m: 85000 },
  earth: { tile_id: "earth_-77.50_+162.00", lat: -77.5, lon: 162 },
  climate: null,
  breakdown: [{ dimension: "Median slope", moon: "4°", earth: "4°", match: 0.9, note: "", kind: "compare" }],
  field_tests: { tests: [{ title: "Surviving long darkness", risk: "Losing power", detail: "Polar night.",
                           based_on: ["Median slope"], strength: 0.9 }], avoid: [] },
};

const FILES: Record<string, unknown> = {
  "/data/traps.json": TRAPS,
  "/data/sites.json": SITES,
  "/data/validation.json": VALIDATION,
  "/data/radar.json": { haworth: { lat: -87.45, lon: -5.17, box_half_km: 15, cpr_median: 0.4989,
                                   cpr_p90: 0.87, coverage: 1, n_pixels: 23529, source: "LRO Mini-RF" } },
  "/data/candidates.json": { moon: [{ tile_id: "earth_-26.50_-67.70", lat: -26.5, lon: -67.7,
                                      score_pct: 100, why: ["low greenness"], access_min: 350 }] },
  "/data/analogs/haworth.json": ANALOGS,
  "/data/twins/haworth__earth_-77.50_+162.00.json": CARD,
  "/data/tiles/moon_polar.json": [{ tile_id: "moonsp_2_3", lat: -86, lon: -1.7, bbox: [0, 0, 0, 0],
                                    slope_med: 4.2, relief_km: 3.1, xy: [1, 2, 85000],
                                    psr_frac: 0.12, avg_illum: 0.3, illum_max: 0.88, earth_vis: 0.6 }],
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

describe("pages from the static export", () => {
  it("Traps: headline rate, reasons, and each trap's reason", async () => {
    serve(FILES);
    at("/traps");
    expect(await screen.findByText("97%")).toBeInTheDocument();
    expect(screen.getByText(/1,728 of/)).toBeInTheDocument();
    expect(screen.getByText("97% permanent ice.")).toBeInTheDocument();
    expect(screen.getByText("rank 42")).toBeInTheDocument();
  });

  it("Traps: says so when the export is missing", async () => {
    serve({});
    at("/traps");
    expect(await screen.findByText(/not exported yet/)).toBeInTheDocument();
  });

  it("Methodology: validation from validation.json, ours highlighted", async () => {
    serve(FILES);
    at("/methodology");
    expect(await screen.findByText(/top 9.5%/, { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Image similarity only.*top 22.5%/ })).toBeInTheDocument();
    expect(screen.getByText("terrain shape (CLIP)")).toBeInTheDocument();
    expect(screen.getByText(/What the numbers are not/)).toBeInTheDocument();
  });

  it("Discoveries: candidates with reasons and a link into the Atlas", async () => {
    serve(FILES);
    at("/discoveries");
    expect(await screen.findByText("Why: low greenness")).toBeInTheDocument();
    expect(screen.getByText("6 h")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Find the lunar terrain/ }))
      .toHaveAttribute("href", "/?src=earth:-26.500,-67.700");
  });

  it("Field guide: polar facts, Mini-RF radar, a candidate's field tests, traps", async () => {
    serve(FILES);
    at("/sites/haworth");
    expect(await screen.findByRole("heading", { name: "Haworth" })).toBeInTheDocument();
    expect(await screen.findByText(/CPR 0.50/)).toBeInTheDocument();
    expect(screen.getByText("88%")).toBeInTheDocument();       // best-lit point
    expect(await screen.findByText("Surviving long darkness")).toBeInTheDocument();
    expect(screen.getByText(/Pending the close study/)).toBeInTheDocument();
    expect(screen.getByText(/Lookalikes to avoid/)).toBeInTheDocument();
  });

  it("Field guides index links to each site", async () => {
    serve(FILES);
    const user = userEvent.setup();
    at("/sites");
    await user.click(await screen.findByRole("link", { name: /Haworth/ }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Haworth" })).toBeInTheDocument());
  });

  it("Data page carries the AI-use declaration", async () => {
    serve({});
    at("/data");
    expect(screen.getByRole("heading", { name: "Use of AI tools" })).toBeInTheDocument();
    expect(screen.getByText("Mini-RF global CPR mosaic")).toBeInTheDocument();
  });
});
