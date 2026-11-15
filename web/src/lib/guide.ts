/** Data for the field-guide pages, assembled from the static export. */
import * as api from "./api";
import type {
  AnalogHit, AnalogsResponse, CloseStudyEntry, RadarSite, Site, TileCell, Trap, TwinsResponse,
} from "./types";

/** Nearest grid cell by great-circle angle. Grids are small (≤ ~5k cells). */
export function nearestCell(cells: TileCell[], lat: number, lon: number): TileCell | null {
  const r = Math.PI / 180;
  let best: TileCell | null = null;
  let bestD = Infinity;
  for (const c of cells) {
    const d = Math.acos(Math.min(1,
      Math.sin(lat * r) * Math.sin(c.lat * r) +
      Math.cos(lat * r) * Math.cos(c.lat * r) * Math.cos((lon - c.lon) * r)));
    if (d < bestD) {
      bestD = d;
      best = c;
    }
  }
  return best;
}

export interface GuideCandidate {
  hit: AnalogHit;
  card: TwinsResponse | null;
}

export interface Guide {
  site: Site;
  cell: TileCell | null;
  radar: RadarSite | null;
  candidates: GuideCandidate[];
  traps: Trap[];
  /** Close-study pairs (#19) for this site, if any. */
  closeStudy: CloseStudyEntry[];
}

async function staticJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(path);
    if (!res.ok || (res.headers.get("content-type") ?? "").includes("text/html")) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** Everything one field guide shows. `n` new candidates, each with its
 * exported report card where 03_export.py wrote one. */
export async function loadGuide(site: Site, n = 3): Promise<Guide> {
  const [cells, radar, traps, study, analogs] = await Promise.all([
    api.tiles(site.body),
    api.radar(),
    api.traps(),
    api.closeStudy(),
    staticJson<AnalogsResponse>(`/data/analogs/${site.id}.json`),
  ]);
  const fresh = (analogs?.results ?? []).filter((h) => h.known_analog === null).slice(0, n);
  const cards = await Promise.all(
    fresh.map((h) => staticJson<TwinsResponse>(`/data/twins/${site.id}__${h.tile_id}.json`)),
  );
  return {
    site,
    cell: nearestCell(cells, site.lat, site.lon),
    radar: radar?.[site.id] ?? null,
    candidates: fresh.map((hit, i) => ({ hit, card: cards[i] })),
    traps: traps?.by_site[site.id] ?? [],
    closeStudy: (study ?? []).filter((s) => s.site_id === site.id),
  };
}
