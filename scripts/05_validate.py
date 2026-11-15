"""Step 5: validate the search against independent data (#16).

    python scripts/05_validate.py
    python scripts/05_validate.py --ks 5 10 20

Two tests, both against labels that enter nothing else in the pipeline:

1. Crater retrieval. The Robbins (2019) catalog labels every Moon tile with how
   cratered it is. Ask each tile for its nearest neighbours by embedding and
   count how many carry the same label. Crater density correlates only rho=0.35
   with `slope_med`, so this is close to independent of our own features.

2. Known-analog ranking. For each well-studied Earth analog, rank the whole
   Earth index from a lunar site that shares its role -- a volcanic analog
   queried from a volcanic place on the Moon -- and record where it lands.
   Reported for the shipped scoring and for image-only (`w_phys=0`), because
   the gap between them is what the physical term is worth.

Reads data/index/{moon,moon_polar,earth}_* and the Robbins catalog; writes

    data/index/{moon,moon_polar}_craters.parquet  per-tile crater labels, so other
                                                  devices skip the 227 MB CSV
    data/index/validation.json      keys "crater_retrieval" and
                                    "known_analog_ranking", merged in so #29's
                                    "analog_model" key survives
    docs/figures/crater_precision.png             chart for the slides
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import analog, checks, config as C, craters, traps  # noqa: E402
from analogatlas.sites import (  # noqa: E402
    ANALOG_INFO, KNOWN_EARTH_ANALOGS, MARS_SITES, MOON_BASE_REGIONS,
    MOON_ROLE_SITES, MOON_SITES, UNTESTABLE_ROLES,
)
from api.indices import annotate_known  # noqa: E402

FIG = Path(__file__).resolve().parents[1] / "docs" / "figures"
DEFAULT_KS = (5, 10, 20)


# ------------------------------------------------------ crater retrieval ----
def _neighbours(index: analog.BodyIndex, k_max: int, w_shade: float = 0.6) -> np.ndarray:
    """(N, k_max) row indices of each tile's nearest neighbours, itself excluded.

    The same similarity `analog.search` serves, so this measures what ships.
    """
    sim = (w_shade * (index.shade @ index.shade.T)
           + (1 - w_shade) * (index.img @ index.img.T)).astype(np.float32)
    np.fill_diagonal(sim, -np.inf)
    part = np.argpartition(-sim, k_max, axis=1)[:, :k_max]
    ordered = np.take_along_axis(part, np.argsort(-np.take_along_axis(sim, part, 1), axis=1), 1)
    return ordered


def _precision(neigh: np.ndarray, relevant: np.ndarray, queries: np.ndarray,
               ks: tuple[int, ...]) -> dict:
    """Mean precision@k over `queries`, where `relevant[q]` is a boolean row.

    None, not NaN, when a class has no queries: this lands in validation.json
    and `NaN` is not JSON a browser will parse.
    """
    out = {}
    for k in ks:
        hits = [relevant[q][neigh[q, :k]].mean() for q in queries]
        out[f"p_at_{k}"] = round(float(np.mean(hits)), 4) if len(hits) else None
    return out


def crater_retrieval(index: analog.BodyIndex, labels: pd.DataFrame,
                     ks: tuple[int, ...]) -> dict:
    """Precision@k against crater labels: density class, then big craters."""
    neigh = _neighbours(index, max(ks))
    n = len(labels)

    cls = craters.density_class(labels).to_numpy()
    same = cls[:, None] == cls[None, :]
    by_class = {}
    for c, name in enumerate(("smooth", "middling", "heavily cratered")):
        q = np.flatnonzero(cls == c)
        by_class[name] = {
            "n_queries": int(len(q)),
            # a random neighbour is relevant this often, which is the bar to clear
            "random_baseline": round(float((cls == c).mean()), 4),
            **_precision(neigh, same, q, ks),
        }

    big = craters.big_crater(labels).to_numpy()
    big_rel = np.broadcast_to(big, (n, n))
    return {
        "note": ("Robbins (2019) crater labels; they enter no feature and no training "
                 "label, so this is held-out ground truth"),
        "similarity": "the same shade/imagery embedding mix analog.search uses (w_shade=0.6)",
        "tiles": int(n),
        "density_class": {
            "definition": ("tercile of the count of craters >= 1 km in the 85 km chip "
                           "(smooth mare through saturated highlands)"),
            "overall": {"n_queries": int(n),
                        "random_baseline": round(float(np.mean([(cls == c).mean()
                                                                for c in (0, 1, 2)])), 4),
                        **_precision(neigh, same, np.arange(n), ks)},
            "by_class": by_class,
        },
        "big_crater": {
            "definition": f"the chip holds the centre of a crater >= {craters.BIG_KM:.0f} km "
                          "across, i.e. half the chip wide",
            "n_queries": int(big.sum()),
            "random_baseline": round(float(big.mean()), 4),
            **_precision(neigh, big_rel, np.flatnonzero(big), ks),
        },
    }


# --------------------------------------------------- known-analog ranking ----
def _ranks(score: np.ndarray) -> np.ndarray:
    """1-based rank of every tile, best score first."""
    order = np.argsort(-score)
    out = np.empty(len(score), dtype=int)
    out[order] = np.arange(1, len(score) + 1)
    return out


def _best_rank(src: analog.BodyIndex, site: tuple[float, float], earth: analog.BodyIndex,
               rows: np.ndarray, w_phys: float) -> tuple[int, bool]:
    """Best rank the analog's own tiles reach from this lunar site, and whether
    that tile is one the environment checks push down (#33)."""
    i = src.nearest_tile(*site)
    score, *_ = analog.cross_body_scores(src, i, earth, w_phys=w_phys)
    rank = _ranks(np.nan_to_num(score, nan=-np.inf))
    best = rows[np.argmin(rank[rows])]
    return int(rank[best]), bool(checks.push_down_mask(earth.meta)[best])


def known_analog_ranking(earth: analog.BodyIndex, by_body: dict,
                         w_phys_settings=(("shipped", 0.3), ("image_only", 0.0))) -> dict:
    """Where each known analog ranks on Earth, queried from its role's lunar sites.

    Surface analogs only: a forested or eroded impact structure is a *process*
    analog, and ranking it high would be the search being wrong, not right.
    Same split `learn.py` trains on.

    Mars-target analogs are ranked too but carry `moon_target: false` and stay
    out of the summary. A Mars analog that ranks badly from a lunar site is not
    a failure, so scoring it as one would flatter or damn the search at random.
    """
    n = len(earth.meta)
    tested, skipped = [], {}
    for name, info in ANALOG_INFO.items():
        if not info["surface"]:
            skipped[name] = "process analog (surface unlike the Moon), as in learn.py"
            continue
        roles = [r for r in info["roles"] if r in MOON_ROLE_SITES]
        if not roles:
            why = "; ".join(UNTESTABLE_ROLES.get(r, f"no lunar sites for role {r!r}")
                            for r in info["roles"])
            skipped[name] = why
            continue
        rows = np.flatnonzero((earth.meta.known_analog == name).to_numpy())
        if len(rows) == 0:
            skipped[name] = "no Earth tile within the 150 km known-analog radius"
            continue

        record = {"site": name, "roles": list(info["roles"]), "tested_roles": roles,
                  "moon_target": "moon" in info["target"], "earth_tiles": int(len(rows))}
        for label, w_phys in w_phys_settings:
            best = None
            for role in roles:
                body, site_names = MOON_ROLE_SITES[role]
                src = by_body.get(body)
                if src is None:
                    continue
                coords = MOON_BASE_REGIONS if body == "moon_polar" else MOON_SITES
                for site_name in site_names:
                    rank, pushed = _best_rank(src, coords[site_name], earth, rows, w_phys)
                    if best is None or rank < best["rank"]:
                        best = {"rank": rank, "role": role, "query": site_name,
                                "pushed_down": pushed}
            if best is None:
                continue
            record[label] = {
                **best,
                # same convention as learn.py: % of Earth tiles scoring higher
                "top_pct": round(100 * (best["rank"] - 1) / n, 2),
            }
        tested.append(record)

    tested.sort(key=lambda r: r.get("shipped", {}).get("rank", n + 1))
    scored = [r for r in tested if r["moon_target"] and "shipped" in r]
    in_top = {f"in_top_{p}pct": sum(1 for r in scored if r["shipped"]["top_pct"] <= p)
              for p in (1, 5, 10, 25)}
    return {
        "note": ("each analog ranked against the whole Earth index from lunar sites "
                 "sharing its role (sites.MOON_ROLE_SITES)"),
        "earth_tiles_ranked": n,
        "top_pct_meaning": "% of Earth tiles scoring higher; 0 is first, 50 is chance",
        "summary": {"n": len(scored), **in_top,
                    "median_top_pct": (round(float(np.median(
                        [r["shipped"]["top_pct"] for r in scored])), 2) if scored else None),
                    "counts": "Moon-target surface analogs only"},
        "sites": tested,
        "skipped_sites": skipped,
    }


# The polar analogs #32 asks about by name. Three carry the `polar` role in
# ANALOG_INFO; the Atacama is labelled `arid` there, and this block is the one
# place that asks for it anyway, because the issue's table names it.
POLAR_NAMED = (
    "Atacama Desert (Yungay), Chile",
    "Svalbard (Bockfjorden), Norway",
    "McMurdo Dry Valleys, Antarctica",
    "Haughton Crater, Devon Island, Canada",
)


def polar_ranking(earth: analog.BodyIndex, polar: analog.BodyIndex | None,
                  w_phys: float = 0.3) -> dict:
    """Where the canonical lunar-polar analogs rank, per polar query site (#32).

    Separate from `known_analog_ranking` because the question is different: not
    "does each analog rank for its role" but "for an Artemis region, do the
    sites the literature would name come back". ANALOG_INFO labels three of
    these four as Mars analogs, so most are informational there.
    """
    if polar is None:
        return {"note": "no moon_polar index; build it with scripts/01_tiles.py moon_polar"}
    names = list(dict.fromkeys(
        list(POLAR_NAMED)
        + [n for n, i in ANALOG_INFO.items() if "polar" in i["roles"] and i["surface"]]))
    n = len(earth.meta)
    out = {}
    for site_name, coords in ((s, MOON_BASE_REGIONS[s]) for s in MOON_ROLE_SITES["polar"][1]):
        rows_by_site = {}
        for name in names:
            rows = np.flatnonzero((earth.meta.known_analog == name).to_numpy())
            if len(rows) == 0:
                continue
            rank, pushed = _best_rank(polar, coords, earth, rows, w_phys)
            rows_by_site[name] = {"rank": rank, "top_pct": round(100 * (rank - 1) / n, 2),
                                  "pushed_down": pushed,
                                  "roles": list(ANALOG_INFO[name]["roles"]),
                                  "target": list(ANALOG_INFO[name]["target"])}
        out[site_name] = {
            # Artemis regions are ~15 km across and sit closer together than our
            # 85 km tiles, so two regions can share one. Naming the tile keeps
            # identical rows legible as that, rather than as a duplicated table.
            "query_tile": str(polar.meta.iloc[polar.nearest_tile(*coords)].tile_id),
            "analogs": dict(sorted(rows_by_site.items(), key=lambda kv: kv[1]["rank"])),
        }
    shared = {}
    for site_name, row in out.items():
        shared.setdefault(row["query_tile"], []).append(site_name)
    return {
        "note": ("#32: the polar index adds illumination, permanent shadow and Earth "
                 "visibility, and none of them enter the ranking. These are the "
                 "canonical polar analogs' ranks under the shipped scoring."),
        "earth_tiles_ranked": n,
        "tile_resolution_km": round(C.TILE_KM, 1),
        "query_sites_sharing_a_tile": {t: s for t, s in shared.items() if len(s) > 1},
        "by_query_site": out,
    }


# ------------------------------------------------------------- Mars (#40) ---
# Which Mars sites put each analog role to the test, mirroring MOON_ROLE_SITES.
# Lives here rather than sites.py because sites.py belongs to B3 (#42).
#   "polar" on Mars means ice: the ground-ice landing zones are exactly the
#   sites whose canonical analogs (McMurdo, Axel Heiberg, Svalbard) carry the
#   polar role in ANALOG_INFO.
MARS_ROLE_SITES = {
    "impact": ("mars", ("Gale crater", "Jezero crater")),
    "volcanic": ("mars", ("Arsia Mons skylights",)),
    "lava_tube": ("mars", ("Arsia Mons skylights",)),
    "arid": ("mars", ("Medusae Fossae", "Gale crater")),
    "aqueous": ("mars", ("Jezero crater", "Oxia Planum")),
    "polar": ("mars", ("Arcadia Planitia", "Utopia Planitia", "Deuteronilus Mensae")),
}


def _mars_scores(mars: analog.BodyIndex, i: int, earth: analog.BodyIndex,
                 w_phys: float, w_shade: float = 1.0) -> np.ndarray:
    """cross_body_scores with a controllable visual channel.

    w_shade=1 is exactly what ships (`analog.cross_body_scores` ranks on the
    hillshade channel alone); w_shade=0 ranks on the Viking/Blue Marble look
    channel instead. The comparison is the issue's question: does the look
    channel help or hurt on Mars?
    """
    visual = (w_shade * (earth.shade @ mars.shade[i])
              + (1 - w_shade) * (earth.img @ mars.img[i]))
    s_row = mars.meta.iloc[i]
    v = (visual - visual.mean()) / (visual.std() + 1e-9)
    phys = analog._physical(s_row, earth.meta)
    pushed = analog.push_down_for(s_row, earth.meta)
    return (1 - w_phys) * v + w_phys * (phys - 0.5) * 4 - w_phys * analog.ENV_PENALTY * pushed


def _mars_best_rank(mars, site, earth, rows, w_phys, w_shade=1.0) -> tuple[int, bool]:
    i = mars.nearest_tile(*site)
    score = _mars_scores(mars, i, earth, w_phys, w_shade)
    rank = _ranks(np.nan_to_num(score, nan=-np.inf))
    best = rows[np.argmin(rank[rows])]
    return int(rank[best]), bool(checks.push_down_mask(earth.meta)[best])


def _mars_testable(earth: analog.BodyIndex):
    """(name, roles, earth rows) per rankable analog, plus the skipped ones."""
    tested, skipped = [], {}
    for name, info in ANALOG_INFO.items():
        if not info["surface"]:
            skipped[name] = "process analog (surface unlike Mars), as in learn.py"
            continue
        roles = [r for r in info["roles"] if r in MARS_ROLE_SITES]
        rows = np.flatnonzero((earth.meta.known_analog == name).to_numpy())
        if len(rows) == 0:
            skipped[name] = "no Earth tile within the 150 km known-analog radius"
            continue
        tested.append((name, roles, rows))
    return tested, skipped


def mars_analog_ranking(earth: analog.BodyIndex, mars: analog.BodyIndex,
                        w_phys_settings=(("shipped", 0.3), ("image_only", 0.0))) -> dict:
    """Where each known analog ranks on Earth, queried from Mars sites of its
    role -- the #16 known-analog test, with Mars as the source body. Every
    role is testable here (unlike the Moon, Mars has arid and aqueous sites),
    so only process analogs and tiles without land are skipped."""
    n = len(earth.meta)
    testable, skipped = _mars_testable(earth)
    tested = []
    for name, roles, rows in testable:
        info = ANALOG_INFO[name]
        record = {"site": name, "roles": list(info["roles"]), "tested_roles": roles,
                  "mars_target": "mars" in info["target"], "earth_tiles": int(len(rows))}
        for label, w_phys in w_phys_settings:
            best = None
            for role in roles:
                for site_name in MARS_ROLE_SITES[role][1]:
                    rank, pushed = _mars_best_rank(mars, MARS_SITES[site_name], earth,
                                                   rows, w_phys)
                    if best is None or rank < best["rank"]:
                        best = {"rank": rank, "role": role, "query": site_name,
                                "pushed_down": pushed}
            if best is not None:
                record[label] = {**best, "top_pct": round(100 * (best["rank"] - 1) / n, 2)}
        tested.append(record)

    tested.sort(key=lambda r: r.get("shipped", {}).get("rank", n + 1))
    scored = [r for r in tested if r["mars_target"] and "shipped" in r]
    in_top = {f"in_top_{p}pct": sum(1 for r in scored if r["shipped"]["top_pct"] <= p)
              for p in (1, 5, 10, 25)}
    return {
        "note": ("each analog ranked against the whole Earth index from Mars sites "
                 "sharing its role (MARS_ROLE_SITES in 05_validate.py)"),
        "earth_tiles_ranked": n,
        "top_pct_meaning": "% of Earth tiles scoring higher; 0 is first, 50 is chance",
        "summary": {"n": len(scored), **in_top,
                    "median_top_pct": (round(float(np.median(
                        [r["shipped"]["top_pct"] for r in scored])), 2) if scored else None),
                    "counts": "Mars-target surface analogs only"},
        "sites": tested,
        "skipped_sites": skipped,
    }


def channel_verdict(per_analog: dict[str, list[float]], n_boot: int = 4000, seed: int = 0) -> dict:
    """Does any visual channel beat the shipped hillshade-only one by more than noise?

    `per_analog`: channel label -> top-% per known analog, in the same analog
    order for every channel (so they can be paired). The lowest median is
    the `best` channel; but with a few dozen analogs a gap of about a point
    is easily noise, so a switch is recommended only when a paired bootstrap
    over the analogs puts the whole 95% interval of the median gap
    (shade-only minus best) above zero.
    """
    medians = {k: float(np.median(v)) for k, v in per_analog.items()}
    best = min(medians, key=medians.get)
    if best == "shade_only":
        return {"best": best, "gap_ci95": None,
                "recommendation": "keep the shipped shade-only visual channel for mars"}
    shade, other = np.asarray(per_analog["shade_only"]), np.asarray(per_analog[best])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(shade), size=(n_boot, len(shade)))
    gaps = np.median(shade[idx], axis=1) - np.median(other[idx], axis=1)
    lo, hi = (round(float(x), 2) for x in np.percentile(gaps, [2.5, 97.5]))
    if lo > 0:
        rec = (f"{best} beats shade-only beyond noise (95% interval for the median gap "
               f"{lo} to {hi} points); consider changing analog.cross_body")
    else:
        rec = (f"keep the shipped shade-only visual channel for mars: {best} has the lowest "
               f"median, but the gap to shade-only is within noise (95% interval {lo} to {hi} "
               f"points over {len(shade)} analogs)")
    return {"best": best, "gap_ci95": [lo, hi], "recommendation": rec}


