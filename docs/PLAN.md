# AnalogAtlas — Plan & Status

As of 14 Nov 2026. Related docs:
- [BRIEF.md](BRIEF.md): the challenge text
- [REQUIREMENTS.md](REQUIREMENTS.md): requirements and the submission checklist
- [RESOURCES.md](RESOURCES.md): data sources
- [ARCHITECTURE.md](ARCHITECTURE.md): stack, pages, API and data contract, repo layout, failure modes
- [TARGET-SITES.md](TARGET-SITES.md): the Moon and Mars sites we find analogs for

## Overview

AnalogAtlas is a search engine for planetary analogs. You can describe an Earth landscape and find matching terrain on the Moon, or pick a lunar site and get a ranked list of Earth analogs. Each analog comes with a report card showing where the analogy holds and where it breaks down.

It answers the NASA Space Apps 2026 challenge *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*. The judges stress three things, and each has a matching part of our design:

| Judges want | How we answer |
| --- | --- |
| Go beyond visual similarity | CLIP finds terrain that looks alike; slope, relief, rock cover, temperature and radar roughness check whether it really is alike |
| New, unrecognized analogs | Results near well-known analog sites are tagged "known" (`analogatlas/sites.py`); we lead with the untagged ones |
| Say where it breaks down | Every analog gets a report card: dimension by dimension, holds or breaks |

There are two stages:

1. **Global screening.** We split the Moon and Earth's land into tiles of about 85 × 85 km. Each tile gets CLIP embeddings (vectors describing what it looks like) and physical measurements, and search runs across both bodies.
2. **Close study.** For the 2–3 strongest *new* candidates, we compare radar surface roughness (RADARSAT RCM or Sentinel-1 on Earth, LRO Mini-RF on the Moon), add high-resolution imagery and slopes, and write a full report card.

Scope: the Moon first, then Mars as a full second body. Plan: [MARS-PLAN.md](MARS-PLAN.md).

## Status

Search works end to end on real data: Moon, south pole and Earth indexes, the API, the static export and the app. Mars is planned, not built: [MARS-PLAN.md](MARS-PLAN.md), tasks under the `mars` label.

