import { describe, expect, it } from "vitest";

import { LEGEND_TICKS, scoreColour } from "../lib/palette";

describe("scoreColour", () => {
  it("hits the viridis anchors exactly", () => {
    expect(scoreColour(0)).toBe("#440154");
    expect(scoreColour(0.5)).toBe("#21918c");
    expect(scoreColour(1)).toBe("#fde725");
  });

  it("clamps out-of-range and NaN instead of throwing", () => {
    expect(scoreColour(-1)).toBe("#440154");
    expect(scoreColour(2)).toBe("#fde725");
    expect(scoreColour(Number.NaN)).toBe("#440154");
  });

  it("gets lighter as the score rises, so it also reads in greyscale", () => {
    const luma = (h: string) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const ls = LEGEND_TICKS.map((t) => luma(scoreColour(t)));
    ls.slice(1).forEach((l, i) => expect(l).toBeGreaterThan(ls[i]));
  });
});
