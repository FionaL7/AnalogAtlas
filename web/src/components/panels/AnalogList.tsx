/**
 * Ranked analogs for one site.
 *
 * Shows `visual_cos_scaled` and `physical` — never the raw `score`, which is a
 * ranking value and would overclaim a match (§4.3, §7). Candidates that are not
 * already-known analog sites are flagged "new" and sorted first: that is what
 * the challenge actually asks for.
 */
import { coords, newFirst, percent } from "../../lib/format";
import type { AnalogHit } from "../../lib/types";

interface Props {
  hits: AnalogHit[];
  selected?: string | null;
  onSelect?: (tileId: string) => void;
}

export function AnalogList({ hits, selected, onSelect }: Props) {
  if (hits.length === 0) {
    return <p className="p-4 text-sm text-muted">No candidates yet.</p>;
  }
  return (
    <ol className="divide-y divide-edge">
      {newFirst(hits).map((hit, i) => (
        <li key={hit.tile_id}>
          <button
            type="button"
            onClick={() => onSelect?.(hit.tile_id)}
            aria-current={selected === hit.tile_id}
            className={[
              "flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-edge/40",
              selected === hit.tile_id ? "bg-edge/60" : "",
            ].join(" ")}
          >
            <span className="w-5 pt-0.5 text-xs text-muted">{i + 1}</span>
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{coords(hit.lat, hit.lon)}</span>
                {hit.known_analog === null ? (
                  <span className="rounded bg-holds/20 px-1.5 py-0.5 text-xs text-holds">new</span>
                ) : (
                  <span className="rounded bg-edge px-1.5 py-0.5 text-xs text-muted">
                    known: {hit.known_analog}
                  </span>
                )}
              </span>
              <span className="mt-1 block font-mono text-xs text-muted">{hit.tile_id}</span>
            </span>
            <span className="shrink-0 text-right text-xs">
              <span className="block">
                terrain <strong className="font-semibold">{percent(hit.visual_cos_scaled)}</strong>
              </span>
              <span className="block text-muted">
                physical <strong className="font-semibold">{percent(hit.physical)}</strong>
              </span>
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
