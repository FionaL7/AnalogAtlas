/** How the search works, how we checked it, and what it does not claim.
 * Validation numbers come from validation.json: the hold-one-out model (#29),
 * and crater retrieval plus known-analog ranking (#16). Any section whose key
 * is missing says so instead of showing placeholders. */
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { BarList } from "../components/BarList";
import * as api from "../lib/api";
import type {
  CraterRetrieval, KnownAnalogRanking, PolarAnalogRanking, PrecisionGroup, ValidationFile,
} from "../lib/types";

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

const K = 10;
const pct = (v: number) => Math.round(v * 1000) / 10;
const pAt = (g: PrecisionGroup, k = K) => g[`p_at_${k}`] ?? null;

/** Precision@k against Robbins crater labels, which enter nothing else (#16). */
function Craters({ data }: { data: CraterRetrieval }) {
  const classes = data.density_class.by_class;
  const chance = data.density_class.overall.random_baseline;
  const rows: [string, PrecisionGroup][] = [
    ["Heavily cratered", classes["heavily cratered"]],
    ["Smooth (mare)", classes.smooth],
    ["Middling", classes.middling],
  ];
  const big = pAt(data.big_crater);

  return (
    <>
      <p className="mt-2 text-muted">
        The Robbins (2019) catalog of 1.3 million lunar craters is held out: it is not a feature and
        not a training label. We sort all {data.tiles.toLocaleString()} Moon tiles into thirds by how
        many craters they hold, then ask each tile for its {K} nearest neighbours by image embedding
        and count how many fall in the same third. One in three would do that by chance.
      </p>
      <BarList
        caption={`Of the ${K} nearest tiles by embedding, the percentage carrying the same crater-density label`}
        max={100}
        reference={{ value: pct(chance), label: `chance, ${pct(chance)}%` }}
        bars={rows.map(([label, g]) => {
          const p = pAt(g);
          return {
            label,
            value: p === null ? 0 : pct(p),
            display: p === null ? "—" : `${pct(p)}%`,
            highlight: label === "Heavily cratered",
            detail: `${label}: ${g.n_queries} queries, p@${K} ${p === null ? "n/a" : pct(p) + "%"}, chance ${pct(g.random_baseline)}%`,
          };
        })}
      />
      <p className="mt-2 text-muted">
        The ends of the scale are what retrieval is good at — saturated highlands and smooth mare are
        each found about twice as often as chance. The middle third is barely better than chance, and
        a single big crater (
        {big === null ? "not measured" : `${pct(big)}% versus ${pct(data.big_crater.random_baseline)}% chance`})
        is a much weaker signal than overall cratering. Both are real limits, not rounding.
      </p>
    </>
  );
}

