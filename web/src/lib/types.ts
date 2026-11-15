/**
 * The API and static-export contract, mirrored from docs/ARCHITECTURE.md §4.2-4.3.
 * Python is the single source of truth for every score; the browser only renders.
 */
/** `moon_polar` is the lunar south pole on its own polar stereographic grid
 *  (#26). It is a separate body, not a subset of `moon`: an equirectangular
 *  tile at 85°S is 6 km wide and 85 km tall, so the pole cannot be drawn or
 *  indexed on the same grid. */
export type Body = "moon" | "moon_polar" | "earth";
export type Layer = "img" | "shade";

/** Bodies drawn in a polar stereographic pane rather than in lat/lon. */
export const POLAR_BODIES: readonly Body[] = ["moon_polar"];

export const isPolar = (body: Body): boolean => POLAR_BODIES.includes(body);

export interface SearchRequest {
  body: Body;
  query?: string;
  image_b64?: string;
  k?: number;
  w_shade?: number;
}

export interface SearchHit {
  tile_id: string;
  lat: number;
  lon: number;
  /** Ranking value only — never render it as a similarity. */
  score: number;
  known_analog: string | null;
  tile_url: string;
}

export interface SearchResponse {
  results: SearchHit[];
}

export interface AnalogsRequest {
  src_body: Body;
  lat: number;
  lon: number;
  k?: number;
  w_phys?: number;
  new_only?: boolean;
}

export interface AnalogHit extends SearchHit {
  /** 0-1 percentile of visual similarity. This is what the UI shows. */
  visual_cos_scaled: number;
  /** 0-1 closeness of slope and relief. */
  physical: number;
  /** #29 analog model: 0-1 percentile among Earth tiles. Null/absent until trained. */
  model_score?: number | null;
}

export interface AnalogsResponse {
  src_tile: { tile_id: string; lat: number; lon: number };
  results: AnalogHit[];
}

/** One row of the report card: a dimension, and whether the analogy holds. */
export interface BreakdownRow {
  dimension: string;
  moon: string | number;
  earth: string | number;
  /** 0-1, or null when Earth has no equivalent at all. */
  match: number | null;
  note: string;
  /** How to group the row. `earth_limit` = Earth cannot reproduce this (always match 0). */
  kind?: "compare" | "no_equivalent" | "earth_limit";
}

/** One suggestion from analogatlas/fieldtest.py (C6). */
export interface FieldTest {
  title: string;
  /** The exploration risk this test reduces. */
  risk: string;
  detail: string;
  /** Report-card dimensions this suggestion rests on. */
  based_on: string[];
  /** The weakest match among `based_on`, 0-1. */
  strength: number;
}

export interface FieldTests {
  tests: FieldTest[];
  avoid: { dimension: string; reason: string }[];
}

export interface TwinsResponse {
  moon: Record<string, string | number | null>;
  earth: Record<string, string | number | null>;
  climate: Record<string, number | null> | null;
  breakdown: BreakdownRow[];
  /** What to test at the Earth site. Absent from older exports. */
  field_tests?: FieldTests | null;
  model_score?: number | null;
}

/** Static export: tiles/{body}.json (§4.2). One cell of the map grid. */
export interface TileCell {
  tile_id: string;
  lat: number;
  lon: number;
  /** [lon_min, lat_min, lon_max, lat_max]. Meaningless for a polar cell that
   *  contains the pole itself — use `xy` for those. */
  bbox: [number, number, number, number];
  slope_med: number | null;
  relief_km: number | null;
  known_analog?: string | null;
  /** moon_polar only: [x_m, y_m, size_m] in south polar stereographic metres. */
  xy?: [number, number, number];
  /** moon_polar only: the dimensions a base is actually sited on. */
  psr_frac?: number | null;
  avg_illum?: number | null;
  illum_max?: number | null;
  earth_vis?: number | null;
}

/** Static export: sites.json (§4.2). */
export interface Site {
  id: string;
  body: Body;
  name: string;
  lat: number;
  lon: number;
  blurb?: string;
  /** Artemis candidate base regions — the ones that answer "permanent Moon base". */
  is_base_region?: boolean;
  /** false: outside every index, so it has no analogs (never clamped). */
  in_index?: boolean;
  /** A well-studied Earth analog: a reference point, not a search target. */
  is_known_analog?: boolean;
}

