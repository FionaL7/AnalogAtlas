/**
 * Score colours: a viridis-like sequential ramp, readable with colour-blind
 * vision and in greyscale (§6). Colour is never the only carrier: every value
 * is also printed in the panel and in the map tooltip.
 */

// Viridis anchor colours at 0, 0.25, 0.5, 0.75, 1.
const STOPS: [number, number, number][] = [
  [0x44, 0x01, 0x54],
  [0x3b, 0x52, 0x8b],
  [0x21, 0x91, 0x8c],
  [0x5e, 0xc9, 0x62],
  [0xfd, 0xe7, 0x25],
];

const hex = (n: number) => Math.round(n).toString(16).padStart(2, "0");

/** 0-1 -> "#rrggbb". Out-of-range and NaN are clamped (NaN -> lowest). */
export function scoreColour(t: number): string {
  const v = Number.isFinite(t) ? Math.min(1, Math.max(0, t)) : 0;
  const pos = v * (STOPS.length - 1);
  const i = Math.min(Math.floor(pos), STOPS.length - 2);
  const f = pos - i;
  const [a, b] = [STOPS[i], STOPS[i + 1]];
  return `#${hex(a[0] + (b[0] - a[0]) * f)}${hex(a[1] + (b[1] - a[1]) * f)}${hex(a[2] + (b[2] - a[2]) * f)}`;
}

/** Legend ticks, low to high. */
export const LEGEND_TICKS = [0, 0.25, 0.5, 0.75, 1];
