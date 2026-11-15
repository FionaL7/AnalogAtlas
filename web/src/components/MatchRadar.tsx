/**
 * Spider chart of the report card's `compare` rows: one spoke per dimension,
 * 0 at the centre and 100% match at the rim, with the 60% "holds" line drawn
 * dashed. Inline SVG, no chart library. Every spoke also prints its number,
 * so colour is never the only carrier (§6); the rows below stay the full record.
 */
import { MATCH_HOLDS, percent } from "../lib/format";
import type { BreakdownRow } from "../lib/types";

const R = 80;            // radius of the 100% ring, in viewBox units
const LABEL_R = R + 12;  // where the spoke labels start
const LINE_H = 12;
const RINGS = [0.25, 0.5, 0.75, 1];

/** Two lines at most, split where the longer line is shortest. */
export function wrapLabel(text: string): string[] {
  const words = text.split(" ");
  if (text.length <= 12 || words.length === 1) return [text];
  let best = [text];
  let worst = Infinity;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(" ");
    const b = words.slice(i).join(" ");
    const longest = Math.max(a.length, b.length);
    if (longest < worst) [best, worst] = [[a, b], longest];
  }
  return best;
}

/** Spoke i of n, starting at 12 o'clock and going clockwise. */
const angle = (i: number, n: number) => -Math.PI / 2 + (2 * Math.PI * i) / n;
const point = (i: number, n: number, r: number) =>
  [r * Math.cos(angle(i, n)), r * Math.sin(angle(i, n))] as const;
const ring = (n: number, f: number) =>
  Array.from({ length: n }, (_, i) => point(i, n, R * f).join(",")).join(" ");

export function MatchRadar({ rows, world }: { rows: BreakdownRow[]; world: string }) {
  const spokes = rows.filter((r) => r.kind === "compare" && r.match !== null);
  const n = spokes.length;
  if (n < 3) return null;
  const value = (r: BreakdownRow) => Math.max(0, Math.min(1, r.match ?? 0));
  const shape = spokes.map((r, i) => point(i, n, R * value(r)).join(",")).join(" ");
  const held = spokes.filter((r) => value(r) >= MATCH_HOLDS).length;
  const summary = `Match by dimension, ${world} versus Earth: ${spokes
    .map((r) => `${r.dimension} ${percent(r.match)}`).join(", ")}`;

  return (
    <figure className="flex flex-col items-center">
      <svg viewBox="-190 -122 380 244" role="img" aria-label={summary}
           className="w-full max-w-[26rem] overflow-visible">
        {RINGS.map((f) => (
          <polygon key={f} points={ring(n, f)} className="fill-none stroke-edge" strokeWidth={0.75} />
        ))}
        {spokes.map((_, i) => {
          const [x, y] = point(i, n, R);
          return <line key={i} x1={0} y1={0} x2={x} y2={y} className="stroke-edge" strokeWidth={0.75} />;
        })}
        <polygon points={ring(n, MATCH_HOLDS)} className="fill-none stroke-holds/70"
                 strokeWidth={1} strokeDasharray="3 3" />
        <polygon points={shape} className="fill-accent/20 stroke-accent" strokeWidth={1.5}
                 strokeLinejoin="round" />
        {spokes.map((r, i) => {
          const [x, y] = point(i, n, R * value(r));
          return (
            <circle key={r.dimension} cx={x} cy={y} r={3}
                    className={value(r) >= MATCH_HOLDS ? "fill-holds" : "fill-breaks"} />
          );
        })}
        {spokes.map((r, i) => {
          const [lx, ly] = point(i, n, LABEL_R);
          const c = Math.cos(angle(i, n));
          const s = Math.sin(angle(i, n));
          const anchor = Math.abs(c) < 0.3 ? "middle" : c > 0 ? "start" : "end";
          const lines = [...wrapLabel(r.dimension), percent(r.match)];
          const h = lines.length * LINE_H;
          // Above the top spokes, below the bottom ones, centred on the sides.
          const y0 = (s < -0.3 ? ly - h : s > 0.3 ? ly : ly - h / 2) + LINE_H * 0.8;
          return (
            <text key={r.dimension} x={lx} y={y0} textAnchor={anchor} className="fill-muted text-[10.5px]">
              {lines.map((l, k) => (
                <tspan key={k} x={lx} dy={k ? LINE_H : 0}
                       className={k === lines.length - 1
                         ? value(r) >= MATCH_HOLDS ? "fill-holds font-semibold" : "fill-breaks font-semibold"
                         : undefined}>
                  {l}
                </tspan>
              ))}
            </text>
          );
        })}
      </svg>
      <figcaption className="mt-1 flex flex-wrap justify-center gap-x-4 text-[11px] text-muted">
        <span><span aria-hidden className="mr-1 inline-block h-2 w-2 rounded-full bg-holds" />holds (60%+)</span>
        <span><span aria-hidden className="mr-1 inline-block h-2 w-2 rounded-full bg-breaks" />breaks down</span>
        <span>{held} of {n} hold</span>
      </figcaption>
    </figure>
  );
}
