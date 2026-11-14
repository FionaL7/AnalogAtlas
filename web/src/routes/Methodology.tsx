/** How the search works, how we checked it, and what it does not claim.
 * Validation numbers come from validation.json (#29); without it the section
 * says so instead of showing placeholders. */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { BarList } from "../components/BarList";
import * as api from "../lib/api";
import type { ValidationFile } from "../lib/types";

type Target = "all" | "moon" | "mars";
const TARGET_LABEL: Record<Target, string> = { all: "All analogs", moon: "Moon analogs", mars: "Mars analogs" };
const OURS = "Our model (shape + physics + environment)";

function Validation({ data }: { data: NonNullable<ValidationFile["analog_model"]> }) {
  const available = (Object.keys(TARGET_LABEL) as Target[]).filter((t) => data.targets[t]);
  const [target, setTarget] = useState<Target>(available[0] ?? "all");
  const t = data.targets[target];
  if (!t) return null;
  const methods = Object.entries(t.summary).sort((a, b) => a[1].median_top_pct - b[1].median_top_pct);
  const sites = [...t.per_site].sort((a, b) => a.top_pct - b.top_pct);
  const weights = [...(t.weights ?? [])].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)).slice(0, 8);
  const ours = t.summary[OURS];

  return (
    <>
      <p className="mt-2 text-muted">
        The analog model learns what well-studied analog sites have in common, then ranks every Earth
        tile. To test it we hide one known site, train on the rest, and see where the hidden site lands
        among all ~11,700 Earth tiles. A random guess lands at {data.random_baseline_top_pct}% on
        average. Lower is better.
      </p>

      <div role="tablist" aria-label="Analog target" className="mt-3 flex gap-1">
        {available.map((k) => (
          <button
            key={k}
            role="tab"
            type="button"
            aria-selected={k === target}
            onClick={() => setTarget(k)}
            className={`rounded border border-edge px-2 py-1 text-xs ${k === target ? "bg-edge text-ink" : "text-muted hover:text-ink"}`}
          >
            {TARGET_LABEL[k]} ({data.targets[k]!.sites_used.length})
          </button>
        ))}
      </div>

      {ours && (
        <p className="mt-4 text-base">
          A hidden site lands in the <strong className="text-holds">top {ours.median_top_pct}%</strong> of
          Earth (median), and {ours.in_top_10pct} of {ours.n} land in the top 10%.
        </p>
      )}

      <h3 className="mt-4 font-semibold">Where hidden sites rank, by method (median)</h3>
      <BarList
        caption="Median rank of the hidden site, as a top percentage of all Earth tiles, per method"
        max={data.random_baseline_top_pct}
        reference={{ value: data.random_baseline_top_pct, label: `random guess, ${data.random_baseline_top_pct}%` }}
        bars={methods.map(([name, s]) => ({
          label: name,
          value: s.median_top_pct,
          display: `top ${s.median_top_pct}%`,
          highlight: name === OURS,
          detail: `${name}: median top ${s.median_top_pct}%, mean ${s.mean_top_pct}%, ${s.in_top_5pct}/${s.n} in top 5%, ${s.in_top_10pct}/${s.n} in top 10%`,
        }))}
      />

      <details className="mt-4">
        <summary className="cursor-pointer text-sm">Every hidden site ({sites.length})</summary>
        <BarList
          caption="Rank of each hidden known site under our model"
          max={100}
          reference={{ value: data.random_baseline_top_pct, label: "random guess" }}
          bars={sites.map((s) => ({ label: s.site, value: s.top_pct, display: `top ${s.top_pct}%` }))}
        />
      </details>

      {weights.length > 0 && (
        <>
          <h3 className="mt-4 font-semibold">What the model leans on</h3>
          <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
            {weights.map((w) => (
              <li key={w.feature} className="flex justify-between gap-2 border-b border-edge py-1">
                <span>{w.feature}</span>
                <span className="tabular-nums text-muted">
                  {w.weight > 0 ? "more → more analog-like" : "more → less analog-like"}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="mt-3 text-xs text-muted">
        {data.method}. {data.note}.
        {data.skipped_sites && ` ${Object.keys(data.skipped_sites).length} known sites are left out of training: islands with no land tile, and process analogs whose surface looks nothing like the Moon (forested craters, lakes).`}
      </p>
    </>
  );
}

export function Methodology() {
  const [validation, setValidation] = useState<ValidationFile | null | undefined>(undefined);
  useEffect(() => {
    api.validation().then(setValidation);
  }, []);
  const model = validation?.analog_model;

  return (
    <article className="mx-auto max-w-2xl text-sm leading-relaxed">
      <h1 className="text-xl font-semibold">How AnalogAtlas decides two places are alike</h1>

      <h2 className="mt-6 font-semibold">Two stages</h2>
      <p className="mt-2 text-muted">
        Global screening splits the Moon and Earth's land into tiles of about 85 × 85 km. Each tile
        gets CLIP embeddings and physical measurements, and search runs across both bodies. The
        strongest new candidates then get a close study with radar surface roughness.
      </p>

      <h2 className="mt-6 font-semibold">How a pair is scored</h2>
      <ul className="mt-2 list-disc pl-5 text-muted">
        <li><strong className="text-ink">Terrain</strong>: CLIP similarity of the two hillshades, averaged over four sun directions, shown as a percentile.</li>
        <li><strong className="text-ink">Physical</strong>: closeness of median slope and local relief, both measured at ~1.9 km per pixel.</li>
        <li><strong className="text-ink">Analog model</strong>: how much the Earth tile resembles known analog sites, from terrain, look, climate, vegetation and ice (#29).</li>
        <li><strong className="text-ink">Report card</strong>: every dimension compared on its own, grouped into holds, breaks down, and what Earth cannot reproduce.</li>
      </ul>

      <h2 className="mt-6 font-semibold">Why the comparison is fair</h2>
      <p className="mt-2 text-muted">
        LOLA LDEM_16 is 1.9 km/px and ETOPO 60s is 1.85 km/px, so slope and relief are measured at
        the same baseline on both bodies by construction — not rescaled after the fact.
      </p>

      <h2 className="mt-6 font-semibold">Checked against independent data</h2>
      <p className="mt-2 text-muted">
        Text queries for craters, mare and highlands return terrain whose slopes, measured
        independently from LOLA elevation, match what the query asked for:
      </p>
      <BarList
        caption="Median slope of the top 6 tiles for three text queries"
        max={8}
        reference={{ value: 3.9, label: "median slope of all Moon tiles, 3.9°" }}
        bars={[
          { label: "“smooth flat dark lava plains”", value: 0.4, display: "0.4°" },
          { label: "“a large impact crater with a central peak”", value: 3.3, display: "3.3°" },
          { label: "“rugged mountainous highlands”", value: 6.5, display: "6.5°", highlight: true },
        ]}
      />

      <h2 className="mt-6 font-semibold">Validation: can it find analogs we already know?</h2>
      {validation === undefined ? (
        <p className="mt-2 text-muted">Loading…</p>
      ) : model ? (
        <Validation data={model} />
      ) : (
        <p className="mt-2 text-muted">
          Not exported yet. Run <code>scripts/04_train.py</code>, then <code>scripts/03_export.py</code>.
        </p>
      )}

      <h2 className="mt-6 font-semibold">Why looking alike is not enough</h2>
      <p className="mt-2 text-muted">
        Most Earth tiles that look most like a lunar tile fail a physical check: they are ice sheets,
        forests, wetlands, or simply far steeper. See the <Link to="/traps" className="text-holds underline">lookalike traps</Link>.
      </p>

      <h2 className="mt-6 font-semibold">What the numbers are not</h2>
      <ul className="mt-2 list-disc pl-5 text-muted">
        <li>The ranking score mixes a standardised visual score with physical closeness. It is not a 0–1 similarity, so it is never shown.</li>
        <li>Lunar surface temperature extremes are modelled from latitude (or, at the pole, from shadow), not measured.</li>
        <li>Atmosphere and gravity cannot be reproduced on Earth at all. They are listed as limits, not as low scores.</li>
        <li>The analog model was trained on 14 Moon sites; for the Moon alone, CLIP-only does as well. We say so rather than hide it.</li>
      </ul>
    </article>
  );
}