/** Where the known analogs rank, queried from lunar sites of the same role (#16). */
function KnownAnalogs({ data }: { data: KnownAnalogRanking }) {
  const scored = data.sites.filter((s) => s.moon_target && s.shipped);
  const others = data.sites.filter((s) => !s.moon_target && s.shipped);
  const s = data.summary;
  const bar = (row: KnownAnalogRanking["sites"][number]) => ({
    label: row.site.replace(/,.*$/, ""),
    value: row.shipped!.top_pct,
    display: `top ${row.shipped!.top_pct}%`,
    highlight: row.shipped!.top_pct <= 1,
    detail: `${row.site}: rank ${row.shipped!.rank} of ${data.earth_tiles_ranked} queried from ${row.shipped!.query} (role: ${row.shipped!.role}); image-only ${row.image_only?.top_pct ?? "n/a"}%${row.shipped!.pushed_down ? "; pushed down by the environment checks" : ""}`,
  });

  return (
    <>
      <p className="mt-2 text-muted">
        A volcanic analog is only a fair test when the query is a volcanic place on the Moon, so each
        site is ranked from lunar sites that share its role — Copernicus and Tycho for impact,
        Aristarchus and the Gruithuisen Domes for volcanic, the Artemis regions for polar. Lower is
        better; 50% is chance.
      </p>
      {s.median_top_pct !== null && (
        <p className="mt-3 text-base">
          Of {s.n} Moon analogs, the median lands in the{" "}
          <strong className="text-holds">top {s.median_top_pct}%</strong> of{" "}
          {data.earth_tiles_ranked.toLocaleString()} Earth tiles, {s.in_top_1pct} in the top 1% and{" "}
          {s.in_top_10pct} in the top 10%.
        </p>
      )}
      <BarList
        caption="Rank of each known Moon analog, as a top percentage of all Earth tiles"
        max={100}
        reference={{ value: 50, label: "chance, 50%" }}
        bars={scored.map(bar)}
      />
      {others.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm">
            Mars analogs, ranked for information only ({others.length})
          </summary>
          <p className="mt-2 text-xs text-muted">
            These are not Moon analogs, so a poor rank here is not a failure. They are shown because
            several are the sites a reader expects to see.
          </p>
          <BarList
            caption="Rank of each Mars analog, for information only"
            max={100}
            reference={{ value: 50, label: "chance, 50%" }}
            bars={others.map(bar)}
          />
        </details>
      )}
      <p className="mt-3 text-xs text-muted">
        {Object.keys(data.skipped_sites).length} known sites are not ranked at all: process analogs
        whose surface looks nothing like the Moon, islands with no land tile, and roles with no lunar
        counterpart — the whole Moon is arid, so no lunar site tests an arid analog.
      </p>
    </>
  );
}

/** Mars validation (#40): the same known-analog test with Mars as the source
 * body, plus the visual-channel comparison and the Mars trap rate. The keys
 * are new, so they are typed here until the shared types catch up. */
type MarsRanking = Omit<KnownAnalogRanking, "sites"> & {
  sites: (Omit<KnownAnalogRanking["sites"][number], "moon_target"> & { mars_target: boolean })[];
};
type MarsChannels = {
  channels: Record<string, { median_top_pct: number; in_top_5pct: number; n: number }>;
  best: string;
  recommendation: string;
};
type MarsTraps = { trap_rate: number; traps: number; lookalikes_checked: number };
const CHANNEL_LABEL: Record<string, string> = {
  shade_only: "Hillshade only (what ships)",
  look_only: "Viking colour only",
  "mixed_0.6": "Mixed (60% hillshade)",
};

