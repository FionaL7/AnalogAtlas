/**
 * The explorer. Three ways in, one way out:
 *   pick a preset site | click anywhere on a map | search by text or picture
 *     -> ranked analogs on the other body -> report card.
 *
 * Navigation state lives in the URL (?site= or ?src=, &tile=, &new=, &w=) so
 * any view can be shared or linked from the slides (§6). Search results are
 * transient and stay in component state.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { TrapCard } from "../components/TrapCard";
import { MapPane, type MapMarker } from "../components/map/MapPane";
import { AnalogList } from "../components/panels/AnalogList";
import { ReportCard } from "../components/panels/ReportCard";
import { SearchBox, type SearchInput } from "../components/panels/SearchBox";
import { SearchResults } from "../components/panels/SearchResults";
import * as api from "../lib/api";
import { coords } from "../lib/format";
import {
  BODY_NAME, SOURCE_BODIES, type AnalogHit, type AnalogsResponse, type Body, type SearchHit,
  type Site, type SourceBody, type TileCell, type Trap, type TwinsResponse,
} from "../lib/types";

const DEFAULT_W_PHYS = 0.3;

/** Where each index has data, so a click outside it is refused, not clamped. */
const IN_INDEX: Record<Body, (lat: number) => boolean> = {
  moon: (lat) => Math.abs(lat) <= 60,
  moon_polar: (lat) => lat <= -75,
  mars: (lat) => Math.abs(lat) <= 60,
  earth: (lat) => Math.abs(lat) <= 82,
};
const OUTSIDE: Record<Body, string> = {
  moon: "The Moon index covers 60°S to 60°N. For the pole, switch the lunar map to the south pole.",
  moon_polar: "The south pole index covers 75°S to 90°S.",
  mars: "The Mars index covers 60°S to 60°N.",
  earth: "The Earth index covers 82°S to 82°N.",
};
/** The buttons that pick which world sits beside Earth. */
const WORLD_BUTTON: Record<SourceBody, string> = {
  moon: "Moon 60°S–60°N", moon_polar: "Moon south pole", mars: "Mars",
};
const isSource = (v: string | null): v is SourceBody =>
  (SOURCE_BODIES as readonly string[]).includes(v ?? "");

interface Source {
  body: Body;
  lat: number;
  lon: number;
  label: string;
  site?: Site;
}

function parseSrc(v: string | null): { body: Body; lat: number; lon: number } | null {
  const m = v?.match(/^(moon|moon_polar|mars|earth):(-?[\d.]+),(-?[\d.]+)$/);
  return m ? { body: m[1] as Body, lat: Number(m[2]), lon: Number(m[3]) } : null;
}

