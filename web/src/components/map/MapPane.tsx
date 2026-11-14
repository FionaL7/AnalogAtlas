/**
 * The map boundary. The rest of the app only knows these props.
 *
 * The map itself is Leaflet (#24, see LeafletMap.tsx), loaded lazily so the
 * first page load ships no map code (§6).
 */
import { Suspense, lazy } from "react";

import type { Body, TileCell } from "../../lib/types";

export interface MapMarker {
  tile_id: string;
  lat: number;
  lon: number;
  /** 0-1; drives the marker colour, and is always also printed in the panel. */
  weight?: number;
  label?: string;
  /** false = a known analog site (dashed outline); true = a new candidate. */
  isNew?: boolean;
}

export interface MapPaneProps {
  body: Body;
  markers: MapMarker[];
  selected?: string | null;
  onSelect?: (tileId: string) => void;
  /** Full tile grid drawn as faint outlines (from the static export). */
  grid?: TileCell[];
  /** Centre here instead of fitting to the markers (e.g. the source site). */
  focus?: { lat: number; lon: number };
}

const LeafletMap = lazy(() => import("./LeafletMap"));

function Loading({ body }: { body: Body }) {
  return (
    <div className="grid h-full min-h-[18rem] place-content-center rounded-lg border border-edge bg-panel text-sm text-muted">
      Loading {body} map…
    </div>
  );
}

export function MapPane(props: MapPaneProps) {
  return (
    <Suspense fallback={<Loading body={props.body} />}>
      <LeafletMap {...props} />
    </Suspense>
  );
}
