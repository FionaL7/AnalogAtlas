/**
 * The real map (#24): Leaflet in EPSG:4326, one instance per body.
 *
 * Why Leaflet: NASA Moon Trek tiles and our GIBS requests are both plain
 * lat/lon (EPSG:4326). Leaflet renders that CRS natively and its zoom-0 grid
 * (2x1 tiles) is exactly Trek's. MapLibre only does Web Mercator or globe.
 *
 * Loaded lazily from MapPane, so first page load ships no map code.
 */
import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, WMSTileLayer, useMap } from "react-leaflet";

import { BASEMAPS } from "../../lib/basemaps";
import { percent } from "../../lib/format";
import { LEGEND_TICKS, scoreColour } from "../../lib/palette";
import type { TileCell } from "../../lib/types";
import type { MapMarker, MapPaneProps } from "./MapPane";

const WORLD = L.latLngBounds([-90, -180], [90, 180]);

/** The full tile grid as faint outlines. Imperative, on one canvas: ~12k
 * rectangles as React components would re-reconcile on every render. */
function GridLayer({ cells }: { cells: TileCell[] }) {
  const map = useMap();
  useEffect(() => {
    if (!cells.length) return;
    const renderer = L.canvas({ padding: 0.5 });
    const group = L.layerGroup(
      cells.map((c) =>
        L.rectangle(
          [[c.bbox[1], c.bbox[0]], [c.bbox[3], c.bbox[2]]],
          { renderer, weight: 0.5, color: "#ffffff", opacity: 0.12, fill: false, interactive: false },
        ),
      ),
    );
    group.addTo(map);
    return () => {
      group.remove();
    };
  }, [map, cells]);
  return null;
}

/** Re-frame when the results or the focus point change, not on every render. */
function Framing({ markers, focus }: { markers: MapMarker[]; focus?: MapPaneProps["focus"] }) {
  const map = useMap();
  const key = markers.map((m) => m.tile_id).join(",");
  const flat = focus?.lat;
  const flon = focus?.lon;
  useEffect(() => {
    if (flat !== undefined && flon !== undefined) {
      map.setView([flat, flon], 3);
    } else if (markers.length) {
      map.fitBounds(L.latLngBounds(markers.map((m) => [m.lat, m.lon])).pad(0.3), { maxZoom: 4 });
    }
    // `markers` is tracked through `key` on purpose: same tiles, no re-frame.
  }, [map, key, flat, flon]);
  return null;
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-6 left-2 z-[1000] rounded bg-base/85 px-2 py-1.5 text-[11px] text-ink">
      <p className="mb-1 text-muted">Visual similarity (percentile)</p>
      <div
        className="h-2 w-40 rounded-sm"
        style={{ background: `linear-gradient(to right, ${LEGEND_TICKS.map(scoreColour).join(",")})` }}
        aria-hidden
      />
      <div className="flex w-40 justify-between tabular-nums">
        {LEGEND_TICKS.map((t) => (
          <span key={t}>{percent(t)}</span>
        ))}
      </div>
      <p className="mt-1 text-muted">Dashed outline = known analog site</p>
    </div>
  );
}

export default function LeafletMap({ body, markers, selected, onSelect, grid, focus }: MapPaneProps) {
  const base = BASEMAPS[body];
  const scored = markers.some((m) => m.weight !== undefined);

  return (
    <div
      role="region"
      aria-label={`${body === "moon" ? "Moon" : "Earth"} map`}
      className="relative h-full min-h-[18rem] overflow-hidden rounded-lg border border-edge"
    >
      <MapContainer
        crs={L.CRS.EPSG4326}
        center={[0, 0]}
        zoom={1}
        minZoom={0}
        maxZoom={base.maxNativeZoom + 2}
        maxBounds={WORLD}
        maxBoundsViscosity={1}
        preferCanvas
        className="h-full w-full"
        style={{ background: "var(--color-base)" }}
      >
        {base.kind === "xyz" ? (
          <TileLayer url={base.url} maxNativeZoom={base.maxNativeZoom} noWrap bounds={WORLD}
                     attribution={base.attribution} />
        ) : (
          <WMSTileLayer url={base.url} maxNativeZoom={base.maxNativeZoom} noWrap bounds={WORLD}
                        attribution={base.attribution}
                        params={{ layers: base.layers ?? "", format: "image/jpeg", version: "1.3.0" }} />
        )}

        {grid && <GridLayer cells={grid} />}

        {markers.map((m) => {
          const isSelected = m.tile_id === selected;
          return (
            <CircleMarker
              key={m.tile_id}
              center={[m.lat, m.lon]}
              radius={isSelected ? 9 : 6}
              pathOptions={{
                color: isSelected ? "#ffffff" : "#0b0d12",
                weight: isSelected ? 3 : 1,
                // known sites get a dashed outline, so "new vs known" is not colour alone
                dashArray: m.isNew === false ? "3 2" : undefined,
                fillColor: m.weight === undefined ? "#ffffff" : scoreColour(m.weight),
                fillOpacity: 0.9,
              }}
              eventHandlers={{ click: () => onSelect?.(m.tile_id) }}
            >
              <Tooltip>
                {m.label ?? m.tile_id}
                {m.weight !== undefined && ` · ${percent(m.weight)}`}
                {m.isNew && " · new"}
              </Tooltip>
            </CircleMarker>
          );
        })}

        <Framing markers={markers} focus={focus} />
      </MapContainer>

      {scored && <Legend />}
    </div>
  );
}
