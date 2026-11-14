/**
 * The report card: dimension by dimension, where the analogy holds and where it
 * breaks down. Rows arrive already scored from Python (§4.3) and are only
 * grouped here. Every bar also prints its number, so colour is never the only
 * carrier of meaning (§6).
 */
import { GROUP_LABEL, groupBreakdown, percent, type Group } from "../../lib/format";
import type { BreakdownRow, TwinsResponse } from "../../lib/types";

const GROUP_ORDER: Group[] = ["holds", "breaks", "cannot-reproduce", "no-equivalent"];

const BAR_COLOUR: Record<Group, string> = {
  holds: "bg-holds",
  breaks: "bg-breaks",
  "cannot-reproduce": "bg-limit",
  "no-equivalent": "bg-edge",
};

function Row({ row, group }: { row: BreakdownRow; group: Group }) {
  return (
    <tr className="border-t border-edge align-top">
      <th scope="row" className="py-2 pr-3 text-left font-medium">
        {row.dimension}
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

export function ReportCard({ data }: { data: TwinsResponse }) {
  const groups = groupBreakdown(data.breakdown);
  return (
    <section className="p-4">
      <h2 className="text-sm uppercase tracking-wide text-muted">Report card</h2>
      <p className="mt-1 font-mono text-xs text-muted">
        {String(data.moon.tile_id)} ↔ {String(data.earth.tile_id)}
      </p>
      {data.climate === null && (
        <p className="mt-2 rounded border border-breaks/40 bg-breaks/10 px-2 py-1 text-xs text-breaks">
          Climate rows unavailable — NASA POWER did not answer. Everything else is unaffected.
        </p>
      )}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <caption className="sr-only">
            Dimension-by-dimension comparison of the lunar tile and the Earth tile
          </caption>
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="pb-2 pr-3">Dimension</th>
              <th scope="col" className="pb-2 pr-3">Moon</th>
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

      <p className="mt-4 text-xs text-muted">
        Lunar surface temperatures are modelled, not measured. Slope and relief are measured at the
        same ~1.9 km baseline on both bodies, which is what makes them comparable.
      </p>
    </section>
  );
}
