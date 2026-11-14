/**
 * The explorer: pick a Moon site -> ranked Earth analogs -> report card.
 *
 * State lives in the URL (?site=&tile=) so any view can be shared or linked
 * from the slides (§6).
 */
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { MapPane } from "../components/map/MapPane";
import { AnalogList } from "../components/panels/AnalogList";
import { ReportCard } from "../components/panels/ReportCard";
import { SearchBox } from "../components/panels/SearchBox";
import * as api from "../lib/api";
import type { AnalogHit, AnalogsResponse, Site, TwinsResponse } from "../lib/types";

export function Atlas() {
  const [params, setParams] = useSearchParams();
  const siteId = params.get("site");
  const tileId = params.get("tile");
  const newOnly = params.get("new") === "1";

  const [sites, setSites] = useState<Site[]>([]);
  const [analogs, setAnalogs] = useState<AnalogsResponse | null>(null);
  const [card, setCard] = useState<TwinsResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sites().then(setSites);
  }, []);

  const site = sites.find((s) => s.id === siteId) ?? null;

  useEffect(() => {
    if (!site) return;
    setBusy(true);
    setError(null);
    api
      .analogs({ src_body: site.body, lat: site.lat, lon: site.lon, k: 12, new_only: newOnly })
      .then(setAnalogs)
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false));
  }, [site, newOnly]);

  useEffect(() => {
    if (!analogs || !tileId) return setCard(null);
    api
      .twins(analogs.src_tile.tile_id, tileId)
      .then(setCard)
      .catch((e: Error) => setError(e.message));
  }, [analogs, tileId]);

  const update = (next: Record<string, string | null>) => {
    const merged = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v === null) merged.delete(k);
      else merged.set(k, v);
    }
    setParams(merged);
  };

  const hits: AnalogHit[] = analogs?.results ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_26rem]">
      <div className="flex flex-col gap-4">
        <div className="rounded-lg border border-edge bg-panel">
          <div className="flex flex-wrap items-end gap-3 p-4">
            <span className="flex flex-col gap-1">
              <label htmlFor="site" className="text-xs uppercase tracking-wide text-muted">
                Target site
              </label>
              <select
                id="site"
                value={siteId ?? ""}
                onChange={(e) => update({ site: e.target.value || null, tile: null })}
                className="rounded border border-edge bg-base px-3 py-2 text-sm"
              >
                <option value="">Pick a site…</option>
                <optgroup label="Moon base candidates (Artemis)">
                  {sites.filter((s) => s.is_base_region).map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </optgroup>
                <optgroup label="Other sites">
                  {sites.filter((s) => !s.is_base_region).map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.body})</option>
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
          </div>
          {site?.blurb && <p className="px-4 pb-4 text-sm text-muted">{site.blurb}</p>}
        </div>

        <div className="h-72 lg:h-[26rem]">
          <MapPane
            body="earth"
            markers={hits.map((h) => ({
              tile_id: h.tile_id, lat: h.lat, lon: h.lon,
              weight: h.visual_cos_scaled, isNew: h.known_analog === null,
              label: h.known_analog ?? h.tile_id,
            }))}
            selected={tileId}
            onSelect={(id) => update({ tile: id })}
          />
        </div>

        {card && (
          <div className="rounded-lg border border-edge bg-panel">
            <ReportCard data={card} />
          </div>
        )}
      </div>

      <aside className="flex max-h-[calc(100vh-8rem)] flex-col overflow-hidden rounded-lg border border-edge bg-panel">
        <SearchBox
          busy={busy}
          error={error}
          onSearch={(q) => {
            setBusy(true);
            api
              .search({ body: "moon", query: q, k: 12 })
              .then(() => setError(null))
              .catch((e: Error) => setError(e.message))
              .finally(() => setBusy(false));
          }}
        />
        <div className="border-t border-edge px-4 py-2 text-xs uppercase tracking-wide text-muted">
          {busy ? "Ranking…" : `${hits.length} candidates`}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <AnalogList hits={hits} selected={tileId} onSelect={(id) => update({ tile: id })} />
        </div>
      </aside>
    </div>
  );
}
