/** Close study (#19): one new Earth analog, looked at up close. Radar
 * roughness on both bodies, 30 m slopes, a satellite picture, and the full
 * report card. Everything comes from the static export. */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { TileChip } from "../components/TileChip";
import { ReportCard } from "../components/panels/ReportCard";
import * as api from "../lib/api";
import type { TileLike } from "../lib/chips";
import { coords, percent } from "../lib/format";
import type { CloseStudyEntry, RadarStat, TwinsResponse } from "../lib/types";

const num = (v: number | null | undefined, d = 2) => (v == null ? "—" : v.toFixed(d));

function RadarCard({ title, stat, empty, dashed }: {
  title: string; stat: RadarStat | null; empty: string; dashed?: boolean;
}) {
  const label = stat?.measure === "s1_vh_vv" ? "VH/VV" : "CPR";
  return (
    <div className={`rounded border border-edge p-3 ${dashed ? "border-dashed" : ""}`}>
      <dt className="text-xs text-muted">{title}</dt>
      {stat && stat.cpr_median != null ? (
        <>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">
            {label} {num(stat.cpr_median)} <span className="text-sm font-normal text-muted">median</span>
          </dd>
          <dd className="text-xs text-muted">
            90th percentile {num(stat.cpr_p90)} · {stat.box_half_km * 2} km box ·{" "}
            {percent(stat.coverage)} coverage
            {stat.coverage < 0.5 && <strong className="text-breaks"> · uncertain, low coverage</strong>}
          </dd>
          <dd className="mt-1 text-[11px] text-muted">{stat.source}{stat.dates && ` · ${stat.dates.replace("/", " to ")}`}</dd>
        </>
      ) : (
        <dd className="mt-0.5 text-sm text-muted">{empty}</dd>
      )}
    </div>
  );
}

/** One plain sentence comparing the two CPRs. Only CPR is compared to CPR. */
export function cprVerdict(moon: number | null, earth: number | null): string | null {
  if (moon == null || earth == null) return null;
  const r = earth / moon;
  if (r > 0.8 && r < 1.25) return `About as rough as the Moon site at radar scale (Earth/Moon ratio ${r.toFixed(2)}).`;
  return r >= 1.25
    ? `Rougher than the Moon site at radar scale (${r.toFixed(2)}× its CPR).`
    : `Smoother than the Moon site at radar scale (${r.toFixed(2)}× its CPR).`;
}

function Radar({ s }: { s: CloseStudyEntry }) {
  const { moon, earth_cpr, earth_s1 } = s.radar;
  const verdict = cprVerdict(moon.cpr_median, earth_cpr?.cpr_median ?? null);
  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-muted">Radar roughness</h2>
      <p className="mt-1 max-w-3xl text-sm text-muted">
        CPR (circular polarisation ratio) says how much the ground scrambles a radar echo: ~0.2 is
        smooth, ~0.5 typical, 0.8 and up blocky. It senses roughness at centimetre-to-metre scale,
        what a footpad or wheel meets, which pictures and slope maps cannot see.
      </p>
      <dl className="mt-3 grid gap-3 md:grid-cols-3">
        <RadarCard title="Moon · LRO Mini-RF (12.6 cm)" stat={moon} empty="No Mini-RF coverage here." />
        <RadarCard
          title="Earth · RADARSAT Constellation (5.6 cm)" stat={earth_cpr}
          empty="No CPR here: free RCM compact-pol data covers Canada only."
          dashed={!earth_cpr}
        />
        <RadarCard title="Earth · Sentinel-1 (5.6 cm), indicator" stat={earth_s1}
                   empty="No Sentinel-1 scenes in the window." dashed />
      </dl>
      {verdict && <p className="mt-3 text-sm"><strong>{verdict}</strong></p>}
      <ul className="mt-2 max-w-3xl list-disc pl-5 text-xs text-muted">
        {!earth_cpr && (
          <li>
            Sentinel-1 sends straight (linear) waves, so it cannot measure CPR. Its VH/VV ratio rises
            with roughness too, but on a different scale: it ranks Earth sites against each other and
            is never compared with the Moon number directly.
          </li>
        )}
        <li>Different wavelengths: 12.6 cm on the Moon, 5.6 cm on Earth, so each senses a slightly different roughness scale.</li>
        <li>Plants scramble radar on Earth and the Moon has none, so vegetation pushes the Earth numbers up.</li>
      </ul>
    </section>
  );
}

function Slopes({ s, card }: { s: CloseStudyEntry; card: TwinsResponse | null }) {
  const moonSlope = card?.moon.slope_med as number | null | undefined;
  const earthSlope = card?.earth.slope_med as number | null | undefined;
  const fine = s.earth_slope_30m;
  return (
    <section>
      <h2 className="text-sm uppercase tracking-wide text-muted">Slopes</h2>
      <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded border border-edge p-3">
          <dt className="text-xs text-muted">Moon, 1.9 km baseline</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{num(moonSlope, 1)}°</dd>
          <dd className="text-[11px] text-muted">LOLA, median over the 85 km tile</dd>
        </div>
        <div className="rounded border border-edge p-3">
          <dt className="text-xs text-muted">Earth, 1.85 km baseline</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{num(earthSlope, 1)}°</dd>
          <dd className="text-[11px] text-muted">Copernicus DEM, same baseline as the Moon</dd>
        </div>
        <div className="rounded border border-edge p-3">
          <dt className="text-xs text-muted">Earth, 30 m</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{num(fine.slope_med, 1)}°</dd>
          <dd className="text-[11px] text-muted">median in the 30 km box</dd>
        </div>
        <div className="rounded border border-edge p-3">
          <dt className="text-xs text-muted">Earth, 30 m, steepest 10%</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{num(fine.slope_p90, 1)}°</dd>
          <dd className="text-[11px] text-muted">{fine.source}</dd>
        </div>
      </dl>
      <p className="mt-2 max-w-3xl text-xs text-muted">
        Only the 1.9 km slopes compare across bodies. Slopes get steeper at finer baselines, so the
        30 m number shows what a rover would meet on Earth; the lunar equivalent needs LOLA's
        high-resolution polar DEMs, which this build does not include.
      </p>
    </section>
  );
}

