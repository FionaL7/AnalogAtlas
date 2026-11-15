/** The analog portfolio (#31): the fewest Earth sites that together cover
 * every dimension of one Moon or Mars site. No single site matches on every
 * count, so this shows which site stands in for which part of the target. */
import { coords, percent } from "../../lib/format";
import { WORLD_NAME, type PortfolioFile } from "../../lib/types";

export function Portfolio({ data, siteName }: { data: PortfolioFile; siteName: string }) {
  const label = Object.fromEntries(data.dimensions.map((d) => [d.id, d.label]));
  const orderOf = Object.fromEntries(data.sites.map((s) => [s.tile_id, s.order]));
  const total = data.dimensions.length;
  const covered = total - data.uncovered.length;
  const single = data.best_single_site?.covers;
  const mars = data.body === "mars";

  return (
    <div className="flex flex-col gap-4">
      <p className=" text-sm text-muted">
        No single Earth site matches {siteName} on every count. These{" "}
        <strong className="text-ink">{data.sites.length}</strong> together cover{" "}
        <strong className="text-ink">{covered} of {total}</strong> dimensions
        {single != null && single < total && <>; the best single site covers only {single}</>}.
        {mars
          ? "Forests and lakes are never picked; ice only where the Mars site has ground ice."
          : "Ice sheets, forests and lakes are never picked."}
      </p>

      <ol className="grid gap-3 md:grid-cols-2">
        {data.sites.map((s) => (
          <li key={s.tile_id} className="rounded-lg border border-edge bg-panel p-3">
            <h3 className="font-semibold">#{s.order} · {coords(s.lat, s.lon)}</h3>
            <p className="text-xs text-muted">{s.known_analog ? `Near ${s.known_analog}` : "New candidate"}</p>
            <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={`Site ${s.order} covers`}>
              {s.covers.map((d) => (
                <li key={d}
                    className={`rounded border px-1.5 py-0.5 text-xs ${s.adds.includes(d)
                      ? "border-holds text-ink" : "border-edge text-muted"}`}>
                  {label[d] ?? d}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>

      <table className="w-full text-left text-sm">
        <thead className="text-xs text-muted">
          <tr><th className="py-1 pr-3 font-normal">Dimension</th>
              <th className="py-1 pr-3 font-normal">On {mars ? "Mars" : `the ${WORLD_NAME[data.body] ?? "Moon"}`}</th>
              <th className="py-1 font-normal">Covered by</th></tr>
        </thead>
        <tbody>
          {data.dimensions.map((d) => (
            <tr key={d.id} className="border-t border-edge align-top">
              <td className="py-1.5 pr-3">{d.label}</td>
              <td className="py-1.5 pr-3 text-muted">{d.moon === "-" ? "—" : d.moon}</td>
              <td className="py-1.5">
                {d.covered_by ? <>site #{orderOf[d.covered_by]}</> : <span className="text-breaks">not covered</span>}
                {d.earth_best_only && (
                  <p className="text-[11px] text-breaks">
                    Nowhere on Earth fully matches; this is the closest Earth gets ({percent(d.earth_best)}).
                  </p>
                )}
                {d.id === "access" && (
                  <p className="text-[11px] text-muted">Practical, not likeness: a field team must get there.</p>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
