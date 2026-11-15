# Mars plan

As of 15 Nov 2026. Scope decision: [#7](https://github.com/FionaL7/AnalogAtlas/issues/7). Tasks: `gh issue list --label mars`.

## Goal

Mars gets the same treatment as the Moon: a global index, Earth analogs for 7 landing sites, a report card with measured dimensions, and its own validation.

Why it helps us win:

- **Relevance:** the challenge title gives Mars equal billing. Before this we had no Mars data.
- **Creativity:** Mars fills the dimensions the Moon can't (dust, surface material, ground ice, water-altered minerals). One engine, two worlds.
- **Validity:** a second, independent body tests that the method transfers. Same slope baseline, same hold-out checks.
- **Surprise:** "dual-use" Earth sites that score high for both the Moon and Mars.

## Design

- **Body id:** `mars`. Global, ±60° latitude (all 7 sites in [TARGET-SITES.md](TARGET-SITES.md) are inside).
- **Grid:** NASA Trek zoom-7 tiles, 1.406° = ~83 km (Moon and Earth tiles are ~85 km). ~21,800 tiles. Same tile matrix as the Moon, so `moon_grid` and the #27 crop fix are reused.
- **Tile id:** `mars_7_{y}_{x}`.
- **Index size:** ~45 MB for the two embedding matrices. Fits the Hugging Face Space.

### Data (all checked reachable on 15 Nov unless marked)

Trek base: `https://trek.nasa.gov/tiles/Mars/EQ/{layer}/1.0.0/default/default028mm/{z}/{row}/{col}.jpg`

| Use | Mars source | Earth counterpart |
|---|---|---|
| Terrain shape (CLIP) | Trek `Mars_MOLA_blend200ppx_HRSC_Shade_clon0dd_200mpp_lzw` (grey hillshade) | ASTER shaded relief (have) |
| Look (CLIP) | Trek `Mars_Viking_MDIM21_ClrMosaic_global_232m` | Blue Marble (have) |
| Elevation, slope, relief | `https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif` (2.1 GB), block-averaged to ~1.85 km | Copernicus DEM at 1.85 km (have) |
| Surface material | TES thermal inertia: `https://www.mars.asu.edu/data/tes_putzigti/nightside2007/NBmap2007.tif` (78 MB). TES albedo: USGS `Mars_MGS_TES_Albedo_mosaic_global_7410m.tif` (17 MB, not download-tested) | `lst_swing_c` (have) + MODIS albedo (new) |
| Dust | TES dust cover index: `https://www.mars.asu.edu/data/tes_ruffdust/large/tes_ruffdust.png` (coloured PNG: decode colour to value, or drop) | MERRA-2 dust `DUEXTTAU`, Earth Engine `NASA/GSFC/MERRA/aer/2` (new) |
| Water / ground ice | GRS water-equivalent hydrogen: `https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/odgm_xxxx/data/smoothed/h2o_sr_5x5.tab` (5° bins, coarse) | `aridity`, `precip_mm` (have) + mean surface temperature from MODIS LST (new) |
| Water-altered minerals | Trek `Hydrous_Mineral_Detections_CRISM_clon0` (points → count per tile) | `aqueous` tag on known sites only. No global Earth layer |
| Temperature | Modelled from latitude, albedo and thermal inertia. Label as modelled, as on the Moon | MODIS LST (have) |

Not usable now: SWIM ice maps (site down), OMEGA/CRISM global mineral map (portal down), full Mars Climate Database (request form), EMIT minerals (login, swath files, 54°N–54°S only).

### Contract

Both tracks build against this. Change it only with a comment on the Team log.

`data/index/mars_meta.parquet`, `mars_img.npy`, `mars_shade.npy`, `mars_order.json`: same rules as the Moon ([ARCHITECTURE.md §4.1](ARCHITECTURE.md#41-index-files-dataindex--produced-by-the-pipeline)).

| Column | Body | Meaning |
|---|---|---|
| grid columns, `z`, `y`, `x` | mars | As on the Moon |
| `elev_km`, `relief_km`, `slope_med`, `slope_p90` | mars | As on the Moon, at the ~1.85 km baseline |
| `thermal_inertia` | mars | TES, J m⁻² K⁻¹ s⁻½. Low = dust, high = rock |
| `albedo` | mars, earth | 0–1 |
| `dust_index` | mars | Relative dust cover, 0–1, 1 = dustiest, decoded from the TES dust cover index colour map (the index values themselves are not recoverable) |
| `weh_pct` | mars | GRS water-equivalent hydrogen, weight %. Regional (5°) |
| `hydrous_count` | mars | CRISM hydrated-mineral detections in the tile |
| `t_max_k`, `t_min_k` | mars | Modelled |
| `dust_aod` | earth | MERRA-2 mean dust optical depth |
| `lst_mean_c` | earth | Mean surface temperature. Below 0 = frozen ground |

Code must cope with any Mars-only or new Earth column being absent or NaN (as `breakdown()` already does for `rock_abundance`).

### Honesty rules (Validity)

- Each report-card row says **measured**, **modelled** or **no Earth equivalent**.
- Fixed "breaks down" rows for Mars: 0.6 kPa CO₂ atmosphere, 38% gravity, radiation, perchlorates, global dust storms.
- GRS is 5° (~300 km): show it as regional context, never as a per-tile match.
- Thermal inertia vs Earth day–night swing is a proxy, and Earth's air and moisture distort it. Say so.

## Tasks

Two tracks with no shared files, so two devices or worktrees can work at once. Pick the first unclaimed task in a track whose "Needs" are closed.

### Track A: data (`track:data`)

| Task | Owns | Needs |
|---|---|---|
| A1 Mars tiles | `config.py`, `tiles.py`, `01_tiles.py` | — |
| A2 Mars features + index | `rasters.py`, `02_features.py`, README raw-data section, `RESOURCES.md` | A1 |
| A3 Earth counterpart columns | Earth Engine feature code, `earth_meta` | —. Needs `EE_PROJECT` |
| A4 Mars validation | `05_validate.py`, `04_train.py`, `learn.py`, `Methodology.tsx` | A2, B1 |

### Track B: scoring and app (`track:app`)

| Task | Owns | Needs |
|---|---|---|
| B1 Mars scoring + report card | `analog.py`, `fieldtest.py`, `traps.py`, `portfolio.py`, `tests/` | —. Uses the synthetic index |
| B2 Web app on mocks | `web/src/` except `Methodology.tsx` and `Discoveries.tsx` | — |
| B3 Sites, export, API | `sites.py`, `03_export.py`, `api/`, `deploy/hf-space/`, `TARGET-SITES.md` | A2, B1 |

### Finish

| Task | Owns | Needs |
|---|---|---|
| C1 Showcase + submission | `Discoveries.tsx`, `docs/figures/`, slides (#22), `REQUIREMENTS.md`, `PLAN.md` | B2, B3, A4 |

**Start now, in parallel:** A1, A3, B1, B2.

**Rules for agents:**

- Only edit the files your task owns. Need a change elsewhere? Comment on that task's issue.
- A2 and A3 change files in `data/`: push them to the `data` release and post on the Team log.
- #32 (polar scoring) also edits `analog.py`. Do it in the B1 session or before it.

## Stretch

- Mars crater retrieval check with the Robbins & Hynek Mars crater catalog (mirrors #16).
- Finer imagery for the close study: Trek `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018`, or CTX.
- SWIM ice maps if the site comes back: per-tile ice for Arcadia, Deuteronilus, Utopia.
- More validation labels from the ESA Catalogue of Planetary Analogues.

## Risks

| Risk | Plan |
|---|---|
| TES dust PNG can't be decoded to values | Leave `dust_index` NaN; keep dust as a "breaks down" row plus Earth dust as context |
| Viking colour vs Blue Marble look too different for CLIP | A4 measures it. If the look channel hurts, raise the shade weight for `mars` |
| Mars slope too smooth at 463 m | Same ~1.85 km baseline on all bodies, so the comparison stays fair. State it |
| Earth Engine only on Fiona's project | A3 runs on a device with `EE_PROJECT` set |
