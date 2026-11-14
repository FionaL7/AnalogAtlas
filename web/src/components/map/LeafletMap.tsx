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
import {
  CircleMarker, MapContainer, TileLayer, Tooltip, WMSTileLayer, useMap, useMapEvents,
} from "react-leaflet";

import { BASEMAPS } from "../../lib/basemaps";
import { percent } from "../../lib/format";
import { LEGEND_TICKS, scoreColour } from "../../lib/palette";
import { CRS_MOON_SOUTH_POLAR, polarCellCorners } from "../../lib/polar";
import { isPolar, type Body, type TileCell } from "../../lib/types";
import type { MapMarker, MapPaneProps } from "./MapPane";

const WORLD = L.latLngBounds([-90, -180], [90, 180]);

const BODY_LABEL: Record<Body, string> = {
  moon: "Moon",
  moon_polar: "Moon south pole",
  earth: "Earth",
};

/** The full tile grid as faint outlines. Imperative, on one canvas: ~12k
 * rectangles as React components would re-reconcile on every render.
 *
 * Polar cells are squares in projected metres, not lat/lon boxes, so they are
 * drawn as polygons through their four corners — a rectangle would be wrong.
 */
function GridLayer({ cells, polar }: { cells: TileCell[]; polar: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!cells.length) return;
    const renderer = L.canvas({ padding: 0.5 });
    const style = {
      renderer,
      weight: 0.5,
      color: "#ffffff",
      opacity: 0.12,
      fill: false,
      interactive: false,
    };
    const group = L.layerGroup(
      cells.map((c) =>
        polar && c.xy
          ? L.polygon(polarCellCorners(c.xy), style)
          : L.rectangle([[c.bbox[1], c.bbox[0]], [c.bbox[3], c.bbox[2]]], style),
      ),
    );
    group.addTo(map);
    return () => {
      group.remove();
    };
  }, [map, cells, polar]);
  return null;
}

/** Re-frame when the results or the focus point change, not on every render. */
function Framing({
  markers,
  focus,
  polar,
}: {
  markers: MapMarker[];
  focus?: MapPaneProps["focus"];
  polar: boolean;
}) {
  const map = useMap();
  const key = markers.map((m) => m.tile_id).join(",");
  const flat = focus?.lat;
  const flon = focus?.lon;
  useEffect(() => {
    if (flat !== undefined && flon !== undefined) {
      map.setView([flat, flon], polar ? 4 : 3);
    } else if (markers.length) {
      map.fitBounds(L.latLngBounds(markers.map((m) => [m.lat, m.lon])).pad(0.3), {
        maxZoom: polar ? 5 : 4,
      });
    } else if (polar) {
      map.setView([-90, 0], 2);
    }
    // `markers` is tracked through `key` on purpose: same tiles, no re-frame.
  }, [map, key, flat, flon, polar]);
  return null;
}

/** Map clicks that miss every marker. Markers stop their own clicks from
 * bubbling, so picking a candidate never also starts a new search. */
function ClickToSearch({ onMapClick }: { onMapClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click: (e) => onMapClick(e.latlng.lat, ((e.latlng.lng + 540) % 360) - 180),
  });
  return null;
}

function Legend({ title }: { title: string }) {
  return (
    <div className="pointer-events-none absolute bottom-6 left-2 z-[1000] rounded bg-base/85 px-2 py-1.5 text-[11px] text-ink">
      <p className="mb-1 text-muted">{title}</p>
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

export default function LeafletMap({
  body, markers, selected, onSelect, grid, focus, onMapClick,
  legend = "Visual similarity (percentile)",
}: MapPaneProps) {
  const base = BASEMAPS[body];
  const scored = markers.some((m) => m.weight !== undefined);
  const polar = isPolar(body);
  // No tile `bounds` on the polar pane. Leaflet derives the valid-tile box by
  // projecting the NW and SE corners of a lat/lon rectangle, which collapses
  // to a sliver under a polar projection and hides almost every tile. The
  // layer 404s outside its own footprint anyway, which is the correct limit.
  const bounds = polar ? undefined : WORLD;

  return (
    <div
      role="region"
      aria-label={`${BODY_LABEL[body]} map`}
      className={`relative h-full min-h-[18rem] overflow-hidden rounded-lg border border-edge ${
        onMapClick ? "[&_.leaflet-container]:cursor-crosshair" : ""}`}
    >
      <MapContainer
        // The pole needs its own projection, not a different view of the same
        // one — see lib/polar.ts.
        crs={polar ? CRS_MOON_SOUTH_POLAR : L.CRS.EPSG4326}
        center={polar ? [-90, 0] : [0, 0]}
        zoom={polar ? 2 : 1}
        minZoom={polar ? 1 : 0}
        maxZoom={base.maxNativeZoom + 2}
        maxBounds={polar ? undefined : WORLD}
        maxBoundsViscosity={1}
        preferCanvas
        className="h-full w-full"
        style={{ background: "var(--color-base)" }}
      >
        {base.kind === "xyz" ? (
          <TileLayer url={base.url} maxNativeZoom={base.maxNativeZoom} noWrap bounds={bounds}
                     attribution={base.attribution} />
        ) : (
          <WMSTileLayer url={base.url} maxNativeZoom={base.maxNativeZoom} noWrap bounds={bounds}
                        attribution={base.attribution}
                        params={{ layers: base.layers ?? "", format: "image/jpeg", version: "1.3.0" }} />
        )}

        {grid && <GridLayer cells={grid} polar={polar} />}

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
              bubblingMouseEvents={false}
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

        <Framing markers={markers} focus={focus} polar={polar} />
        {onMapClick && <ClickToSearch onMapClick={onMapClick} />}
      </MapContainer>

      {scored && <Legend title={legend} />}
    </div>
  );
}
