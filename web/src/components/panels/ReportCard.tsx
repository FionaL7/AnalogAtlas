/**
 * The report card: the two tiles side by side, then dimension by dimension
 * where the analogy holds and where it breaks down, then what to test there.
 * Rows arrive already scored from Python (§4.3) and are only grouped here.
 * Every bar also prints its number, so colour is never the only carrier of
 * meaning (§6).
 */
import { useState } from "react";

import { sourceBodyOf, type TileLike } from "../../lib/chips";
import { GROUP_LABEL, coords, groupBreakdown, percent, type Group } from "../../lib/format";
import {
  BODY_NAME, WORLD_NAME, type BreakdownRow, type FieldTests, type Layer, type TwinsResponse,
} from "../../lib/types";
import { TileChip } from "../TileChip";

const GROUP_ORDER: Group[] = ["holds", "breaks", "cannot-reproduce", "no-equivalent"];

const BAR_COLOUR: Record<Group, string> = {
  holds: "bg-holds",
  breaks: "bg-breaks",
  "cannot-reproduce": "bg-limit",
  "no-equivalent": "bg-edge",
};

/** A model or a stand-in must never read as a measurement (§6), so those
 * rows carry a tag. Measured rows are the default and stay untagged. */
const BASIS_TAG: Partial<Record<NonNullable<BreakdownRow["basis"]>, [string, string]>> = {
  modelled: ["modelled", "This value comes from a model, not a measurement"],
  proxy: ["stand-in", "Two different measurements standing in for the same property: read it as a guide"],
};

function Row({ row, group }: { row: BreakdownRow; group: Group }) {
  const tag = row.basis && row.kind !== "earth_limit" ? BASIS_TAG[row.basis] : undefined;
  return (
    <tr className="border-t border-edge align-top">
      <th scope="row" className="py-2 pr-3 text-left font-medium">
        {row.dimension}
        {tag && (
          <span title={tag[1]}
                className="ml-1.5 rounded border border-edge px-1 py-px align-middle text-[10px] font-normal uppercase tracking-wide text-muted">
            {tag[0]}
          </span>
        )}
        {row.note && <span className="mt-0.5 block text-xs font-normal text-muted">{row.note}</span>}
      </th>
      <td className="py-2 pr-3 tabular-nums">{row.moon}</td>
      <td className="py-2 pr-3 tabular-nums">{row.earth}</td>
      <td className="w-32 py-2">
        <span className="flex items-center gap-2">
          <span className="h-1.5 flex-1 overflow-hidden rounded bg-edge" aria-hidden>
            <span
              className={`block h-full ${BAR_COLOUR[group]}`}
              style={{ width: `${(row.match ?? 0) * 100}%` }}
            />
          </span>
          <span className="w-10 text-right text-xs tabular-nums">{percent(row.match)}</span>
        </span>
      </td>
    </tr>
  );
}

const asTile = (rec: Record<string, unknown>): TileLike | null =>
  typeof rec.lat === "number" && typeof rec.lon === "number" ? (rec as unknown as TileLike) : null;