def mars_visual_channels(earth: analog.BodyIndex, mars: analog.BodyIndex,
                         w_phys: float = 0.3) -> dict:
    """Shade-only vs look-only vs mixed visual channel, judged by the same
    known-analog medians. The risk named in the plan: Viking colour and Blue
    Marble look so different that the look channel drags the ranking down."""
    n = len(earth.meta)
    testable, _ = _mars_testable(earth)
    testable = [(name, roles, rows) for name, roles, rows in testable
                if "mars" in ANALOG_INFO[name]["target"] and roles]
    channels, per_analog = {}, {}
    for label, w_shade in (("shade_only", 1.0), ("look_only", 0.0), ("mixed_0.6", 0.6)):
        pcts = []
        for name, roles, rows in testable:
            best = min(_mars_best_rank(mars, MARS_SITES[s], earth, rows, w_phys, w_shade)[0]
                       for role in roles for s in MARS_ROLE_SITES[role][1])
            pcts.append(100 * (best - 1) / n)
        per_analog[label] = pcts
        channels[label] = {"median_top_pct": round(float(np.median(pcts)), 2),
                           "mean_top_pct": round(float(np.mean(pcts)), 2),
                           "in_top_5pct": int(sum(p <= 5 for p in pcts)),
                           "n": len(pcts)}
    verdict = channel_verdict(per_analog)
    return {
        "note": ("the shipped cross-body ranking uses the hillshade channel alone "
                 "(w_shade=1); this measures what the Viking look channel would add, "
                 f"at w_phys={w_phys}, over the Mars-target analogs"),
        "channels": channels,
        **verdict,
    }


