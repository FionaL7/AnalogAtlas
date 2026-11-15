"""Step 4: train the analog model, validate it, find new candidates (#29).

    python scripts/04_train.py

Reads data/index/earth_*; writes
    data/index/earth_scores.parquet     tile_id + analog_score_{all,moon,mars} (0..1, 1 = best)
    data/index/candidates_{target}.json top new candidates (not near a known site) with reasons
    data/index/validation.json          key "analog_model": hold-one-out results (merged, so
                                        other validation keys from #16 are kept)
    docs/figures/holdout.png            chart for the slides
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import analog, config as C, learn  # noqa: E402
from analogatlas.sites import ANALOG_INFO, KNOWN_EARTH_ANALOGS  # noqa: E402

FIG = Path(__file__).resolve().parents[1] / "docs" / "figures"


def summary(df: pd.DataFrame) -> dict:
    t = df.top_pct
    return {"median_top_pct": round(float(t.median()), 1), "mean_top_pct": round(float(t.mean()), 1),
            "in_top_5pct": int((t <= 5).sum()), "in_top_10pct": int((t <= 10).sum()), "n": int(len(t))}


earth = analog.load_index("earth")
F_full = learn.build_features(earth)
variants = {
    "Our model (shape + physics + environment)": F_full,
    "CLIP only (learned)": learn.build_features(earth, parts=("shape", "look")),
    "Physics + environment only": learn.build_features(earth, parts=("phys", "env")),
}

# Extra checks (see validation.json "checks_note"): a one-column baseline the
# model must beat, and hold-one-out that also hides nearby known sites.
BARE = "Bare ground only (no learning)"
REGION = "Our model, sites within 1,500 km also hidden"

scores = pd.DataFrame({"tile_id": earth.meta.tile_id})
val = {"method": "PU logistic regression, hold-one-out over known surface analog sites",
       "note": f"C={learn.C_REG} picked by the same hold-one-out sweep, so results are slightly optimistic",
       "random_baseline_top_pct": 50.0,
       "checks_note": (f"'{BARE}' ranks tiles by bare-ground fraction alone: the model must beat it to claim "
                       f"more than 'barren and dry'. '{REGION}' hides every known site within 1,500 km of the "
                       "test site, so the model can't score by learning where sites cluster; it is the closer "
                       "proxy for an unseen region. 'random_sites_control': hold-one-out medians when random "
                       "tiles pose as known sites; ~50 means the method doesn't find signal in noise."),
       "targets": {}}

for target in (None, "moon", "mars"):
    key = target or "all"
    sites = learn.site_tiles(earth, target)
    print(f"\n== {key}: {len(sites)} sites with a land tile")
    res = {name: learn.holdout(F, sites) for name, F in variants.items()}
    res["Image similarity only (no learning)"] = learn.holdout_visual_baseline(earth, sites)
    res[BARE] = learn.holdout_single_column(earth.meta, sites, "barren_frac")
    res[REGION] = learn.holdout_region(F_full, sites, earth.meta)
    for name, df in res.items():
        print(f"  {name:45s} {summary(df)}")

    model = learn.fit(F_full.X, set(sites.values()))
    s = model.decision_function(F_full.X)
    scores[f"analog_score_{key}"] = learn.percentile_rank(s).round(4)

    cands = learn.new_candidates(earth, s, model, F_full)
    cands.to_json(C.INDEX / f"candidates_{key}.json", orient="records", indent=1)
    print(cands.head(10)[["lat", "lon", "score_pct", "why"]].to_string())

    full = res["Our model (shape + physics + environment)"]
    val["targets"][key] = {
        "sites_used": list(sites),
        "summary": {name: summary(df) for name, df in res.items()},
        "per_site": full.drop(columns="tile_row").round(1).to_dict(orient="records"),
        "per_site_region_hidden": res[REGION].drop(columns="tile_row").round(1).to_dict(orient="records"),
        "weights": learn.weights(model, F_full).round(3).to_dict(orient="records"),
    }

n_all = len(learn.site_tiles(earth))
val["random_sites_control"] = {"n_sites": n_all, "runs_median_top_pct": learn.random_sites_control(F_full, n_all)}
print(f"\nrandom-sites control (should be ~50): {val['random_sites_control']['runs_median_top_pct']}")

val["skipped_sites"] = {
    n: ("process analog (surface unlike Moon/Mars)" if not ANALOG_INFO[n]["surface"] else "no land tile (island)")
    for n in KNOWN_EARTH_ANALOGS if n not in learn.site_tiles(earth)}

scores.to_parquet(C.INDEX / "earth_scores.parquet")
vpath = C.INDEX / "validation.json"
allval = json.loads(vpath.read_text()) if vpath.exists() else {}
allval["analog_model"] = val
vpath.write_text(json.dumps(allval, indent=1))

# ---- chart: where hidden known sites rank, per method ("all" target) --------
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

summ = val["targets"]["all"]["summary"]
order = ["Image similarity only (no learning)", BARE, "CLIP only (learned)",
         "Physics + environment only", REGION, "Our model (shape + physics + environment)"]
INK, MUTED, BLUE, GREY, SURF = "#0b0b0b", "#52514e", "#2a78d6", "#b8b7b1", "#fcfcfb"
fig, ax = plt.subplots(figsize=(10, 5.2), facecolor=SURF)
ax.set_facecolor(SURF)
vals = [summ[k]["median_top_pct"] for k in order]
colors = [BLUE if k.startswith("Our model (") else "#8fb8e8" if k == REGION else GREY for k in order]
ax.barh(range(len(order)), vals, color=colors, height=0.55)
ax.axvline(50, color=MUTED, lw=1, ls="--")
ax.text(50.8, -0.25, "random guess", color=MUTED, fontsize=9, va="center")
for i, v in enumerate(vals):
    ax.text(v + 0.8, i, f"top {v:.1f}%", va="center", color=INK, fontsize=10)
ax.set_yticks(range(len(order)), order, color=INK, fontsize=10)
ax.set_xlim(0, 60)
ax.set_xlabel("Median rank of the hidden site: % of Earth tiles ranked above it (lower is better)",
              color=MUTED, fontsize=9)
fig.suptitle(f"Hide one of {summ[order[-1]]['n']} known analog sites, train on the rest: where does it rank?",
             color=INK, fontsize=12, x=0.01, ha="left")
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
for sp in ("left", "bottom"):
    ax.spines[sp].set_color(GREY)
ax.tick_params(colors=MUTED)
fig.tight_layout()
FIG.mkdir(parents=True, exist_ok=True)
fig.savefig(FIG / "holdout.png", dpi=200, facecolor=SURF)
print(f"\nwrote earth_scores.parquet, candidates_*.json, validation.json, {FIG / 'holdout.png'}")
