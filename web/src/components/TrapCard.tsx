/**
 * One lookalike trap (#30): an Earth tile an image-only AI would pick for a
 * lunar tile, and the physical reason it is wrong. Shown in terrain shape
 * (hillshade), the channel the lookalike was found in.
 */
import { coords, percent } from "../lib/format";
import type { Trap } from "../lib/types";
import { TileChip } from "./TileChip";

export function TrapCard({ trap, compact }: { trap: Trap; compact?: boolean }) {
  const earth = { lat: trap.earth_lat, lon: trap.earth_lon };
  const moon = { lat: trap.src_lat, lon: trap.src_lon };
  return (
    <article className="rounded-lg border border-edge bg-panel p-3">
      <div className={`grid gap-2 ${compact ? "grid-cols-[4rem_4rem_1fr]" : "grid-cols-2 sm:grid-cols-[8rem_8rem_1fr]"}`}>
        <div>
          <TileChip body="earth" tile={earth} layer="shade" label={`Earth lookalike at ${coords(earth.lat, earth.lon)}`} />
          {!compact && <p className="mt-1 text-[11px] text-muted">Earth · {coords(earth.lat, earth.lon)}</p>}
        </div>
        <div>
          <TileChip body={trap.src_body} tile={moon} layer="shade" label={`Lunar tile at ${coords(moon.lat, moon.lon)}`} />
          {!compact && (
            <p className="mt-1 text-[11px] text-muted">
              {trap.src_body === "moon_polar" ? "South pole" : "Moon"} · {coords(moon.lat, moon.lon)}
            </p>
          )}
        </div>
        <div className={compact ? "min-w-0" : "col-span-2 min-w-0 sm:col-span-1"}>
          <p className="text-sm">
            Looks alike: <strong>#{trap.visual_rank}</strong> lookalike
            <span className="text-muted"> ({percent(trap.visual_pct)} percentile)</span>
          </p>
          <ul className="mt-1 flex flex-col gap-1">
            {trap.breakers.map((b) => (
              <li key={b.id} className="text-sm">
                <span className={`mr-1 rounded px-1.5 py-0.5 text-xs ${b.environment ? "bg-limit/20 text-limit" : "bg-breaks/20 text-breaks"}`}>
                  {b.label}
                </span>
                {!compact && <span className="text-muted">{b.reason}</span>}
              </li>
            ))}
          </ul>
          {!compact && (
            <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
              <div>
                <dt className="text-muted">Image only</dt>
                <dd className="tabular-nums">rank {trap.visual_rank}</dd>
              </div>
              <div>
                <dt className="text-muted" title="Our search: looks + slope/relief, ice, plants and water pushed down">Our search</dt>
                <dd className="tabular-nums">rank {trap.physics_rank.toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-muted" title="#29 analog model, environment-aware">Analog model</dt>
                <dd className="tabular-nums">{percent(trap.model_score_pct)}</dd>
              </div>
            </dl>
          )}
        </div>
      </div>
    </article>
  );
}
