/** The pages that read the static export: traps, discoveries, validation,
 * field guides, data. Each must render real numbers when the file exists and
 * say so plainly when it does not. */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import type { MapPaneProps } from "../components/map/MapPane";
import * as api from "../lib/api";
import { cprVerdict } from "../routes/CloseStudy";
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
  // #16: crater retrieval and known-analog ranking from scripts/05_validate.py
  crater_retrieval: {
    note: "Robbins (2019) crater labels", similarity: "w_shade=0.6", tiles: 5376,
    density_class: {
      definition: "tercile of the count of craters >= 1 km",
      overall: { n_queries: 5376, random_baseline: 0.3333, p_at_10: 0.5913 },
      by_class: {
        smooth: { n_queries: 1792, random_baseline: 0.3333, p_at_10: 0.632 },
        middling: { n_queries: 1783, random_baseline: 0.3317, p_at_10: 0.447 },
        "heavily cratered": { n_queries: 1801, random_baseline: 0.335, p_at_10: 0.695 },
      },
    },
    big_crater: { definition: "a crater >= 40 km", n_queries: 1864, random_baseline: 0.3467, p_at_10: 0.478 },
  },
  known_analog_ranking: {
    note: "ranked from lunar sites sharing its role", earth_tiles_ranked: 11699,
    top_pct_meaning: "% of Earth tiles scoring higher",
    summary: { n: 13, in_top_1pct: 4, in_top_5pct: 7, in_top_10pct: 9, in_top_25pct: 11, median_top_pct: 4.06 },
    sites: [
      { site: "Craters of the Moon, Idaho, USA", roles: ["volcanic"], tested_roles: ["volcanic"],
        moon_target: true, earth_tiles: 2,
        shipped: { rank: 4, top_pct: 0.03, role: "volcanic", query: "Gruithuisen Domes", pushed_down: false },
        image_only: { rank: 33, top_pct: 0.28, role: "volcanic", query: "Gruithuisen Domes", pushed_down: false } },
      { site: "McMurdo Dry Valleys, Antarctica", roles: ["polar", "arid"], tested_roles: ["polar"],
        moon_target: false, earth_tiles: 1,
        shipped: { rank: 7533, top_pct: 64.38, role: "polar", query: "Shackleton rim", pushed_down: true } },
    ],
    skipped_sites: { "Ries Crater, Germany": "process analog" },
  },
  polar_analog_ranking: {
    note: "#32: the polar dimensions report but do not rank", earth_tiles_ranked: 11699,
    tile_resolution_km: 85,
    query_sites_sharing_a_tile: { moonsp_5_6: ["Haworth", "Malapert Massif"] },
    by_query_site: {
      "Shackleton rim (classic base concept)": {
        query_tile: "moonsp_5_5",
        analogs: {
          "Atacama Desert (Yungay), Chile": { rank: 22, top_pct: 0.18, pushed_down: false,
                                              roles: ["arid"], target: ["mars", "moon"] },
          "McMurdo Dry Valleys, Antarctica": { rank: 7533, top_pct: 64.38, pushed_down: true,
                                               roles: ["polar", "arid"], target: ["mars"] },
        },
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

const STUDY = {
  id: "haworth-puna", site_id: "haworth", site_name: "Haworth", site_body: "moon_polar",
  earth_tile_id: "earth_-77.50_+162.00", earth_lat: -77.5, earth_lon: 162,
  twin: "/data/twins/haworth__earth_-77.50_+162.00.json", model_score: 0.99,
  headline: "A bare plateau", earth_name: "Somewhere high", why_picked: "#1 for Haworth.",
  rank_among_new: 1, nearest_known: { name: "Atacama", km: 291 }, box: { half_km: 15 },
  radar: {
    moon: { cpr_median: 0.44, cpr_p90: 0.8, coverage: 0.79, n_pixels: 100, source: "LRO Mini-RF",
            measure: "cpr", box_half_km: 15 },
    earth_cpr: null,
    earth_s1: { cpr_median: 0.152, cpr_p90: 0.3, coverage: 0.63, n_pixels: 100, source: "Sentinel-1",
                measure: "s1_vh_vv", box_half_km: 15, dates: "2025-03-01/2025-05-31" },
  },
  earth_slope_30m: { slope_med: 10.77, slope_p90: 26.25, n_pixels: 1000, source: "Copernicus GLO-30" },
  picture: { url: "/data/close_study/x.jpg", date: "2025-04-27", source: "Sentinel-2", cloud_pct: 0.1 },
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

describe("close study (#19)", () => {
  const files = { ...FILES, "/data/close_study.json": [STUDY] };

  it("Close-study page: radar on both bodies, labelled measures, slopes, full card", async () => {
    serve(files);
    at("/close-study/haworth-puna");
    expect(await screen.findByRole("heading", { name: "Haworth ↔ Somewhere high" })).toBeInTheDocument();
    expect(screen.getByText(/CPR 0.44/)).toBeInTheDocument();
    expect(screen.getByText(/VH\/VV 0.15/)).toBeInTheDocument();
    expect(screen.getByText(/free RCM compact-pol data covers Canada only/)).toBeInTheDocument();
    expect(screen.getByText("10.8°")).toBeInTheDocument();
    expect(screen.getByText(/291 km/)).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Report card" })).toBeInTheDocument();
  });

  it("Close-study page: unknown id says so", async () => {
    serve(files);
    at("/close-study/nope");
    expect(await screen.findByText(/No close study called/)).toBeInTheDocument();
  });

  it("Discoveries and the field guide link to the close study", async () => {
    serve(files);
    at("/discoveries");
    expect(await screen.findByRole("link", { name: /Somewhere high/ }))
      .toHaveAttribute("href", "/close-study/haworth-puna");
  });

  it("Field guide shows the Earth radar number from the close study", async () => {
    serve(files);
    at("/sites/haworth");
    expect(await screen.findByText(/Somewhere high \(close study\)/)).toBeInTheDocument();
    expect(screen.getByText(/Sentinel-1 indicator, not CPR/)).toBeInTheDocument();
  });
});

describe("cprVerdict", () => {
  it("compares CPR with CPR only, in plain words", () => {
    expect(cprVerdict(0.46, 0.536)).toMatch(/About as rough/);
    expect(cprVerdict(0.4, 0.8)).toMatch(/Rougher/);
    expect(cprVerdict(0.6, 0.2)).toMatch(/Smoother/);
    expect(cprVerdict(0.5, null)).toBeNull();
  });
});

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

  it("Methodology: crater retrieval beats chance, and the weak cases are stated", async () => {
    serve(FILES);
    at("/methodology");
    expect(await screen.findByRole("row", { name: /Heavily cratered.*69.5%/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Smooth \(mare\).*63.2%/ })).toBeInTheDocument();
    // the middling third is barely better than chance; the page must not bury it
    expect(screen.getByRole("row", { name: /Middling.*44.7%/ })).toBeInTheDocument();
    expect(screen.getByText(/47.8% versus 34.7% chance/)).toBeInTheDocument();
  });

  it("Methodology: known analogs ranked for their role, Mars ones not scored", async () => {
    serve(FILES);
    at("/methodology");
    expect(await screen.findByText(/top 4.06%/, { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Craters of the Moon.*top 0.03%/ })).toBeInTheDocument();
    expect(screen.getByText(/ranked for information only \(1\)/)).toBeInTheDocument();
  });

  it("Methodology: says which dimensions rank, and that McMurdo is pushed down (#32)", async () => {
    serve(FILES);
    at("/methodology");
    expect(await screen.findByText(/none of\s+them enter the ranking/)).toBeInTheDocument();
    // McMurdo appears in the Mars list too, so scope to the Artemis region's block
    const region = screen.getByRole("heading", { name: "Shackleton rim (classic base concept)" });
    expect(within(region.parentElement!).getByRole("row", { name: /McMurdo Dry Valleys.*top 64.38%/ }))
      .toBeInTheDocument();
    expect(screen.getByText(/Haworth and Malapert Massif share tile moonsp_5_6/))
      .toBeInTheDocument();
  });

  it("Methodology: the #16 sections say so when validation.json lacks them", async () => {
    serve({ ...FILES, "/data/validation.json": { analog_model: VALIDATION.analog_model } });
    at("/methodology");
    expect(await screen.findByText(/top 9.5%/, { selector: "strong" })).toBeInTheDocument();
    expect(screen.getAllByText(/05_validate.py/).length).toBe(3); // #16 x2 + the Mars section (#40)
    // with no polar key the page still states what ranks and what only reports
    expect(screen.getByText(/do not affect the ranking/)).toBeInTheDocument();
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
    expect(screen.getByText(/Not in the close study/)).toBeInTheDocument();
    expect(screen.getByText(/Lookalikes to avoid/)).toBeInTheDocument();
  });

  it("Field guide: portfolio of Earth sites, with Earth's limits said plainly", async () => {
    const dim = (id: string, label: string, covered_by: string | null, earth_best_only = false) =>
      ({ id, label, note: "", moon: "-", threshold: 0.6, earth_best: 0.64, earth_best_only, covered_by });
    serve({ ...FILES, "/data/portfolio/haworth.json": {
      site_id: "haworth", site_name: "Haworth", body: "moon_polar",
      src_tile: { tile_id: "moonsp_2_3", lat: -86, lon: -1.7 }, polar: true,
      dimensions: [dim("dryness", "Dryness", "earth_a"), dim("sun_angle", "Low sun angle", "earth_b", true),
                   dim("access", "Access", "earth_a")],
      sites: [
        { order: 1, tile_id: "earth_a", lat: -26.5, lon: -68.82, known_analog: null,
          covers: ["dryness", "access"], adds: ["dryness", "access"], scores: {} },
        { order: 2, tile_id: "earth_b", lat: 81.5, lon: -88.67, known_analog: "Haughton Crater",
          covers: ["sun_angle"], adds: ["sun_angle"], scores: {} },
      ],
      uncovered: [], best_single_site: { tile_id: "earth_a", covers: 2 }, candidates: 100,
    } });
    at("/sites/haworth");
    expect(await screen.findByText("Smallest set of Earth sites")).toBeInTheDocument();
    expect(screen.getByText(/the best single site covers only 2/)).toBeInTheDocument();
    expect(screen.getByText("Near Haughton Crater")).toBeInTheDocument();
    expect(screen.getByText(/closest Earth gets \(64%\)/)).toBeInTheDocument();
    expect(screen.getByText(/Practical, not likeness/)).toBeInTheDocument();
  });

  it("Field guide: no portfolio section when it is not exported", async () => {
    serve(FILES);
    at("/sites/haworth");
    expect(await screen.findByRole("heading", { name: "Haworth" })).toBeInTheDocument();
    expect(screen.queryByText("Smallest set of Earth sites")).not.toBeInTheDocument();
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
