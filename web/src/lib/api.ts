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
  SearchRequest,
  SearchResponse,
  Site,
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

export function analogs(req: AnalogsRequest): Promise<AnalogsResponse> {
  if (!isLive()) return Promise.resolve(mockAnalogs(req));
  return request<AnalogsResponse>("/analogs", { method: "POST", body: JSON.stringify(req) });
}

export function twins(srcTileId: string, earthTileId: string): Promise<TwinsResponse> {
  if (!isLive()) return Promise.resolve(mockTwins(srcTileId, earthTileId));
  const q = new URLSearchParams({ src_tile_id: srcTileId, earth_tile_id: earthTileId });
  return request<TwinsResponse>(`/twins?${q}`);
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