function SideBySide({ data }: { data: TwinsResponse }) {
  const [layer, setLayer] = useState<Layer>("img");
  const earth = asTile(data.earth);
  const moon = asTile(data.moon);
  if (!earth || !moon) return null;
  const lunar = sourceBodyOf(data.moon);
  return (
    <div className="mt-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs uppercase tracking-wide text-muted">Side by side, same 85 km scale</h3>
        <div role="radiogroup" aria-label="Picture layer" className="flex rounded border border-edge text-xs">
          {(["img", "shade"] as Layer[]).map((l) => (
            <button
              key={l}
              type="button"
              role="radio"
              aria-checked={layer === l}
              onClick={() => setLayer(l)}
              className={`px-2 py-0.5 ${layer === l ? "bg-edge text-ink" : "text-muted hover:text-ink"}`}
            >
              {l === "img" ? "Imagery" : "Terrain shape"}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <p className="mb-1 text-xs text-muted">Earth · {coords(earth.lat, earth.lon)}</p>
          <TileChip body="earth" tile={earth} layer={layer} caption
                    label={`Earth tile near ${coords(earth.lat, earth.lon)}`} />
        </div>
        <div>
          <p className="mb-1 text-xs text-muted">
            {BODY_NAME[lunar]} · {coords(moon.lat, moon.lon)}
          </p>
          <TileChip body={lunar} tile={moon} layer={layer} caption
                    label={`${WORLD_NAME[lunar]} tile near ${coords(moon.lat, moon.lon)}`} />
        </div>
      </div>
      {lunar === "moon_polar" && layer === "img" && (
        <p className="mt-1 text-[11px] text-muted">
          The pole shows terrain shape only: the imagery mosaic covers 85.5–90°S and much of it is in
          permanent shadow.
        </p>
      )}
    </div>
  );
}

export function FieldTestList({ tests }: { tests: FieldTests }) {
  return (
    <div className="mt-6">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">What to test here</h3>
      {tests.tests.length === 0 ? (
        <p className="mt-2 text-sm text-muted">
          No dimension holds strongly enough here to recommend a field test.
        </p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {tests.tests.map((t) => (
            <li key={t.title} className="rounded border border-holds/30 bg-holds/5 p-3">
              <p className="font-medium">{t.title}</p>
              <p className="mt-0.5 text-xs text-holds">Reduces the risk of: {t.risk.toLowerCase()}</p>
              <p className="mt-1 text-sm text-muted">{t.detail}</p>
              <p className="mt-1 text-[11px] text-muted">
                Based on: {t.based_on.join(", ")} (weakest match {percent(t.strength)})
              </p>
            </li>
          ))}
        </ul>
      )}
      {tests.avoid.length > 0 && (
        <>
          <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">
            Don’t rely on this site for
          </h4>
          <ul className="mt-1 list-disc pl-5 text-sm text-muted">
            {tests.avoid.map((a) => <li key={a.dimension}>{a.reason}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}

export function ReportCard({ data }: { data: TwinsResponse }) {
  const groups = groupBreakdown(data.breakdown);
  const world = WORLD_NAME[sourceBodyOf(data.moon)];
  return (
    <section className="p-4" aria-label="Report card">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Report card</h2>
        {data.model_score != null && (
          <span className="text-xs text-muted" title={`Analog model (#29): how much this Earth tile resembles known ${world} analog sites, as a percentile of all Earth tiles`}>
            Analog model: <strong className="text-ink">{percent(data.model_score)}</strong> percentile
          </span>
        )}
      </div>
      <p className="mt-1 font-mono text-xs text-muted">
        {String(data.moon.tile_id)} ↔ {String(data.earth.tile_id)}
      </p>
      {data.climate === null && (
        <p className="mt-2 rounded border border-breaks/40 bg-breaks/10 px-2 py-1 text-xs text-breaks">
          Climate rows unavailable — NASA POWER did not answer. Everything else is unaffected.
        </p>
      )}

      <SideBySide data={data} />

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <caption className="sr-only">
            Dimension-by-dimension comparison of the {world} tile and the Earth tile
          </caption>
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="pb-2 pr-3">Dimension</th>
              <th scope="col" className="pb-2 pr-3">{world}</th>
              <th scope="col" className="pb-2 pr-3">Earth</th>
              <th scope="col" className="pb-2">Match</th>
            </tr>
          </thead>
          {GROUP_ORDER.filter((g) => groups[g].length > 0).map((g) => (
            <tbody key={g}>
              <tr>
                <td colSpan={4} className="pt-4 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">
                  {GROUP_LABEL[g]}
                </td>
              </tr>
              {groups[g].map((row) => (
                <Row key={row.dimension} row={row} group={g} />
              ))}
            </tbody>
          ))}
        </table>
      </div>

      {data.field_tests && <FieldTestList tests={data.field_tests} />}

      <p className="mt-4 text-xs text-muted">
        {world === "Mars"
          ? "Mars surface temperatures are modelled, not measured. Rows tagged “stand-in” compare two different measurements, so read them as a guide. "
          : "Lunar surface temperatures are modelled, not measured. "}
        Slope and relief are measured at the same ~1.9 km baseline on both bodies, which is what
        makes them comparable.
      </p>
    </section>
  );
}