function MarsAnalogs({ data, channels, traps }:
  { data: MarsRanking; channels?: MarsChannels; traps?: MarsTraps }) {
  const scored = data.sites.filter((s) => s.mars_target && s.shipped);
  const s = data.summary;

  return (
    <>
      <p className="mt-2 text-muted">
        The same test, with Mars as the source body — and a stronger one, because unlike the Moon
        every role is testable: Mars has arid sites, water-altered sites (Jezero, Oxia Planum) and
        ice-rich landing zones (Arcadia, Utopia, Deuteronilus) to query from. Lower is better; 50%
        is chance.
      </p>
      {s.median_top_pct !== null && (
        <p className="mt-3 text-base">
          Of {s.n} Mars analogs, the median lands in the{" "}
          <strong className="text-holds">top {s.median_top_pct}%</strong> of{" "}
          {data.earth_tiles_ranked.toLocaleString()} Earth tiles, {s.in_top_1pct} in the top 1% and{" "}
          {s.in_top_10pct} in the top 10%.
        </p>
      )}
      <BarList
        caption="Rank of each known Mars analog, as a top percentage of all Earth tiles"
        max={100}
        reference={{ value: 50, label: "chance, 50%" }}
        bars={scored.map((row) => ({
          label: row.site.replace(/,.*$/, ""),
          value: row.shipped!.top_pct,
          display: `top ${row.shipped!.top_pct}%`,
          highlight: row.shipped!.top_pct <= 1,
          detail: `${row.site}: rank ${row.shipped!.rank} of ${data.earth_tiles_ranked} queried from ${row.shipped!.query} (role: ${row.shipped!.role}); image-only ${row.image_only?.top_pct ?? "n/a"}%${row.shipped!.pushed_down ? "; pushed down by the environment checks" : ""}`,
        }))}
      />
      {channels && (
        <>
          <h3 className="mt-4 font-semibold">Does the Viking colour channel help?</h3>
          <p className="mt-2 text-muted">
            The risk in the plan: Viking colour and Earth's Blue Marble look so different that
            mixing the colour channel in would drag the ranking down. Measured on the medians above:
          </p>
          <BarList
            caption="Median known-analog rank per visual channel"
            max={50}
            bars={Object.entries(channels.channels).map(([k, c]) => ({
              label: CHANNEL_LABEL[k] ?? k,
              value: c.median_top_pct,
              display: `top ${c.median_top_pct}%`,
              highlight: k === channels.best,
              detail: `${CHANNEL_LABEL[k] ?? k}: median top ${c.median_top_pct}%, ${c.in_top_5pct}/${c.n} in top 5%`,
            }))}
          />
          <p className="mt-2 text-xs text-muted">Conclusion: {channels.recommendation}.</p>
        </>
      )}
      {traps && (
        <p className="mt-3 text-muted">
          Lookalike traps exist on Mars too: of each Mars tile's top {""}
          {Math.round(traps.lookalikes_checked / data.earth_tiles_ranked) || 20} Earth lookalikes
          by terrain shape alone, {Math.round(1000 * traps.trap_rate) / 10}% fail a hard physical
          check (ice, plants, water) — {traps.traps.toLocaleString()} of{" "}
          {traps.lookalikes_checked.toLocaleString()} checked.
        </p>
      )}
      <h3 className="mt-4 font-semibold">What the Mars numbers cannot say</h3>
      <ul className="mt-2 list-disc pl-5 text-muted">
        <li>GRS water is measured in 5° (~300 km) bins: regional context, never a per-tile match.</li>
        <li>Thermal inertia against Earth's day–night swing is a proxy, and Earth's air and moisture distort it.</li>
        <li>The dust index is decoded from a published colour map, so it is relative, not in physical units.</li>
        <li>Mars surface temperatures are modelled from latitude, albedo and thermal inertia, not measured.</li>
        <li>Hydrated-mineral counts are empty until the Trek feature service returns.</li>
        <li>0.6 kPa of CO₂, 38% gravity, radiation, perchlorates and global dust storms have no Earth analog at all.</li>
      </ul>
    </>
  );
}

/** #32: the polar dimensions report but do not rank, and this is the cost. */
function PolarAnalogs({ data }: { data: PolarAnalogRanking }) {
  const sites = Object.entries(data.by_query_site ?? {});
  if (sites.length === 0) return null;
  const shared = Object.entries(data.query_sites_sharing_a_tile ?? {});

  return (
    <>
      <p className="mt-2 text-muted">
        For the Artemis regions the index also carries illumination, permanently shadowed fraction and
        Earth visibility. They appear on every report card and <strong className="text-ink">none of
        them enter the ranking</strong>, which ranks terrain shape, slope and relief. So the
        properties that make a place a <em>base</em> site play no part in finding its Earth analog.
        Here is where that lands the sites the literature would name:
      </p>
      {sites.map(([site, row]) => (
        <div key={site} className="mt-3">
          <h3 className="font-semibold">{site}</h3>
          <BarList
            caption={`Rank of each canonical polar analog for ${site}`}
            max={100}
            reference={{ value: 50, label: "chance, 50%" }}
            bars={Object.entries(row.analogs).map(([name, r]) => ({
              label: name.replace(/,.*$/, ""),
              value: r.top_pct,
              display: `top ${r.top_pct}%`,
              highlight: r.top_pct <= 1,
              detail: `${name}: rank ${r.rank} of ${data.earth_tiles_ranked}${r.pushed_down ? "; pushed down by the environment checks" : ""}`,
            }))}
          />
        </div>
      ))}
      <p className="mt-3 text-muted">
        The Atacama comes back first, which is right. The McMurdo Dry Valleys — the most-cited
        terrestrial analog for the lunar poles — rank at or below chance, and part of that is our own
        doing: the tiles around them read as ice, so the environment checks that keep ice sheets out
        of the results push them down too.
      </p>
      {shared.length > 0 && (
        <p className="mt-2 text-xs text-muted">
          {shared.map(([tile, names]) => `${names.join(" and ")} share tile ${tile}`).join("; ")}.
          The Artemis regions are about 15 km across and our tiles{" "}
          {data.tile_resolution_km ?? 85} km, so neighbouring regions cannot always be told apart.
        </p>
      )}
    </>
  );
}