export function Atlas() {
  const [params, setParams] = useSearchParams();
  const siteId = params.get("site");
  const tileId = params.get("tile");
  const newOnly = params.get("new") === "1";
  const wPhys = Number(params.get("w") ?? DEFAULT_W_PHYS);
  const srcParam = params.get("src");
  // `lunar` keeps its name so old links still work; it now also takes `mars`.
  const worldParam = params.get("lunar");
  const lunarParam: SourceBody = isSource(worldParam) ? worldParam : "moon";

  const [sites, setSites] = useState<Site[]>([]);
  const [analogs, setAnalogs] = useState<AnalogsResponse | null>(null);
  const [card, setCard] = useState<TwinsResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [siteTraps, setSiteTraps] = useState<Trap[]>([]);

  const [searchBody, setSearchBody] = useState<Body>("moon");
  const [search, setSearch] = useState<{ label: string; body: Body; hits: SearchHit[] } | null>(null);

  const [grids, setGrids] = useState<Record<Body, TileCell[]>>(
    { moon: [], moon_polar: [], mars: [], earth: [] });

  useEffect(() => {
    api.sites().then(setSites);
    // Full grids come from the static export; empty until 03_export.py has run.
    // moon_polar and mars are absent unless those indexes were built (#26,
    // docs/MARS-PLAN.md), so they must not take the others down with them.
    Promise.all([
      api.tiles("moon"),
      api.tiles("earth"),
      api.tiles("moon_polar").catch(() => [] as TileCell[]),
      api.tiles("mars").catch(() => [] as TileCell[]),
    ]).then(([moon, earth, moon_polar, mars]) => setGrids({ moon, earth, moon_polar, mars }));
  }, []);

  const site = sites.find((s) => s.id === siteId) ?? null;
  const source: Source | null = useMemo(() => {
    if (site) return { body: site.body, lat: site.lat, lon: site.lon, label: site.name, site };
    const p = parseSrc(srcParam);
    return p ? { ...p, label: `${BODY_NAME[p.body]} · ${coords(p.lat, p.lon)}` } : null;
  }, [site, srcParam]);

  const srcBody = source?.body ?? null;
  /** From Earth, the analogs are on the world shown beside it: Mars if the
   *  Mars map is up, else the equatorial Moon (the pole has too few tiles to
   *  search from Earth). */
  const earthDst: SourceBody = lunarParam === "mars" ? "mars" : "moon";
  /** The body the ranked analogs are on. Every Moon or Mars body pairs with Earth. */
  const dstBody: Body | null = srcBody === null ? null : srcBody === "earth" ? earthDst : "earth";
  /** The other world's half of the pair of maps (the name predates Mars). */
  const lunarBody: SourceBody =
    srcBody !== null && srcBody !== "earth" ? srcBody
    : srcBody === "earth" ? earthDst
    : search && search.body !== "earth" ? search.body
    : lunarParam;

  const update = (next: Record<string, string | null>) => {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v === null) merged.delete(k);
      else merged.set(k, v);
    }
    setParams(merged);
  };

  // ---- analogs for the current source -------------------------------------
  useEffect(() => {
    if (!source) {
      setAnalogs(null);
      return;
    }
    setBusy(true);
    setError(null);
    const req = {
      src_body: source.body, lat: source.lat, lon: source.lon,
      k: 12, new_only: newOnly, w_phys: wPhys,
      ...(source.body === "earth" && earthDst !== "moon" ? { dst_body: earthDst } : {}),
    };
    // The static export is precomputed at the default weight; any other weight
    // has to ask the API.
    const staticId = source.site && wPhys === DEFAULT_W_PHYS ? source.site.id : undefined;
    api
      .analogs(req, staticId)
      .then(setAnalogs)
      .catch((e: Error) => {
        setAnalogs(null);
        setError(e.message);
      })
      .finally(() => setBusy(false));
  }, [source, newOnly, wPhys, earthDst]);

  // ---- report card for the selected pair ----------------------------------
  useEffect(() => {
    if (!analogs || !tileId || !srcBody) {
      setCard(null);
      return;
    }
    const pending =
      srcBody === "earth"
        // Earth source: the selected hit is the Moon or Mars tile, the source the Earth one.
        ? api.twins(tileId, analogs.src_tile.tile_id, undefined, earthDst)
        : api.twins(analogs.src_tile.tile_id, tileId, site?.id, srcBody);
    pending.then(setCard).catch((e: Error) => setError(e.message));
  }, [analogs, tileId, srcBody, site, earthDst]);

  // ---- lookalike traps for a preset site (#30) ----------------------------
  useEffect(() => {
    if (!site) {
      setSiteTraps([]);
      return;
    }
    api.traps().then((t) => setSiteTraps(t?.by_site[site.id] ?? []));
  }, [site]);

  // The static export holds every candidate; "new only" filters here too.
  const hits: AnalogHit[] = (analogs?.results ?? [])
    .filter((h) => !newOnly || h.known_analog === null)
    .slice(0, 12);

  const startFrom = (body: Body, lat: number, lon: number) => {
    if (!IN_INDEX[body](lat)) {
      setNotice(OUTSIDE[body]);
      return;
    }
    setNotice(null);
    setSearch(null);
    update({
      site: null, tile: null,
      src: `${body}:${lat.toFixed(3)},${lon.toFixed(3)}`,
      // An Earth click keeps Mars beside it if Mars is showing; else the Moon.
      lunar: body === "earth" ? (lunarParam === "mars" ? "mars" : null)
        : body === "moon" ? null : body,
    });
  };

  const runSearch = (input: SearchInput) => {
    setBusy(true);
    setError(null);
    const body = searchBody;
    const req = "query" in input
      ? { body, query: input.query, k: 12 }
      : { body, image_b64: input.image_b64, k: 12 };
    api
      .search(req)
      .then((res) => setSearch({
        label: "query" in input ? input.query : `picture: ${input.filename}`,
        body, hits: res.results,
      }))
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false));
  };

  const paneProps = (body: Body) => {
    const onMapClick = (lat: number, lon: number) => startFrom(body, lat, lon);
    if (search && body === search.body) {
      return {
        markers: search.hits.map<MapMarker>((h) => ({
          tile_id: h.tile_id, lat: h.lat, lon: h.lon, label: h.known_analog ?? h.tile_id,
        })),
        onSelect: (id: string) => {
          const h = search.hits.find((x) => x.tile_id === id);
          if (h) startFrom(search.body, h.lat, h.lon);
        },
        onMapClick,
      };
    }
    if (source && body === srcBody) {
      return {
        markers: [{
          tile_id: analogs?.src_tile.tile_id ?? "source",
          lat: analogs?.src_tile.lat ?? source.lat,
          lon: analogs?.src_tile.lon ?? source.lon,
          label: source.label,
        }],
        focus: { lat: source.lat, lon: source.lon },
        onMapClick,
      };
    }
    if (body === dstBody) {
      return {
        markers: hits.map<MapMarker>((h) => ({
          tile_id: h.tile_id, lat: h.lat, lon: h.lon,
          weight: h.visual_cos_scaled, isNew: h.known_analog === null,
          label: h.known_analog ?? h.tile_id,
        })),
        selected: tileId,
        onSelect: (id: string) => update({ tile: id }),
        onMapClick,
      };
    }
    return { markers: [], onMapClick };
  };

  const guideable = site && site.body !== "earth" && !site.is_known_analog;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_26rem]">
      <div className="flex min-w-0 flex-col gap-4">
        <div className="rounded-lg border border-edge bg-panel">
          <div className="flex flex-wrap items-end gap-3 p-4">
            <span className="flex flex-col gap-1">
              <label htmlFor="site" className="text-xs uppercase tracking-wide text-muted">
                Target site
              </label>
              <select
                id="site"
                value={siteId ?? ""}
                onChange={(e) => {
                  setSearch(null);
                  update({ site: e.target.value || null, tile: null, src: null });
                }}
                className="max-w-[18rem] rounded border border-edge bg-base px-3 py-2 text-sm"
              >
                <option value="">{source && !site ? "Custom point (map click)" : "Pick a site…"}</option>
                <optgroup label="Moon base candidates (Artemis)">
                  {sites.filter((s) => s.is_base_region).map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </optgroup>
                <optgroup label="Other Moon sites">
                  {sites.filter((s) => !s.is_base_region && (s.body === "moon" || s.body === "moon_polar")).map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </optgroup>
                <optgroup label="Mars landing and exploration sites">
                  {sites.filter((s) => s.body === "mars").map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </optgroup>
                <optgroup label="Earth sites (find Moon or Mars terrain)">
                  {sites.filter((s) => s.body === "earth").map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </optgroup>
              </select>
            </span>
            <label className="flex items-center gap-2 py-2 text-sm">
              <input
                type="checkbox"
                checked={newOnly}
                onChange={(e) => update({ new: e.target.checked ? "1" : null })}
              />
              New candidates only
            </label>
            <label className="flex flex-col gap-1 py-1 text-xs text-muted"
                   title={api.isLive() ? undefined : "Needs the API: the static export is precomputed at 0.3"}>
              <span>Physical weight: <span className="tabular-nums text-ink">{wPhys.toFixed(1)}</span>
                {!api.isLive() && " (needs the API)"}</span>
              <input
                type="range" min={0} max={1} step={0.1} value={wPhys}
                disabled={!api.isLive()}
                aria-label="Physical weight"
                onChange={(e) => {
                  const v = Number(e.target.value);
                  update({ w: v === DEFAULT_W_PHYS ? null : String(v), tile: null });
                }}
                className="w-36 disabled:opacity-40"
              />
            </label>
            {guideable && (
              <Link to={`/sites/${site.id}`} className="ml-auto self-center text-sm text-holds underline">
                Field guide →
              </Link>
            )}
          </div>
          {site?.blurb && <p className="px-4 pb-2 text-sm text-muted">{site.blurb}</p>}
          {source && !site && (
            <p className="px-4 pb-2 text-sm text-muted">Searching from {source.label}.</p>
          )}
          <p className="px-4 pb-4 text-xs text-muted">
            Tip: click anywhere on either map to find analogs for that spot.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted">
          Compare Earth with:
          {SOURCE_BODIES.map((b) => (
            <button
              key={b}
              type="button"
              aria-pressed={lunarBody === b}
              disabled={srcBody !== null && srcBody !== "earth" && srcBody !== b}
              onClick={() => update({ lunar: b === "moon" ? null : b, tile: null })}
              className={`rounded border border-edge px-2 py-0.5 disabled:opacity-40 ${
                lunarBody === b ? "bg-edge text-ink" : "hover:text-ink"}`}
            >
              {WORLD_BUTTON[b]}
            </button>
          ))}
          {notice && <span role="status" className="ml-2 text-breaks">{notice}</span>}
        </div>

        {/* Earth is always the left pane and the Moon or Mars always the right
            one, whichever direction the search runs (#26). */}
        <div className="grid gap-4 md:grid-cols-2">
          {(["earth", lunarBody] as Body[]).map((body) => (
            <div key={body} className="h-72 lg:h-[26rem]">
              <MapPane body={body} grid={grids[body]} {...paneProps(body)} />
            </div>
          ))}
        </div>

        {card && (
          <div className="rounded-lg border border-edge bg-panel">
            <ReportCard data={card} />
          </div>
        )}

        {siteTraps.length > 0 && (
          <section className="rounded-lg border border-edge bg-panel p-4" aria-label="Lookalike traps">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm uppercase tracking-wide text-muted">Lookalike traps for this site</h2>
              <Link to="/traps" className="text-xs text-holds underline">All traps →</Link>
            </div>
            <p className="mt-1 text-sm text-muted">
              {siteTraps.length} of the 20 Earth tiles that look most like this site fail a physical
              check. An image-only search would have recommended them.
            </p>
            <div className="mt-3 grid gap-2 xl:grid-cols-2">
              {siteTraps.slice(0, 4).map((t) => <TrapCard key={t.earth_tile_id} trap={t} compact />)}
            </div>
          </section>
        )}
      </div>

      <aside className="flex max-h-[calc(100vh-8rem)] flex-col overflow-hidden rounded-lg border border-edge bg-panel lg:sticky lg:top-4">
        <SearchBox
          body={searchBody}
          onBodyChange={setSearchBody}
          busy={busy}
          error={error}
          onSearch={runSearch}
        />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {search ? (
            <SearchResults
              body={search.body}
              label={search.label}
              hits={search.hits}
              onPick={(h) => startFrom(search.body, h.lat, h.lon)}
              onClear={() => setSearch(null)}
            />
          ) : (
            <>
              <div className="border-t border-edge px-4 py-2 text-xs uppercase tracking-wide text-muted">
                {busy ? "Ranking…" : `${hits.length} candidates`}
                {dstBody && !busy && ` on ${BODY_NAME[dstBody]}`}
              </div>
              <AnalogList hits={hits} body={dstBody ?? "earth"} selected={tileId}
                          onSelect={(id) => update({ tile: id })} />
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