def mars_trap_rate(mars: analog.BodyIndex, earth: analog.BodyIndex) -> dict:
    """Share of image-only Mars lookalikes that fail a physics check (#30's
    headline number, for Mars). Stats only; the browsable list is traps.json."""
    _, stats = traps.scan(mars, earth, "mars")
    return {
        "note": (f"of each Mars tile's top {traps.TOP_N} Earth lookalikes by terrain "
                 "shape alone, the share failing a hard physical check (ice, plants, "
                 "water); ice is kept for ice-rich Mars tiles"),
        **stats,
    }


# ----------------------------------------------------------------- chart ----
def chart(crater: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    INK, MUTED, BLUE, GREY, SURF = "#0b0b0b", "#52514e", "#2a78d6", "#b8b7b1", "#fcfcfb"
    by_class = crater["density_class"]["by_class"]
    rows = [("Heavily cratered", by_class["heavily cratered"]),
            ("Smooth (mare)", by_class["smooth"]),
            ("Middling", by_class["middling"]),
            ("Holds a big crater", crater["big_crater"])]
    rows = [(name, g) for name, g in rows if g.get("p_at_10") is not None]
    fig, ax = plt.subplots(figsize=(10, 4.0), facecolor=SURF)
    ax.set_facecolor(SURF)
    y = np.arange(len(rows))
    vals = [100 * g["p_at_10"] for _, g in rows]
    base = [100 * g["random_baseline"] for _, g in rows]
    # The weak rows matter as much as the strong ones, so colour marks "clears
    # chance by half as much again" rather than "this is the row we like".
    ax.barh(y, vals, color=[BLUE if v >= 1.5 * b else GREY for v, b in zip(vals, base)], height=0.5)
    # chance as a tick per row, not a second bar: an overlapping bar reads as
    # one striped bar rather than two series
    ax.vlines(base, y - 0.3, y + 0.3, color=MUTED, lw=1.4)
    for i, (v, b) in enumerate(zip(vals, base)):
        ax.text(v + 1.5, i, f"{v:.0f}%", va="center", color=INK, fontsize=10)
    ax.set_yticks(y, [n for n, _ in rows], color=INK, fontsize=10)
    ax.set_xlim(0, 105)
    ax.set_xlabel(f"Of the 10 nearest tiles by image embedding, % carrying the same "
                  f"independent crater label. Ticks: chance, ~{np.mean(base):.0f}%",
                  color=MUTED, fontsize=9)
    fig.suptitle("Crater labels were never shown to the model. Retrieval finds them anyway.",
                 color=INK, fontsize=12, x=0.01, ha="left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GREY)
    ax.tick_params(colors=MUTED)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, facecolor=SURF)


# ------------------------------------------------------------------ main ----
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ks", type=int, nargs="+", default=list(DEFAULT_KS),
                    help="k values for precision@k (default 5 10 20)")
    ap.add_argument("--no-chart", action="store_true")
    args = ap.parse_args()
    ks = tuple(sorted(args.ks))

    try:
        moon, earth = analog.load_index("moon"), analog.load_index("earth")
        polar = (analog.load_index("moon_polar")
                 if (C.INDEX / "moon_polar_meta.parquet").exists() else None)
        mars = (analog.load_index("mars")
                if (C.INDEX / "mars_meta.parquet").exists() else None)
    except analog.IndexMismatchError as e:
        sys.exit(f"index is inconsistent: {e} - do not validate it")
    earth.meta = annotate_known(earth.meta)

    catalog = craters.load_catalog()
    print(f"{len(catalog):,} craters in the Robbins catalog")

    labels = craters.per_tile(moon.meta, "moon", catalog)
    labels.to_parquet(C.INDEX / "moon_craters.parquet")
    if polar is not None:
        craters.per_tile(polar.meta, "moon_polar", catalog).to_parquet(
            C.INDEX / "moon_polar_craters.parquet")

    print(f"\n== crater retrieval over {len(moon.meta)} Moon tiles")
    crater = crater_retrieval(moon, labels, ks)
    k = 10 if 10 in ks else ks[-1]
    for name, row in {**crater["density_class"]["by_class"],
                      "big crater": crater["big_crater"]}.items():
        p = row[f"p_at_{k}"]
        print(f"  {name:18s} p@{k:<3d} {'--' if p is None else f'{p:.3f}'}  "
              f"(chance {row['random_baseline']:.3f}, {row['n_queries']} queries)")

    print("\n== known-analog ranking")
    ranking = known_analog_ranking(earth, {"moon": moon, "moon_polar": polar})
    for r in ranking["sites"]:
        s, img = r.get("shipped", {}), r.get("image_only", {})
        flags = ("" if r["moon_target"] else "  [Mars analog, not scored]") + \
                ("  [pushed down]" if s.get("pushed_down") else "")
        print(f"  {r['site'][:46]:46s} top {s.get('top_pct', float('nan')):5.2f}%  "
              f"(image-only {img.get('top_pct', float('nan')):5.2f}%)  "
              f"via {s.get('role', '?')}/{s.get('query', '?')}{flags}")
    print(f"  -- {ranking['summary']}")

    print("\n== polar analogs, per Artemis query site (#32)")
    polar_rank = polar_ranking(earth, polar)
    for site_name, row in polar_rank.get("by_query_site", {}).items():
        print(f"  {site_name}  (tile {row['query_tile']})")
        for name, r in row["analogs"].items():
            print(f"    {name[:44]:44s} rank {r['rank']:>5} of {polar_rank['earth_tiles_ranked']}"
                  f"  top {r['top_pct']:5.2f}%" + ("  [pushed down]" if r["pushed_down"] else ""))
    for tile, names in polar_rank.get("query_sites_sharing_a_tile", {}).items():
        print(f"  ! {' and '.join(names)} share tile {tile}: "
              f"{polar_rank['tile_resolution_km']:.0f} km tiles cannot separate them")

    mars_keys = {}
    if mars is not None:
        print(f"\n== Mars known-analog ranking over {len(mars.meta)} Mars tiles (#40)")
        mars_keys["mars_analog_ranking"] = mr = mars_analog_ranking(earth, mars)
        for r in mr["sites"]:
            s, img = r.get("shipped", {}), r.get("image_only", {})
            flags = ("" if r["mars_target"] else "  [Moon analog, not scored]") + \
                    ("  [pushed down]" if s.get("pushed_down") else "")
            print(f"  {r['site'][:46]:46s} top {s.get('top_pct', float('nan')):5.2f}%  "
                  f"(image-only {img.get('top_pct', float('nan')):5.2f}%)  "
                  f"via {s.get('role', '?')}/{s.get('query', '?')}{flags}")
        print(f"  -- {mr['summary']}")

        print("\n== Mars visual channels")
        mars_keys["mars_visual_channels"] = mv = mars_visual_channels(earth, mars)
        for label, row in mv["channels"].items():
            print(f"  {label:12s} median top {row['median_top_pct']:5.2f}%  "
                  f"({row['in_top_5pct']}/{row['n']} in top 5%)")
        print(f"  -- {mv['recommendation']}")

        print("\n== Mars trap rate")
        mars_keys["mars_traps"] = mt = mars_trap_rate(mars, earth)
        print(f"  {mt['traps']} traps in {mt['lookalikes_checked']} lookalikes "
              f"= {100 * mt['trap_rate']:.1f}%  by reason: {mt['by_reason']}")
    else:
        print("\n(no mars index: skipping the Mars validation; "
              "build it with scripts/01_tiles.py and 02_features.py)")

    path = C.INDEX / "validation.json"
    allval = json.loads(path.read_text()) if path.exists() else {}
    allval["crater_retrieval"] = crater
    allval["known_analog_ranking"] = ranking
    allval["polar_analog_ranking"] = polar_rank
    allval.update(mars_keys)
    path.write_text(json.dumps(allval, indent=1))
    print(f"\nwrote {path} (keys: {', '.join(sorted(allval))})")

    if not args.no_chart:
        chart(crater, FIG / "crater_precision.png")
        print(f"wrote {FIG / 'crater_precision.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