export function Methodology() {
  const [validation, setValidation] = useState<ValidationFile | null | undefined>(undefined);
  useEffect(() => {
    api.validation().then(setValidation);
  }, []);
  const model = validation?.analog_model;
  const crater = validation?.crater_retrieval;
  const known = validation?.known_analog_ranking;
  const polar = validation?.polar_analog_ranking;
  const v = validation as Record<string, unknown> | null | undefined;
  const marsRanking = v?.mars_analog_ranking as MarsRanking | undefined;
  const marsChannels = v?.mars_visual_channels as MarsChannels | undefined;
  const marsTraps = v?.mars_traps as MarsTraps | undefined;

  // Hints elsewhere link to /methodology#<section> (#53). The router does not
  // scroll to a hash, so do it here. The linked sections are static, above
  // anything that loads, so their position is already final on mount.
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash]);

  return (
    <article className="mx-auto max-w-2xl text-sm leading-relaxed">
      <h1 className="text-xl font-semibold">How AnalogAtlas decides two places are alike</h1>

      <h2 className="mt-6 font-semibold">Two stages</h2>
      <p className="mt-2 text-muted">
        Global screening splits the Moon and Earth's land into tiles of about 85 × 85 km. Each tile
        gets CLIP embeddings and physical measurements, and search runs across both bodies. The
        strongest new candidates then get a close study with radar surface roughness.
      </p>

      <h2 id="scoring" className="mt-6 scroll-mt-4 font-semibold">How a pair is scored</h2>
      <ul className="mt-2 list-disc pl-5 text-muted">
        <li><strong className="text-ink">Terrain</strong>: CLIP similarity of the two hillshades, averaged over four sun directions, shown as a percentile.</li>
        <li><strong className="text-ink">Physical</strong>: closeness of median slope and local relief, both measured at ~1.9 km per pixel.</li>
        <li><strong className="text-ink">Analog model</strong>: how much the Earth tile resembles known analog sites, from terrain, look, climate, vegetation and ice (#29).</li>
        <li><strong className="text-ink">Report card</strong>: every dimension compared on its own, grouped into holds, breaks down, and what Earth cannot reproduce.</li>
      </ul>

      <h2 id="glossary" className="mt-6 scroll-mt-4 font-semibold">What the words on the page mean</h2>
      <dl className="mt-2 grid gap-x-4 gap-y-2 text-muted sm:grid-cols-[10rem_1fr]">
        <dt className="font-medium text-ink">Terrain %</dt>
        <dd>How alike the two landscapes look in shape, as a percentile of all tiles. 99% means only 1% of tiles look more alike.</dd>
        <dt className="font-medium text-ink">Physical %</dt>
        <dd>How close the measured slope and relief are (plus albedo for Mars). 100% means the same values.</dd>
        <dt className="font-medium text-ink">Model %</dt>
        <dd>The analog model's percentile: how much the Earth tile resembles places already used as analogs.</dd>
        <dt className="font-medium text-ink">Look ↔ Measurements</dt>
        <dd>
          How the ranking mixes the two. At 0 it ranks by look alone, like an image-only AI. At 1 it
          ranks by measured slope and relief alone. The default, 0.3, is mostly look, with
          measurements as a strong check, and pushes down tiles that fail the ice, plant or water
          checks. Needs the live API; precomputed results use 0.3.
        </dd>
        <dt className="font-medium text-ink">New / known</dt>
        <dd>“Known” tiles lie within 150 km of a site already used as an analog. “New” ones don't: those are the discoveries the challenge asks for.</dd>
        <dt className="font-medium text-ink">Match</dt>
        <dd>On the report card, how close one property is on the two bodies. 100% means the same value.</dd>
        <dt className="font-medium text-ink">Holds / breaks down</dt>
        <dd>A property holds at a match of 60% or more; below that, the analogy breaks down there.</dd>
        <dt className="font-medium text-ink">Earth cannot reproduce</dt>
        <dd>Gravity, atmosphere, radiation: no place on Earth matches them, so they are listed as limits, not scored.</dd>
        <dt className="font-medium text-ink">Modelled / stand-in</dt>
        <dd>A modelled value comes from a model, not a measurement. A stand-in compares two different measurements of the same property: read it as a guide.</dd>
      </dl>

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

      <h2 className="mt-6 font-semibold">Does retrieval find craters nobody told it about?</h2>
      {validation === undefined ? (
        <p className="mt-2 text-muted">Loading…</p>
      ) : crater ? (
        <Craters data={crater} />
      ) : (
        <p className="mt-2 text-muted">
          Not exported yet. Run <code>scripts/05_validate.py</code>, then <code>scripts/03_export.py</code>.
        </p>
      )}

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

      <h2 className="mt-6 font-semibold">Where the known analogs rank for their role</h2>
      {validation === undefined ? (
        <p className="mt-2 text-muted">Loading…</p>
      ) : known ? (
        <KnownAnalogs data={known} />
      ) : (
        <p className="mt-2 text-muted">
          Not exported yet. Run <code>scripts/05_validate.py</code>, then <code>scripts/03_export.py</code>.
        </p>
      )}

      <h2 className="mt-6 font-semibold">Mars: the same tests on a second world</h2>
      {validation === undefined ? (
        <p className="mt-2 text-muted">Loading…</p>
      ) : marsRanking ? (
        <MarsAnalogs data={marsRanking} channels={marsChannels} traps={marsTraps} />
      ) : (
        <p className="mt-2 text-muted">
          Not exported yet. Build the mars index, then run <code>scripts/05_validate.py</code> and{" "}
          <code>scripts/03_export.py</code>.
        </p>
      )}

      <h2 className="mt-6 font-semibold">What we rank on, and what we only report</h2>
      {polar ? (
        <PolarAnalogs data={polar} />
      ) : (
        <p className="mt-2 text-muted">
          Ranking uses terrain shape, slope and relief. Illumination, permanent shadow and Earth
          visibility are reported on the card but do not affect the ranking.
        </p>
      )}

      <h2 className="mt-6 font-semibold">Why looking alike is not enough</h2>
      <p className="mt-2 text-muted">
        Most Earth tiles that look most like a lunar tile fail a physical check: they are ice sheets,
        forests, wetlands, or simply far steeper. See the <Link to="/traps" className="text-holds underline">lookalike traps</Link>.
      </p>

      <h2 id="numbers" className="mt-6 scroll-mt-4 font-semibold">What the numbers are not</h2>
      <ul className="mt-2 list-disc pl-5 text-muted">
        <li>The ranking score mixes a standardised visual score with physical closeness. It is not a 0–1 similarity, so it is never shown.</li>
        <li>Lunar surface temperature extremes are modelled from latitude (or, at the pole, from shadow), not measured.</li>
        <li>Atmosphere and gravity cannot be reproduced on Earth at all. They are listed as limits, not as low scores.</li>
        <li>The analog model was trained on 14 Moon sites; for the Moon alone, CLIP-only does as well. We say so rather than hide it.</li>
      </ul>
    </article>
  );
}
