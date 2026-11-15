/** Field guides: one page per Moon or Mars target site, base regions first. */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { TileChip } from "../components/TileChip";
import * as api from "../lib/api";
import { nearestCell } from "../lib/guide";
import { percent } from "../lib/format";
import type { RadarFile, Site, TileCell, TrapsFile } from "../lib/types";

export function Sites() {
  const [sites, setSites] = useState<Site[]>([]);
  const [polar, setPolar] = useState<TileCell[]>([]);
  const [radar, setRadar] = useState<RadarFile | null>(null);
  const [traps, setTraps] = useState<TrapsFile | null>(null);
  useEffect(() => {
    api.sites().then(setSites);
    api.tiles("moon_polar").then(setPolar);
    api.radar().then(setRadar);
    api.traps().then(setTraps);
  }, []);

  const lunar = sites.filter((s) => s.body !== "earth");
  const groups: [string, Site[]][] = [
    ["Artemis candidate base regions", lunar.filter((s) => s.is_base_region)],
    ["Other Moon sites", lunar.filter((s) => !s.is_base_region && s.body !== "mars")],
    ["Mars landing and exploration sites", lunar.filter((s) => s.body === "mars")],
  ];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">Field guides</h1>
        <p className="mt-2 text-sm text-muted">
          One page per Moon or Mars site: what the ground is like, the strongest new Earth analogs
          with what to test there, and the lookalikes to avoid. Lunar sites add radar roughness from
          LRO Mini-RF.
        </p>
      </header>
      {groups.map(([title, list]) => list.length > 0 && (
        <section key={title}>
          <h2 className="text-sm uppercase tracking-wide text-muted">{title}</h2>
          <ul className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((s) => {
              const cell = s.body === "moon_polar" ? nearestCell(polar, s.lat, s.lon) : null;
              const cpr = radar?.[s.id]?.cpr_median;
              const nTraps = traps?.by_site[s.id]?.length;
              return (
                <li key={s.id}>
                  <Link to={`/sites/${s.id}`}
                        className="grid grid-cols-[4.5rem_1fr] gap-3 rounded-lg border border-edge bg-panel p-3 hover:border-muted">
                    <TileChip body={s.body} tile={cell ?? s} layer="shade" label={`${s.name} terrain`} />
                    <span className="min-w-0">
                      <span className="block font-medium">{s.name}</span>
                      <span className="mt-1 block text-xs text-muted">
                        {cell?.illum_max != null && <>sunlit up to {percent(cell.illum_max)} · </>}
                        {cell?.psr_frac != null && <>{percent(cell.psr_frac)} permanent shadow · </>}
                        {cpr != null && <>radar CPR {cpr.toFixed(2)} · </>}
                        {nTraps != null && <>{nTraps} traps</>}
                        {s.in_index === false && "outside the index"}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
