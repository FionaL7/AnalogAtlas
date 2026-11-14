/** Lookalike traps (#30): what an image-only AI would recommend, and why it
 * fails. The headline is the trap rate; below it, the strongest examples. */
import { useEffect, useState } from "react";

import { BarList } from "../components/BarList";
import { TrapCard } from "../components/TrapCard";
import * as api from "../lib/api";
import { percent } from "../lib/format";
import type { Body, TrapsFile } from "../lib/types";

const BODY_NAME: Record<string, string> = { moon: "Moon, 60°S–60°N", moon_polar: "Moon south pole" };
const REASON_LABEL: Record<string, string> = {
  ice: "Ice sheet, not rock",
  vegetation: "Covered in plants",
  water: "Mostly lakes or wetland",
  wet_climate: "Wet climate",
  slope: "Different steepness",
  relief: "Different height range",
};
const FILTERS = ["all", "ice", "vegetation", "water", "wet_climate", "slope", "relief"] as const;

export function Traps() {
  const [data, setData] = useState<TrapsFile | null | undefined>(undefined);
  const [body, setBody] = useState<Body | "all">("all");
  const [reason, setReason] = useState<(typeof FILTERS)[number]>("all");
  useEffect(() => {
    api.traps().then(setData);
  }, []);

  if (data === undefined) return <p className="text-sm text-muted">Loading…</p>;
  if (data === null) {
    return (
      <p className="text-sm text-muted">
        Traps are not exported yet. Run <code>scripts/03_export.py</code>.
      </p>
    );
  }

  const shown = data.traps.filter((t) =>
    (body === "all" || t.src_body === body) &&
    (reason === "all" || t.breakers.some((b) => b.id === reason)));

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <header className="max-w-2xl">
        <h1 className="text-xl font-semibold">Lookalike traps</h1>
        <p className="mt-2 text-sm text-muted">
          For every lunar tile we took the 20 Earth tiles whose terrain <em>looks</em> most alike — what
          an image-only AI would recommend — and checked each against physics: ice, plants, water, a wet
          climate, or very different slopes. This is why AnalogAtlas never ranks on looks alone.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {data.stats.map((s) => {
          const reasons = Object.entries(s.by_reason).sort((a, b) => b[1] - a[1]);
          return (
            <section key={s.src_body} className="rounded-lg border border-edge bg-panel p-4">
              <h2 className="text-xs uppercase tracking-wide text-muted">{BODY_NAME[s.src_body] ?? s.src_body}</h2>
              <p className="mt-1 text-3xl font-semibold tabular-nums">{percent(s.trap_rate)}</p>
              <p className="text-sm text-muted">
                of the top lookalikes fail a physical check ({s.traps.toLocaleString()} of{" "}
                {s.lookalikes_checked.toLocaleString()})
              </p>
              <BarList
                caption={`Traps by reason, ${BODY_NAME[s.src_body] ?? s.src_body}. A trap can fail several checks.`}
                max={s.lookalikes_checked}
                bars={reasons.map(([id, n]) => ({
                  label: REASON_LABEL[id] ?? id,
                  value: n,
                  display: percent(n / s.lookalikes_checked),
                  detail: `${REASON_LABEL[id] ?? id}: ${n.toLocaleString()} of ${s.lookalikes_checked.toLocaleString()} lookalikes`,
                }))}
              />
              <p className="mt-1 text-[11px] text-muted">Share of all lookalikes checked. A trap can fail several checks.</p>
            </section>
          );
        })}
      </div>

      <section>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto text-sm uppercase tracking-wide text-muted">
            Strongest traps ({shown.length})
          </h2>
          <label className="text-xs text-muted">
            Body{" "}
            <select value={body} onChange={(e) => setBody(e.target.value as Body | "all")}
                    className="rounded border border-edge bg-base px-1.5 py-0.5 text-ink">
              <option value="all">All</option>
              {data.stats.map((s) => <option key={s.src_body} value={s.src_body}>{BODY_NAME[s.src_body]}</option>)}
            </select>
          </label>
          <label className="text-xs text-muted">
            Reason{" "}
            <select value={reason} onChange={(e) => setReason(e.target.value as (typeof FILTERS)[number])}
                    className="rounded border border-edge bg-base px-1.5 py-0.5 text-ink">
              {FILTERS.map((f) => <option key={f} value={f}>{f === "all" ? "Any" : REASON_LABEL[f]}</option>)}
            </select>
          </label>
        </div>
        <p className="mt-1 text-xs text-muted">
          One per Earth tile and per lunar tile; hard reasons (ice, plants, water) first. Pictures show
          terrain shape, the channel the lookalike was found in.
        </p>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {shown.map((t) => <TrapCard key={`${t.src_tile_id}-${t.earth_tile_id}`} trap={t} />)}
        </div>
        {shown.length === 0 && <p className="mt-3 text-sm text-muted">No traps match these filters.</p>}
      </section>
    </div>
  );
}
