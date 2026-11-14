/**
 * The map boundary.
 *
 * The map library is still an open decision (MapLibre vs Leaflet — see
 * docs/PLAN.md). Everything else in the app is built against these props, so
 * swapping this one component in is the whole change. Until then it plots tiles
 * on a plain equirectangular panel: no projection, no tile server, no network.
 */
import type { Body } from "../../lib/types";

export interface MapMarker {
  tile_id: string;
  lat: number;
  lon: number;
  /** 0-1; drives marker size, and is always also printed in the panel. */
  weight?: number;
  label?: string;
  isNew?: boolean;
}

interface Props {
  body: Body;
  markers: MapMarker[];
  selected?: string | null;
  onSelect?: (tileId: string) => void;
}

export function MapPane({ body, markers, selected, onSelect }: Props) {
  return (
    <div className="relative h-full min-h-[18rem] overflow-hidden rounded-lg border border-edge bg-panel">
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255,255,255,.06) 1px, transparent 1px)," +
            "linear-gradient(to bottom, rgba(255,255,255,.06) 1px, transparent 1px)",
          backgroundSize: "8.333% 16.666%",
        }}
        aria-hidden
      />
      <p className="absolute left-3 top-2 text-xs uppercase tracking-wide text-muted">
        {body} · placeholder projection
      </p>

      <ul className="absolute inset-0 list-none">
        {markers.map((m) => {
          const size = 8 + (m.weight ?? 0.5) * 16;
          const isSelected = selected === m.tile_id;
          return (
            <li
              key={m.tile_id}
              className="absolute"
              style={{ left: `${((m.lon + 180) / 360) * 100}%`, top: `${((90 - m.lat) / 180) * 100}%` }}
            >
              <button
                type="button"
                onClick={() => onSelect?.(m.tile_id)}
                aria-label={`${m.label ?? m.tile_id}${m.isNew ? ", new candidate" : ""}`}
                aria-pressed={isSelected}
                className={[
                  "-translate-x-1/2 -translate-y-1/2 rounded-full border transition-transform",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
                  isSelected ? "border-ink bg-ink/80" : "border-ink/60 bg-ink/25 hover:scale-110",
                ].join(" ")}
                style={{ width: size, height: size }}
              />
            </li>
          );
        })}
      </ul>

      {markers.length === 0 && (
        <p className="absolute inset-0 grid place-content-center text-sm text-muted">
          Pick a site to see candidate analogs.
        </p>
      )}
    </div>
  );
}
