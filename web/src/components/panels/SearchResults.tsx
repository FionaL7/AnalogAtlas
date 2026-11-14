/**
 * Text or image search results within one body. The raw score is a ranking
 * value, so only the rank is shown. Picking a result makes it the source of a
 * cross-body analog search.
 */
import { coords } from "../../lib/format";
import type { Body, SearchHit } from "../../lib/types";
import { TileChip } from "../TileChip";

interface Props {
  body: Body;
  label: string;
  hits: SearchHit[];
  onPick: (hit: SearchHit) => void;
  onClear: () => void;
}

const BODY_NAME: Record<Body, string> = {
  moon: "the Moon",
  moon_polar: "the lunar south pole",
  earth: "Earth",
};

export function SearchResults({ body, label, hits, onPick, onClear }: Props) {
  return (
    <section aria-label="Search results">
      <div className="flex items-start justify-between gap-2 border-t border-edge px-4 py-2">
        <p className="text-xs text-muted">
          <span className="uppercase tracking-wide">{hits.length} matches on {BODY_NAME[body]}</span>
          <span className="mt-0.5 block normal-case">for “{label}”. Pick one to find its analogs.</span>
        </p>
        <button type="button" onClick={onClear} className="text-xs text-muted underline hover:text-ink">
          clear
        </button>
      </div>
      <ol className="divide-y divide-edge">
        {hits.map((hit, i) => (
          <li key={hit.tile_id}>
            <button
              type="button"
              onClick={() => onPick(hit)}
              className="flex w-full items-center gap-3 px-4 py-2 text-left hover:bg-edge/40"
            >
              <span className="w-5 text-xs text-muted">{i + 1}</span>
              <TileChip body={body} tile={hit} label={`Tile ${hit.tile_id}`} className="w-12 shrink-0" />
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{coords(hit.lat, hit.lon)}</span>
                <span className="block truncate font-mono text-xs text-muted">{hit.tile_id}</span>
              </span>
              {hit.known_analog && (
                <span className="max-w-[8rem] truncate rounded bg-edge px-1.5 py-0.5 text-xs text-muted">
                  known: {hit.known_analog}
                </span>
              )}
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