/** Static export: traps.json (#30). */
export interface TrapBreaker {
  id: "ice" | "vegetation" | "water" | "wet_climate" | "slope" | "relief" | string;
  label: string;
  /** true: about what the ground is; false: about its shape. */
  environment: boolean;
  reason: string;
}

export interface Trap {
  src_body: Body;
  src_tile_id: string;
  src_lat: number;
  src_lon: number;
  earth_tile_id: string;
  earth_lat: number;
  earth_lon: number;
  visual_cos: number;
  /** 0-1 percentile of visual similarity among all Earth tiles. */
  visual_pct: number;
  /** Rank by image similarity alone (1 = the top lookalike). */
  visual_rank: number;
  /** Rank by cross_body (image + slope/relief). */
  physics_rank: number;
  /** #29 model, 0-1. Null without a trained model. */
  model_score_pct: number | null;
  known_analog: string | null;
  breakers: TrapBreaker[];
}

export interface TrapStats {
  src_body: Body;
  lookalikes_checked: number;
  traps: number;
  trap_rate: number;
  by_reason: Record<string, number>;
}

export interface TrapsFile {
  stats: TrapStats[];
  traps: Trap[];
  by_site: Record<string, Trap[]>;
}

/** Static export: candidates.json (#29), one list per target. */
export interface Candidate {
  tile_id: string;
  lat: number;
  lon: number;
  /** 0-100 percentile of the model score. */
  score_pct: number;
  why: string[];
  slope_med?: number | null;
  barren_frac?: number | null;
  precip_mm?: number | null;
  access_min?: number | null;
}

export type CandidatesFile = Partial<Record<"moon" | "mars" | "all", Candidate[]>>;

/** Static export: radar.json (#17), keyed by site id. */
export interface RadarSite {
  lat: number;
  lon: number;
  box_half_km: number;
  cpr_median: number;
  cpr_p90: number;
  coverage: number;
  n_pixels: number;
  source: string;
}

export type RadarFile = Record<string, RadarSite>;

/** Static export: validation.json, key analog_model (#29). */
export interface MethodSummary {
  median_top_pct: number;
  mean_top_pct: number;
  in_top_5pct: number;
  in_top_10pct: number;
  n: number;
}

export interface ModelTarget {
  sites_used: string[];
  summary: Record<string, MethodSummary>;
  per_site: { site: string; top_pct: number }[];
  weights?: { feature: string; weight: number }[];
}

export interface ValidationFile {
  analog_model?: {
    method: string;
    note: string;
    random_baseline_top_pct: number;
    targets: Partial<Record<"all" | "moon" | "mars", ModelTarget>>;
    skipped_sites?: Record<string, string>;
  };
}

/** Static export: portfolio/{site_id}.json (#31). The fewest Earth sites
 * that together cover every dimension of one lunar target. */
export interface PortfolioDimension {
  id: string;
  label: string;
  note: string;
  /** What this dimension is on the Moon side, in words ("-" if none). */
  moon: string;
  /** Score (0-1) a site needs to cover it. */
  threshold: number;
  /** Best score any eligible Earth tile reaches. */
  earth_best: number | null;
  /** No Earth site reaches the usual bar; the best Earth can do counts. */
  earth_best_only: boolean;
  /** tile_id of the site that first covered it; null if uncovered. */
  covered_by: string | null;
}

export interface PortfolioSite {
  order: number;
  tile_id: string;
  lat: number;
  lon: number;
  known_analog: string | null;
  /** Every dimension this site covers. */
  covers: string[];
  /** The ones it was the first to cover. */
  adds: string[];
  scores: Record<string, number>;
}

export interface PortfolioFile {
  site_id: string;
  site_name: string;
  body: Body;
  src_tile: { tile_id: string; lat: number; lon: number };
  polar: boolean;
  dimensions: PortfolioDimension[];
  sites: PortfolioSite[];
  uncovered: string[];
  best_single_site: { tile_id: string; covers: number } | null;
  candidates: number;
}
