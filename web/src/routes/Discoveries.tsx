/** New analog candidates (#29): Earth tiles the analog model ranks highest that
 * are not near any well-studied analog site. Each links into the Atlas to find
 * the lunar terrain it matches. */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { TileChip } from "../components/TileChip";
import { MapPane } from "../components/map/MapPane";
import * as api from "../lib/api";
import { CloseStudyList } from "./CloseStudy";
import { coords } from "../lib/format";
import type { Candidate, CandidatesFile, CloseStudyEntry } from "../lib/types";

type Target = "moon" | "mars" | "all";
const TARGET_LABEL: Record<Target, string> = { moon: "Moon", mars: "Mars", all: "Moon or Mars" };

function hours(min: number | null | undefined): string {
  if (min == null) return "—";
  return min < 90 ? `${min} min` : `${Math.round(min / 60)} h`;
}

function Row({ c, i, selected, onSelect }: {
  c: Candidate; i: number; selected: boolean; onSelect: () => void;
}) {
  return (
    <li className={`rounded-lg border p-3 ${selected ? "border-holds bg-holds/5" : "border-edge bg-panel"}`}>
      <div className="grid grid-cols-[5rem_1fr] gap-3">
        <button type="button" onClick={onSelect} aria-label={`Show candidate ${i + 1} on the map`}>
          <TileChip body="earth" tile={c} label={`Candidate at ${coords(c.lat, c.lon)}`} />
        </button>
        <div className="min-w-0">
          <p className="flex flex-wrap items-baseline gap-2">
            <span className="text-xs text-muted">#{i + 1}</span>
            <strong>{coords(c.lat, c.lon)}</strong>
            <span className="text-xs text-muted">model: {c.score_pct.toFixed(2)} percentile</span>
          </p>
          <p className="mt-1 text-sm text-muted">Why: {c.why.join(", ")}</p>
          <dl className="mt-1 flex flex-wrap gap-x-4 text-xs">
            <div><dt className="inline text-muted">slope </dt><dd className="inline tabular-nums">{c.slope_med ?? "—"}°</dd></div>
            <div><dt className="inline text-muted">bare ground </dt><dd className="inline tabular-nums">{c.barren_frac == null ? "—" : `${Math.round(c.barren_frac * 100)}%`}</dd></div>
            <div><dt className="inline text-muted">rain </dt><dd className="inline tabular-nums">{c.precip_mm ?? "—"} mm/yr</dd></div>
            <div><dt className="inline text-muted">to nearest city </dt><dd className="inline tabular-nums">{hours(c.access_min)}</dd></div>
          </dl>
          <Link
            to={`/?src=earth:${c.lat.toFixed(3)},${c.lon.toFixed(3)}`}
            className="mt-2 inline-block text-xs text-holds underline"
          >
            Find the lunar terrain it matches →
          </Link>
        </div>
      </div>
    </li>
  );
}

export function Discoveries() {
  const [data, setData] = useState<CandidatesFile | null | undefined>(undefined);
  const [target, setTarget] = useState<Target>("moon");
  const [selected, setSelected] = useState<string | null>(null);
  const [study, setStudy] = useState<CloseStudyEntry[] | null>(null);
  useEffect(() => {
    api.candidates().then(setData);
    api.closeStudy().then(setStudy);
  }, []);

  if (data === undefined) return <p className="text-sm text-muted">Loading…</p>;
  if (data === null) {
    return (
      <p className="text-sm text-muted">
        No candidates exported yet. Run <code>scripts/04_train.py</code>, then <code>scripts/03_export.py</code>.
      </p>
    );
  }
  const list = data[target] ?? [];
  const targets = (Object.keys(TARGET_LABEL) as Target[]).filter((t) => data[t]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <header className="max-w-2xl">
        <h1 className="text-xl font-semibold">New analog candidates</h1>
        <p className="mt-2 text-sm text-muted">
          The analog model learned what 32 well-studied analog sites have in common: terrain, surface
          look, climate, vegetation and ice. These are the Earth tiles it ranks highest that are{" "}
          <strong className="text-ink">not</strong> near any known site, with ice sheets excluded. Each
          says why it scored high. They are leads for a close study, not confirmed analogs. See how well
          the model finds known sites on the{" "}
          <Link to="/methodology" className="text-holds underline">methodology page</Link>.
        </p>
      </header>

      {study && study.length > 0 && (
        <section aria-labelledby="close-study">
          <h2 id="close-study" className="text-sm uppercase tracking-wide text-muted">Close study</h2>
          <p className="mt-1 mb-3 max-w-2xl text-sm text-muted">
            {study.length} of the strongest new analogs, measured up close: radar roughness on both
            bodies, 30 m slopes, a satellite picture, and the full report card.
          </p>
          <CloseStudyList entries={study} />
        </section>
      )}

      <div role="tablist" aria-label="Analog for" className="flex gap-1">
        {targets.map((t) => (
          <button key={t} role="tab" type="button" aria-selected={t === target}
                  onClick={() => { setTarget(t); setSelected(null); }}
                  className={`rounded border border-edge px-2 py-1 text-xs ${t === target ? "bg-edge text-ink" : "text-muted hover:text-ink"}`}>
            Analogs for {TARGET_LABEL[t]}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_28rem]">
        <div className="h-80 lg:sticky lg:top-4 lg:h-[32rem]">
          <MapPane
            body="earth"
            markers={list.map((c) => ({
              tile_id: c.tile_id, lat: c.lat, lon: c.lon, weight: c.score_pct / 100, isNew: true,
              label: coords(c.lat, c.lon),
            }))}
            selected={selected}
            onSelect={setSelected}
            legend="Analog model (percentile)"
          />
        </div>
        <ol className="flex flex-col gap-2">
          {list.map((c, i) => (
            <Row key={c.tile_id} c={c} i={i} selected={selected === c.tile_id}
                 onSelect={() => setSelected(c.tile_id)} />
          ))}
        </ol>
      </div>
    </div>
  );
}