| Piece | State | Notes |
| --- | --- | --- |
| Python environment | Done (Dev A's Mac) | Python 3.12, PyTorch on the Apple GPU (MPS), open_clip, FAISS, rasterio |
| Moon tiles | Done | 5,376 tiles from 60°S to 60°N, each with an LROC WAC image and a LOLA hillshade |
| Moon physical features | Done | Slope, relief and elevation (LOLA); rock abundance and regolith-temperature anomaly (Diviner) |
| Moon CLIP embeddings | Done | 512-d image vectors, plus hillshade vectors averaged over four 90° rotations |
| Moon south pole (`moon_polar`) | Done | 89 tiles, 75–90°S, polar stereographic. Adds illumination, permanent shadow and Earth visibility. All ten Artemis regions covered ([#26](https://github.com/FionaL7/AnalogAtlas/issues/26)) |
| Earth side | Done | 11,699 land tiles. Hillshade + slope/relief from Copernicus DEM via `analogatlas/earth_ee.py` (Earth Engine, `EE_PROJECT` in `.env`); imagery from GIBS Blue Marble |
| Analog model | Done | PU learning on known sites, hold-one-out validation, new candidates ([#29](https://github.com/FionaL7/AnalogAtlas/issues/29)) |
| Lookalike traps | Done | `analogatlas/traps.py`, exported as `traps.json` ([#30](https://github.com/FionaL7/AnalogAtlas/issues/30)) |
| Analog portfolio | Done | `analogatlas/portfolio.py`, exported as `portfolio/{site_id}.json` for all 21 lunar targets; each fully covered by 2–4 Earth sites ([#31](https://github.com/FionaL7/AnalogAtlas/issues/31)). Shown on each field guide; slide figure `docs/figures/portfolio.png` (`scripts/05_portfolio_figure.py`). **If #32 changes scoring, re-run `03_export.py` and `05_portfolio_figure.py`** |
| Search API | Done | `api/`: `/search`, `/analogs`, `/twins` (with field tests and model score), `/tile` |
| React frontend | Done | Atlas (site, map-click and text/picture search, report card with tile pictures and field tests), field guides, discoveries, traps, methodology with validation, data and credits ([#34](https://github.com/FionaL7/AnalogAtlas/issues/34)) |
| Radar close study | Done | Mini-RF CPR for every lunar site (`radar.json`). 3 new pairs measured up close: radar on both bodies, 30 m slope, Sentinel-2 picture, full report card, page at `/close-study/:id`. Pairs and why: `analogatlas/closestudy.py` ([#19](https://github.com/FionaL7/AnalogAtlas/issues/19)) |
| Mars | Planned | Global `mars` index, 7 landing sites, report card, validation. Plan and tasks: [MARS-PLAN.md](MARS-PLAN.md) |

**Verification.** Three text queries on the Moon index returned the expected terrain, and slopes measured independently from LOLA elevation data agree:

| Query | Median slope of top 6 | Before the #27 crop fix |
| --- | --- | --- |
| "a large impact crater with a central peak" | 3.3° | 4.7° |
| "smooth flat dark lava plains" | 0.4° | 0.4° |
| "rugged mountainous highlands" | **6.5°** | 5.7° |

For comparison, the median slope across all Moon tiles is 3.9°, unchanged (slope comes from the DEM, not the chips). The ML results agree with independent elevation data, which is the first point to make on the slides.

Rebuilt after [#27](https://github.com/FionaL7/AnalogAtlas/issues/27). "Rugged highlands" separates more sharply from the all-tile median than before, and "smooth plains" is identical. The crater query moved from above the median to below it — at 85 km a large crater is mostly its own flat floor, so this is plausible, but it is a change in behaviour and worth a second look if crater labels land ([#16](https://github.com/FionaL7/AnalogAtlas/issues/16)).

## Challenge fit

Requirements, judging criteria, dimension coverage, things to avoid and the submission checklist are all in [REQUIREMENTS.md](REQUIREMENTS.md).

**"Permanent Moon base" means the lunar south pole**, and that is now covered by the `moon_polar` index ([#26](https://github.com/FionaL7/AnalogAtlas/issues/26)). It carries three dimensions the equatorial index cannot: average solar illumination, permanently shadowed regions, and direct-to-Earth visibility. Those are the strongest answer to "go beyond visual similarity", because they are what a base is actually sited on and each has a real Earth counterpart. Site-by-site numbers: [TARGET-SITES.md](TARGET-SITES.md).

## Time and team

The event runs **14–15 Nov 2026**. We have **36 hours** to finish, and it has already started.

| | Dev A: data and ML | Dev B: app and radar |
| --- | --- | --- |
| First | Earth index (Earth Engine): tiles, slope and relief, embeddings | FastAPI wrapper around `analog.py`; React skeleton on a mocked API |
| Then | South pole (if decided) or crater labels from Robbins + precision@k | Pick 2–3 new candidates; RCM or Sentinel-1 roughness vs Mini-RF |
| Last | Accuracy charts, limitations | Close-study pages, deploy, demo (≤30 s video or ≤7 slides), write-up |

**Milestones**, in order:
1. Search works end to end on real data, Earth and Moon. This is the critical milestone; everything else builds on it.
2. Close study done for 2–3 sites.
3. Feature freeze, then the demo, slides and write-up.
4. Submit together, leaving a buffer before the deadline: **Sun 15 Nov, 11:59 p.m.** local time of our Local Event. Follow the [submission checklist](REQUIREMENTS.md#5-deliverable-checklist-space-apps-submission).

If we fall behind, cut fine-tuning first. Keep the radar close study: it's our strongest answer to "beyond visual similarity".

## Architecture

Stack, pages, user flows, the API/data contract and repo layout are in [ARCHITECTURE.md](ARCHITECTURE.md). Short version: the pipeline runs once, offline, in Python and writes a ~35 MB index. The React app is static-first — the whole demo path is precomputed JSON, so judging doesn't depend on a live server — plus a small FastAPI service for free-text and image search, which need CLIP at request time.

## Repo

Code: [FionaL7/AnalogAtlas](https://github.com/FionaL7/AnalogAtlas), branch `main`. Repo layout and what each piece does: [ARCHITECTURE.md](ARCHITECTURE.md#5-repo-layout).

Git ignores `data/` and `.venv/`. The shared copy of `data/` is on the GitHub Release [`data`](https://github.com/FionaL7/AnalogAtlas/releases/tag/data) ([#8](https://github.com/FionaL7/AnalogAtlas/issues/8)). Skill: [data-sync](../.claude/skills/data-sync/SKILL.md).

### Setup on a new machine

**Quick path:** set up the venv (below), then `python scripts/data.py pull` downloads `data/index/`, which is all the API needs. Add `raw tiles` to get the rasters and tiles too. Only rebuild with the steps below when you change the pipeline, then `python scripts/data.py push <folder>`.

Put the raw rasters in `data/raw/` first — download URLs, sizes and the `.lbl` gotcha are in the [README](../README.md#raw-data). PyTorch picks the device: Apple GPU (MPS) on a Mac, CUDA on an NVIDIA GPU, otherwise CPU (slower, but fine for 5k tiles).

#### Linux / macOS

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
python scripts/01_tiles.py moon     # ~17k tile requests to NASA Trek
python scripts/02_features.py moon  # ~5 min on an M1

# South pole (#26). Needs the four polar rasters in data/raw/ (see the README).
python scripts/01_tiles.py moon_polar     # 89 chips, ~1.5 min
python scripts/02_features.py moon_polar  # seconds

# Earth side (Earth Engine). Once per machine: earthengine authenticate
# with a Google account that has access to the EE_PROJECT in .env.
python scripts/00_ee_check.py       # should print "Earth Engine OK"
python scripts/01_tiles.py earth    # ~11.7k hillshades (EE) + Blue Marble (GIBS)
python scripts/02_features.py earth
```

#### Windows

In PowerShell:

```powershell
uv venv --python 3.12
.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
python scripts\01_tiles.py moon
python scripts\02_features.py moon
```

If HTTPS downloads fail with a certificate error, the Windows certificate store is probably missing a root that a data host relies on. We saw this with spaceappschallenge.org.

The outputs land in `data/index/`:
- `moon_meta.parquet`: one row per tile, with coordinates and physical features
- `moon_img.npy` and `moon_shade.npy`: 5,376 × 512 float16 embeddings, 5.5 MB each
- `moon_polar_*`: the same three files for the south pole, 89 rows, ~90 KB each

These are all the search API needs.

## Next steps

The next milestone is the Earth index. Every Earth–Moon feature in the app depends on it.

- [ ] **Decide hosting (blocking):** pick the hosts, claim the domain, get continuous deployment running so every push redeploys
- [ ] Build Mars: tasks in [MARS-PLAN.md](MARS-PLAN.md#tasks)
- [x] South pole: decided core (#6), built as `moon_polar` (#26)
- [x] Register Google Earth Engine (non-commercial use); project id lives in `.env`
- [ ] Earth pipeline in Earth Engine: tile grid, Copernicus DEM slope and relief, export a table
- [ ] Earth tile images (ASTER hillshade + imagery) and their CLIP embeddings
- [x] FastAPI wrapper around `analogatlas/analog.py` with `/search`, `/analogs`, `/twins`, `/tile`
- [x] `scripts/03_export.py`: static export of the demo path to `web/public/data/` (see [ARCHITECTURE.md](ARCHITECTURE.md#4-data-contract) §4.2)
- [x] React app: every backend output has a page ([#34](https://github.com/FionaL7/AnalogAtlas/issues/34))
- [ ] Run the CSA SAR tutorial on one RCM scene
- [x] Download Mini-RF and the polar LOLA / Diviner products
- [x] Add the fixed "Earth's limits" rows to the report card in `analog.py`

## Decisions

**Decided:**
- Moon first
- React frontend
- Laptop + Earth Engine + Colab for the pipeline (no paid compute there)
- Two developers: Dev A (data and ML), Dev B (app and radar)
- **Static export is not committed.** `web/public/data/` is gitignored; the deploy pulls `data/index/` from the `data` release and runs `scripts/03_export.py` before building the frontend ([#34](https://github.com/FionaL7/AnalogAtlas/issues/34), [#21](https://github.com/FionaL7/AnalogAtlas/issues/21)).
- **Hosting** ([#21](https://github.com/FionaL7/AnalogAtlas/issues/21)). Domain **marsneedsmaps.space** (Porkbun offer).
  - **API: Cloud Run**, scale to zero (~$1–2 over a 1–2 month judging period). Hugging Face was ruled out: Docker Spaces now need PRO. How it deploys and setup: [DEPLOY.md](DEPLOY.md).
  - Frontend host: Firebase Hosting (free tier); setup still to do.

- **Sharing `data/`: GitHub Release files** ([#8](https://github.com/FionaL7/AnalogAtlas/issues/8)), release tag `data`. Free, `gh` already works on every device, 2 GB per file. `python scripts/data.py pull|push`. The last push of a file wins.
- **Map library: Leaflet** (react-leaflet), one map per body in EPSG:4326 ([#24](https://github.com/FionaL7/AnalogAtlas/issues/24)). Trek and GIBS tiles are plain lat/lon, which Leaflet renders natively; MapLibre only does Web Mercator or globe. The polar pane uses a custom Leaflet CRS in `web/src/lib/polar.ts` — **no proj4leaflet**: the spherical stereographic forward/inverse is six lines and Leaflet takes a custom CRS directly.
- **South pole: core scope** ([#6](https://github.com/FionaL7/AnalogAtlas/issues/6), built in [#26](https://github.com/FionaL7/AnalogAtlas/issues/26)). It is a separate body, `moon_polar`, on a south polar stereographic grid — not a wider `moon`. Past ~60° an equirectangular tile stops being square on the ground (at 85°S it is 6 km wide and 85 km tall) and the imagery comes back as horizontal smear, so raising `MOON_MAX_ABS_LAT` produces confident nonsense rather than coverage. This is the same split every lunar data set makes, and why the Diviner cylindrical products stop at ±60.

### Open decisions

- **How much Mars?** Proposed by Rishabh: a full global `mars` index with the same search, report card and validation as the Moon ([MARS-PLAN.md](MARS-PLAN.md)). Waiting for Fiona's OK on [#7](https://github.com/FionaL7/AnalogAtlas/issues/7).
