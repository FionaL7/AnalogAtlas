/**
 * One 85 km tile as a picture, rebuilt from NASA's tile services (lib/chips.ts).
 * Always square, so Earth and Moon chips line up side by side at the same
 * ground scale.
 */
import { chipFor, type TileLike } from "../lib/chips";
import type { Body, Layer } from "../lib/types";

interface Props {
  body: Body;
  tile: TileLike;
  layer?: Layer;
  /** Short description for screen readers, e.g. "Earth tile near 24.1°S 69.9°W". */
  label: string;
  className?: string;
  caption?: boolean;
}

export function TileChip({ body, tile, layer = "img", label, className = "", caption }: Props) {
  const chip = chipFor(body, tile, layer);
  return (
    <figure className={`flex flex-col gap-1 ${className}`}>
      <div
        role="img"
        aria-label={`${label} (${chip.source})`}
        className="relative aspect-square w-full overflow-hidden rounded border border-edge bg-black"
      >
        {chip.pieces.map((p) => (
          <img
            key={p.url}
            src={p.url}
            alt=""
            loading="lazy"
            decoding="async"
            draggable={false}
            className="absolute max-w-none select-none"
            style={{
              left: `${p.left * 100}%`,
              top: `${p.top * 100}%`,
              width: `${p.width * 100}%`,
              height: `${p.height * 100}%`,
            }}
          />
        ))}
      </div>
      {caption && <figcaption className="text-[11px] text-muted">{chip.source}</figcaption>}
    </figure>
  );
}