export function CloseStudyPage() {
  const { id } = useParams();
  const [entry, setEntry] = useState<CloseStudyEntry | null | undefined>(undefined);
  const [card, setCard] = useState<TwinsResponse | null>(null);

  useEffect(() => {
    setCard(null);
    api.closeStudy().then((all) => {
      const e = all?.find((x) => x.id === id) ?? null;
      setEntry(e);
      if (e) api.closeStudyCard(e.twin).then(setCard);
    });
  }, [id]);

  if (entry === undefined) return <p className="text-sm text-muted">Loading…</p>;
  if (entry === null) {
    return (
      <p className="text-sm text-muted">
        No close study called “{id}”. <Link to="/discoveries" className="underline">Discoveries</Link>
      </p>
    );
  }
  const s = entry;
  const moonTile = card?.moon as unknown as TileLike | undefined;
  const earthTile: TileLike = { lat: s.earth_lat, lon: s.earth_lon } as TileLike;

  return (
    <article className="mx-auto flex max-w-5xl flex-col gap-8">
      <header>
        <p className="text-xs uppercase tracking-wide text-muted">
          <Link to="/discoveries" className="hover:text-ink">Discoveries</Link> · Close study
        </p>
        <h1 className="mt-1 text-2xl font-semibold">{s.site_name} ↔ {s.earth_name}</h1>
        <p className="mt-1 text-sm text-muted">{s.headline}</p>
        <p className="mt-3 flex flex-wrap gap-4 text-sm">
          <Link to={`/sites/${s.site_id}`} className="text-holds underline">Field guide for {s.site_name} →</Link>
          <Link to={`/?site=${s.site_id}&tile=${encodeURIComponent(s.earth_tile_id)}`}
                className="text-holds underline">Open in the Atlas →</Link>
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <figure>
          {moonTile && <TileChip body={s.site_body} tile={moonTile} layer="shade" label={`${s.site_name} terrain`} />}
          <figcaption className="mt-1 text-xs text-muted">{s.site_name} · 85 km tile</figcaption>
        </figure>
        <figure>
          <TileChip body="earth" tile={earthTile} label={`${s.earth_name}, 85 km tile`} />
          <figcaption className="mt-1 text-xs text-muted">{s.earth_name} · 85 km tile · {coords(s.earth_lat, s.earth_lon)}</figcaption>
        </figure>
        {s.picture ? (
          <figure>
            <img src={s.picture.url} alt={`Sentinel-2 picture of ${s.earth_name}, 30 km across`}
                 className="aspect-square w-full rounded border border-edge object-cover" />
            <figcaption className="mt-1 text-xs text-muted">
              The 30 km close-study box · {s.picture.source} · {s.picture.date}
            </figcaption>
          </figure>
        ) : (
          <p className="text-sm text-muted">No cloud-free Sentinel-2 picture in the window.</p>
        )}
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wide text-muted">Why this pair, and why it is new</h2>
        <p className="mt-2 max-w-3xl text-sm">{s.why_picked}</p>
        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <div><dt className="inline text-muted">Rank among new analogs for {s.site_name}: </dt>
               <dd className="inline font-semibold tabular-nums">{s.rank_among_new == null ? "—" : `#${s.rank_among_new}`}</dd></div>
          {s.model_score != null && (
            <div><dt className="inline text-muted">Analog model: </dt>
                 <dd className="inline font-semibold tabular-nums">{percent(s.model_score)} percentile</dd></div>
          )}
          <div><dt className="inline text-muted">Nearest well-studied analog: </dt>
               <dd className="inline">{s.nearest_known.name}, <strong className="tabular-nums">{s.nearest_known.km.toLocaleString()} km</strong> away</dd></div>
        </dl>
      </section>

      <Radar s={s} />
      <Slopes s={s} card={card} />

      <section className="rounded-lg border border-edge bg-panel">
        {card ? <ReportCard data={card} /> : <p className="p-4 text-sm text-muted">Loading the report card…</p>}
      </section>
    </article>
  );
}

/** The close-study pairs as cards, for Discoveries and the field guides. */
export function CloseStudyList({ entries }: { entries: CloseStudyEntry[] }) {
  return (
    <ul className="grid gap-3 md:grid-cols-3">
      {entries.map((s) => (
        <li key={s.id} className="rounded-lg border border-holds/60 bg-panel p-3">
          <Link to={`/close-study/${s.id}`} className="block">
            <img src={s.picture?.url} alt="" className={`mb-2 aspect-[2/1] w-full rounded object-cover ${s.picture ? "" : "hidden"}`} />
            <p className="text-xs text-muted">{s.site_name} ↔</p>
            <p className="font-semibold">{s.earth_name}</p>
            <p className="mt-1 text-xs text-muted">{s.headline}</p>
            <p className="mt-2 text-xs text-holds underline">Read the close study →</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
