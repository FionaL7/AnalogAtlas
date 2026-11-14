/**
 * The one place that talks to the outside world.
 *
 * With no VITE_API_BASE set, every call is served from src/lib/mocks.ts, so
 * `npm run dev` works with no backend at all. Point VITE_API_BASE at the
 * FastAPI service (#13) and the same calls go live — nothing else changes.
 */
import { MOCK_SITES, mockAnalogs, mockSearch, mockTwins } from "./mocks";
import type {
  AnalogsRequest,
  AnalogsResponse,
  Body,
  SearchRequest,
  SearchResponse,
  Site,
  TileCell,
  TwinsResponse,
} from "./types";

const BASE: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export const isLive = () => BASE !== "";
export const apiMode = (): "live" | "mock" => (isLive() ? "live" : "mock");

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    // The API answers with {"detail": "..."} on every error (§4.3).
    const detail = await res.json().then((b) => b?.detail).catch(() => null);
    throw new ApiError(res.status, detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function search(req: SearchRequest): Promise<SearchResponse> {
  if (!isLive()) return Promise.resolve(mockSearch(req));
  return request<SearchResponse>("/search", { method: "POST", body: JSON.stringify(req) });
}

/**
 * The static export (§4.2) is tried first wherever a `siteId` is known, so the
 * demo path keeps working with the API stopped — which is the whole point of
 * precomputing it. Missing file just means "not exported", not an error.
 */
async function fromStatic<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(path);
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function analogs(req: AnalogsRequest, siteId?: string): Promise<AnalogsResponse> {
  if (siteId) {
    const exported = await fromStatic<AnalogsResponse>(`/data/analogs/${siteId}.json`);
    if (exported) return exported;
  }
  if (!isLive()) return mockAnalogs(req);
  return request<AnalogsResponse>("/analogs", { method: "POST", body: JSON.stringify(req) });
}

export async function twins(
  srcTileId: string,
  earthTileId: string,
  siteId?: string,
): Promise<TwinsResponse> {
  if (siteId) {
    const exported = await fromStatic<TwinsResponse>(
      `/data/twins/${siteId}__${earthTileId}.json`,
    );
    if (exported) return exported;
  }
  if (!isLive()) return mockTwins(srcTileId, earthTileId);
  const q = new URLSearchParams({ src_tile_id: srcTileId, earth_tile_id: earthTileId });
  return request<TwinsResponse>(`/twins?${q}`);
}

/**
 * The full tile grid for one body, for the map's background layer. Static
 * export only (03_export.py); until it has run there is no grid, just results.
 */
export async function tiles(body: Body): Promise<TileCell[]> {
  return (await fromStatic<TileCell[]>(`/data/tiles/${body}.json`)) ?? [];
}

/**
 * Sites come from the static export, not the API — the demo path must work with
 * the service down (§4.2). Falls back to mocks until 03_export.py (#14) runs.
 */
export async function sites(): Promise<Site[]> {
  try {
    const res = await fetch("/data/sites.json");
    if (!res.ok) throw new Error(String(res.status));
    return (await res.json()) as Site[];
  } catch {
    return MOCK_SITES;
  }
}
