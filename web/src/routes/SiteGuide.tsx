/** One field guide: a lunar site, its radar evidence, its best new Earth
 * analogs with what to test there, and the lookalikes to avoid. Everything
 * comes from the static export, so it works with the API down. */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { TileChip } from "../components/TileChip";
import { TrapCard } from "../components/TrapCard";
import { Portfolio } from "../components/panels/Portfolio";
import { FieldTestList } from "../components/panels/ReportCard";
import * as api from "../lib/api";
import type { TileLike } from "../lib/chips";
import { coords, groupBreakdown, percent } from "../lib/format";
import { loadGuide, type Guide } from "../lib/guide";
import type { PortfolioFile, Site } from "../lib/types";

function Fact({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded border border-edge p-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums">{value}</dd>
      {note && <dd className="text-[11px] text-muted">{note}</dd>}
    </div>
  );
}

function Radar({ guide }: { guide: Guide }) {
  const r = guide.radar;
  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-muted">Radar roughness</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        Circular polarisation ratio (CPR) measures how rough the surface is at the radar's wavelength.
        Higher means blockier rock, fresh ejecta, or — in cold traps — possibly ice. It sees roughness
        that pictures and slope maps cannot, which is why it confirms an analog rather than finds one.
      </p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded border border-edge p-3">
          <dt className="text-xs text-muted">Moon · LRO Mini-RF</dt>
          {r ? (
            <>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums">
                CPR {r.cpr_median.toFixed(2)} <span className="text-sm font-normal text-muted">median</span>
              </dd>
              <dd className="text-xs text-muted">
                90th percentile {r.cpr_p90.toFixed(2)} · {r.box_half_km * 2} km box ·{" "}
                {r.n_pixels.toLocaleString()} pixels · {percent(r.coverage)} coverage
              </dd>
              <dd className="mt-1 text-[11px] text-muted">{r.source}</dd>
            </>
          ) : (
            <dd className="mt-0.5 text-sm text-muted">Not measured for this site yet.</dd>
          )}
        </div>
        {guide.closeStudy.length > 0 ? guide.closeStudy.map((s) => {
          const cpr = s.radar.earth_cpr?.cpr_median;
          const s1 = s.radar.earth_s1.cpr_median;
          return (
            <div key={s.id} className="rounded border border-holds/60 p-3">
              <dt className="text-xs text-muted">Earth · {s.earth_name} (close study)</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums">
                {cpr != null ? <>CPR {cpr.toFixed(2)}</> : <>VH/VV {s1?.toFixed(2) ?? "—"}</>}{" "}
                <span className="text-sm font-normal text-muted">
                  {cpr != null ? "median, RADARSAT Constellation" : "median, Sentinel-1 indicator, not CPR"}
                </span>
              </dd>
              <dd className="mt-1 text-xs">
                <Link to={`/close-study/${s.id}`} className="text-holds underline">Read the close study →</Link>
              </dd>
            </div>
          );
        }) : (
          <div className="rounded border border-dashed border-edge p-3">
            <dt className="text-xs text-muted">Earth · RADARSAT Constellation (CSA)</dt>
            <dd className="mt-0.5 text-sm">Not in the close study.</dd>
            <dd className="mt-1 text-[11px] text-muted">
              Comparable CPR on Earth needs a compact-polarimetry RCM scene, freely available for Canada
              south of ~70°N. Elsewhere only a Sentinel-1 roughness indicator exists, which is not the
              same measurement. <Link to="/discoveries" className="underline">See the close-study pairs</Link>.
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}

function Candidates({ guide }: { guide: Guide }) {
  const { site } = guide;
  if (guide.candidates.length === 0) {
    return <p className="text-sm text-muted">No exported analogs for this site.</p>;
  }
  return (
    <ol className="flex flex-col gap-4">
      {guide.candidates.map(({ hit, card }, i) => {
        const groups = card ? groupBreakdown(card.breakdown) : null;
        return (
          <li key={hit.tile_id} className="rounded-lg border border-edge bg-panel p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="font-semibold">#{i + 1} · {coords(hit.lat, hit.lon)}</h3>
              <Link to={`/?site=${site.id}&tile=${encodeURIComponent(hit.tile_id)}`}
                    className="text-xs text-holds underline">Open the full report card →</Link>
            </div>
            <div className="mt-3 grid gap-4 md:grid-cols-[16rem_1fr]">
              <div className="grid grid-cols-2 gap-2">
                <TileChip body="earth" tile={(card?.earth as unknown as TileLike | undefined) ?? hit} label={`Earth candidate ${coords(hit.lat, hit.lon)}`} />
                <TileChip body={site.body} tile={(card?.moon as unknown as TileLike | undefined) ?? site} layer="shade" label={`${site.name}`} />
                <p className="text-[11px] text-muted">Earth</p>
                <p className="text-[11px] text-muted">{site.name}</p>
              </div>
              <div className="text-sm">
                <p>
                  terrain <strong>{percent(hit.visual_cos_scaled)}</strong> · physical{" "}
                  <strong>{percent(hit.physical)}</strong>
                  {hit.model_score != null && <> · analog model <strong>{percent(hit.model_score)}</strong></>}
                </p>
                {groups && (
                  <p className="mt-1 text-muted">
                    Holds on {groups.holds.map((r) => r.dimension.toLowerCase()).join(", ") || "nothing"}.
                    {groups.breaks.length > 0 && <> Breaks down on {groups.breaks.map((r) => r.dimension.toLowerCase()).join(", ")}.</>}
                  </p>
                )}
                {card?.field_tests && <FieldTestList tests={card.field_tests} />}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function SiteGuide() {
  const { id } = useParams();
  const [site, setSite] = useState<Site | null | undefined>(undefined);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioFile | null>(null);

  useEffect(() => {
    setGuide(null);
    setPortfolio(null);
    api.sites().then((all) => {
      const s = all.find((x) => x.id === id) ?? null;
      setSite(s);
      if (s) {
        loadGuide(s).then(setGuide);
        api.portfolio(s.id).then(setPortfolio);
      }
    });
  }, [id]);

  if (site === undefined) return <p className="text-sm text-muted">Loading…</p>;
  if (site === null) {
    return <p className="text-sm text-muted">No site called “{id}”. <Link to="/sites" className="underline">All field guides</Link></p>;
  }
  const cell = guide?.cell;
  const polar = site.body === "moon_polar";

  return (
    <article className="mx-auto flex max-w-5xl flex-col gap-8">
      <header className="grid gap-4 md:grid-cols-[12rem_1fr]">
        <TileChip body={site.body} tile={cell ?? site} layer="shade" caption label={`${site.name} terrain`} />
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">
            <Link to="/sites" className="hover:text-ink">Field guides</Link> ·{" "}
            {site.is_base_region ? "Artemis candidate base region" : "Moon site"}
          </p>
          <h1 className="mt-1 text-2xl font-semibold">{site.name}</h1>
          <p className="text-sm text-muted">{coords(site.lat, site.lon)}</p>
          {site.blurb && <p className="mt-2 text-sm text-muted">{site.blurb}</p>}
          <p className="mt-3">
            <Link to={`/?site=${site.id}`} className="text-sm text-holds underline">Explore in the Atlas →</Link>
          </p>
        </div>
      </header>

      {site.in_index === false ? (
        <p className="text-sm text-muted">This site is outside the index, so it has no analogs.</p>
      ) : (
        <>
          <section>
            <h2 className="text-sm uppercase tracking-wide text-muted">The ground, at 85 km</h2>
            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Fact label="Median slope" value={cell?.slope_med != null ? `${cell.slope_med.toFixed(1)}°` : "—"} note="LOLA" />
              <Fact label="Local relief" value={cell?.relief_km != null ? `${cell.relief_km.toFixed(2)} km` : "—"} note="LOLA" />
              {polar && (
                <>
                  <Fact label="Best-lit point" value={percent(cell?.illum_max)} note="of the time, LOLA 18.6-yr model" />
                  <Fact label="Permanent shadow" value={percent(cell?.psr_frac)} note="of the tile: cold traps, likely ice" />
                  <Fact label="Average sunlight" value={percent(cell?.avg_illum)} note="across the tile" />
                  <Fact label="Earth in view" value={percent(cell?.earth_vis)} note="direct-to-Earth comms" />
                </>
              )}
            </dl>
          </section>

          <Radar guide={guide ?? { site, cell: null, radar: null, candidates: [], traps: [], closeStudy: [] }} />

          <section>
            <h2 className="text-sm uppercase tracking-wide text-muted">Best new Earth analogs</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              The strongest candidates that are not near any well-studied analog site.
            </p>
            <div className="mt-3">
              {guide ? <Candidates guide={guide} /> : <p className="text-sm text-muted">Loading…</p>}
            </div>
          </section>

          {portfolio && portfolio.sites.length > 0 && (
            <section>
              <h2 className="text-sm uppercase tracking-wide text-muted">Smallest set of Earth sites</h2>
              <div className="mt-3"><Portfolio data={portfolio} siteName={site.name} /></div>
            </section>
          )}

          {guide && guide.traps.length > 0 && (
            <section>
              <h2 className="text-sm uppercase tracking-wide text-muted">Lookalikes to avoid</h2>
              <p className="mt-1 max-w-2xl text-sm text-muted">
                {guide.traps.length} of the 20 Earth tiles that look most like {site.name} fail a physical
                check. <Link to="/traps" className="text-holds underline">About traps</Link>
              </p>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {guide.traps.slice(0, 4).map((t) => <TrapCard key={t.earth_tile_id} trap={t} />)}
              </div>
            </section>
          )}
        </>
      )}
    </article>
  );
}
