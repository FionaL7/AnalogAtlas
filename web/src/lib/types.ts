/**
 * The API and static-export contract, mirrored from docs/ARCHITECTURE.md §4.2-4.3.
 * Python is the single source of truth for every score; the browser only renders.
 */
export type Body = "moon" | "earth";
export type Layer = "img" | "shade";

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

export interface TwinsResponse {
  moon: Record<string, string | number | null>;
  earth: Record<string, string | number | null>;
  climate: Record<string, number | null> | null;
  breakdown: BreakdownRow[];
}

/** Static export: tiles/{body}.json (§4.2). One cell of the map grid. */
export interface TileCell {
  tile_id: string;
  lat: number;
  lon: number;
  /** [lon_min, lat_min, lon_max, lat_max] */
  bbox: [number, number, number, number];
  slope_med: number | null;
  relief_km: number | null;
  known_analog?: string | null;
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
}
