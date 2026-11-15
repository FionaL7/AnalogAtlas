"""Slide figure for the analog portfolio (#31).

    python scripts/05_portfolio_figure.py                 # Shackleton rim
    python scripts/05_portfolio_figure.py --site Haworth  # any MOON_BASE_REGIONS / MOON_SITES name

Writes docs/figures/portfolio.png: one row per picked Earth site, one column
per dimension. Dark cell = this site is the first to cover it; light = it
covers it too; the score is written in every cell. Re-run it if the scores
change (#32).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import analog, config as C, portfolio  # noqa: E402
from analogatlas.sites import MOON_BASE_REGIONS, MOON_SITES  # noqa: E402
from api.indices import annotate_known  # noqa: E402

INK, MUTED, GREY, SURF = "#0b0b0b", "#52514e", "#b8b7b1", "#fcfcfb"   # as holdout.png
ADDS, ALSO = "#1d5fb0", "#6aa3e6"     # one hue, two steps (checked with the dataviz validator)
SHORT = {"shape": "Terrain\nshape", "slope": "Slope and\nrelief", "thermal_swing": "Thermal\nswing",
         "dryness": "Dryness", "sun_angle": "Low sun\nangle", "rock_ice": "Bare rock,\nfrozen",
         "access": "Access"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default="Shackleton rim (classic base concept)")
    ap.add_argument("--out", type=Path, default=C.ROOT / "docs" / "figures" / "portfolio.png")
    args = ap.parse_args()

    if args.site in MOON_BASE_REGIONS:
        body, (lat, lon) = "moon_polar", MOON_BASE_REGIONS[args.site]
    elif args.site in MOON_SITES:
        body, (lat, lon) = "moon", MOON_SITES[args.site]
    else:
        sys.exit(f"unknown site {args.site!r}")
    src, earth = analog.load_index(body), analog.load_index("earth")
    earth.meta = annotate_known(earth.meta)
    p = portfolio.build_portfolio(src, src.nearest_tile(lat, lon), earth)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Patch

    dims = [d for d in portfolio.DIMENSION_IDS]
    flagged = {d["id"] for d in p["dimensions"] if d["earth_best_only"]}
    n_rows, n_cols = len(p["sites"]), len(dims)
    fig, ax = plt.subplots(figsize=(10, 1.6 + 0.75 * n_rows), facecolor=SURF)
    ax.set_facecolor(SURF)
    for r, s in enumerate(p["sites"]):
        for c, d in enumerate(dims):
            if d in s["covers"]:
                color = ADDS if d in s["adds"] else ALSO
                ax.add_patch(FancyBboxPatch((c + 0.06, r + 0.08), 0.88, 0.84,
                                            boxstyle="round,pad=0,rounding_size=0.06",
                                            facecolor=color, edgecolor=SURF, lw=2))
                ax.text(c + 0.5, r + 0.5, f"{s['scores'][d]:.0%}", ha="center", va="center",
                        color="white" if d in s["adds"] else INK, fontsize=10)
            else:
                ax.text(c + 0.5, r + 0.5, "·", ha="center", va="center", color=GREY, fontsize=14)
    place = lambda s: s["known_analog"] or f"{abs(s['lat']):.1f}°{'S' if s['lat'] < 0 else 'N'} {abs(s['lon']):.1f}°{'W' if s['lon'] < 0 else 'E'}"  # noqa: E731
    ax.set_yticks([r + 0.5 for r in range(n_rows)],
                  [f"#{s['order']}  {place(s)}" for s in p["sites"]], color=INK, fontsize=10)
    ax.set_xticks([c + 0.5 for c in range(n_cols)],
                  [SHORT[d] + (" *" if d in flagged else "") for d in dims], color=INK, fontsize=9)
    ax.xaxis.tick_top()
    ax.set_xlim(0, n_cols)
    ax.set_ylim(n_rows, 0)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)

    best = p["best_single_site"]["covers"] if p["best_single_site"] else 0
    fig.suptitle(f"{args.site}: no single Earth site covers all {n_cols} dimensions "
                 f"(best covers {best}); these {n_rows} do together",
                 color=INK, fontsize=12, x=0.01, ha="left")
    note = "Cell = score 0-100%. Ice sheets, forests and lakes are never picked."
    if flagged:
        note += "  * Nowhere on Earth fully matches; the closest Earth gets counts."
    fig.text(0.01, 0.015, note, color=MUTED, fontsize=8.5)
    fig.legend(handles=[Patch(color=ADDS, label="first covered here"),
                        Patch(color=ALSO, label="also covers")],
               loc="lower left", bbox_to_anchor=(0.005, 0.045), frameon=False, fontsize=8.5,
               ncol=2, labelcolor=INK)
    fig.tight_layout(rect=(0, 0.1, 1, 0.95))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200, facecolor=SURF)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
