/**
 * Display rules. Scoring itself is Python's job (§4.4) — this file only decides
 * how numbers are worded, and it enforces two rules the challenge rides on:
 *
 *  1. The raw `score` is a ranking value, not a similarity. It is never shown.
 *  2. Rows Earth cannot reproduce are their own group, not a low score, so the
 *     report card says where the analogy breaks down instead of burying it.
 */
import type { AnalogHit, BreakdownRow } from "./types";

export const MATCH_HOLDS = 0.6;

export type Verdict = "holds" | "partial" | "breaks" | "cannot-reproduce" | "no-equivalent";

export type Group = "holds" | "breaks" | "cannot-reproduce" | "no-equivalent";

/** 0-1 -> "91%". Null/undefined -> an em dash, never "0%". */
export function percent(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

export function verdict(match: number | null): Verdict {
  if (match === null) return "no-equivalent";
  if (match === 0) return "cannot-reproduce";
  if (match >= MATCH_HOLDS) return "holds";
  if (match >= 0.3) return "partial";
  return "breaks";
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  holds: "Holds",
  partial: "Partly holds",
  breaks: "Breaks down",
  "cannot-reproduce": "Earth cannot reproduce this",
  "no-equivalent": "No Earth equivalent measured",
};

/**
 * Report-card grouping. Python marks each row's `kind` (issue #20):
 * `earth_limit` rows are the fixed Earth's-limits rows from analog.breakdown(),
 * and `no_equivalent` means nothing comparable was measured (e.g. Diviner rock
 * abundance). Rows without `kind` (older API) fall back to reading the match.
 */
export function rowGroup(row: BreakdownRow): Group {
  if (row.kind === "earth_limit") return "cannot-reproduce";
  if (row.kind === "no_equivalent") return "no-equivalent";
  const v = verdict(row.match);
  if (row.kind === "compare" && v === "cannot-reproduce") return "breaks"; // a real 0% match
  return v === "partial" || v === "breaks" ? "breaks" : v;
}

export function groupBreakdown(rows: BreakdownRow[]): Record<Group, BreakdownRow[]> {
  const out: Record<Group, BreakdownRow[]> = {
    holds: [], breaks: [], "cannot-reproduce": [], "no-equivalent": [],
  };
  for (const row of rows) out[rowGroup(row)].push(row);
  return out;
}

export const GROUP_LABEL: Record<Group, string> = {
  holds: "Where the analogy holds",
  breaks: "Where it breaks down",
  "cannot-reproduce": "What Earth cannot reproduce",
  "no-equivalent": "Not comparable",
};

/** Lead with candidates that are not already-known analog sites. */
export function newFirst(hits: AnalogHit[]): AnalogHit[] {
  return [...hits].sort((a, b) =>
    Number(a.known_analog !== null) - Number(b.known_analog !== null));
}

export function coords(lat: number, lon: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(2)}°${ns} ${Math.abs(lon).toFixed(2)}°${ew}`;
}

/** Modelled values must never read as measurements (§6). */
export const MODELLED_NOTE = "modelled, not measured";
export const MODELLED_COLUMNS = ["t_max_k", "t_min_k"];
export const isModelled = (column: string) => MODELLED_COLUMNS.includes(column);
