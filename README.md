# AnalogAtlas 🗺️

**Team Mars Needs Maps** — [NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/2026/find-a-team/mars-needs-maps/)

A search engine for planetary analogs: give it a Moon-base or Mars site, and it finds the Earth locations that are physically closest to it — then shows exactly where the resemblance holds and where it breaks down.

Built for the challenge [*Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/).

**🔗 Live demo: [analogatlas.earth](https://analogatlas.earth)**

## What we built

- **Earth analogs for a Moon-base or Mars site.** Rank Earth's land tiles by similarity to a lunar or Martian site, then show a report card of where the analogy holds and where it breaks down.
- **Find terrain on the Moon or Mars.** Describe an Earth landscape in words, or upload an image, and get the matching terrain on another body.
- **Both directions.** The same search, Earth → Moon/Mars or Moon/Mars → Earth.

Similarity isn't just "looks alike": CLIP image embeddings find candidates, then slope, relief, rock cover, temperature and radar roughness — all measured from NASA data on both bodies — decide whether the analogy actually holds physically.

## About the team

We're a team of curious minds excited about space exploration, planetary science, and using technology to solve real-world challenges. Our goal is to explore open datasets, combine scientific insight with data analysis and visualization, and build a solution that helps identify and compare promising terrestrial analogue sites.

| Member | Space Apps username |
| --- | --- |
| Fiona Lazarus | `fional` |
| Rishabh Khandelwal | `yesspark` |

## Docs

| Doc | What's in it |
| --- | --- |
| [docs/PLAN.md](docs/PLAN.md) | Status, decisions, next steps |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Stack, pages, API and data contract, repo layout |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | What we must deliver, and the submission checklist |
| [docs/TARGET-SITES.md](docs/TARGET-SITES.md) | The Moon and Mars sites we find analogs for |
| [docs/BRIEF.md](docs/BRIEF.md) | The challenge text, verbatim |
| [docs/RESOURCES.md](docs/RESOURCES.md) | Data sources and tools |
| [AGENTS.md](AGENTS.md) | How we work — read this before contributing |

## Run the pipeline

Download the [raw rasters](#raw-data) into `data/raw/` first. PyTorch picks its own device: Apple GPU (MPS) on a Mac, CUDA on an NVIDIA GPU, otherwise CPU — fine for 5k tiles, just slower.

```bash
uv venv --python 3.12
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
python scripts/01_tiles.py moon     # grid + tile download (~5.4k Moon tiles, ~11k requests to NASA Trek)
python scripts/02_features.py moon  # DEM/Diviner stats + CLIP embeddings (~5 min on an M1)
```

Pass `earth` or `mars` instead of `moon` for the other bodies.

If HTTPS downloads fail with a certificate error, your certificate store is probably missing a root one of the data hosts relies on. We hit this on Windows with spaceappschallenge.org.

<a id="raw-data"></a>
<details>
<summary><strong>Raw data</strong> — exact files, sizes and sources (click to expand)</summary>

Download once into `data/raw/`. **Take the `.lbl` label file next to each `.img`** — the PDS3 reader in `analogatlas/rasters.py` parses it for the array shape and scaling, so an `.img` alone won't load. ~656 MB total for the Moon:

| File | Size | Source |
| --- | --- | --- |
| `ldem_16.img` + `.lbl` | 32 MB | [PDS Geosciences — LRO LOLA GDR, cylindrical](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/) |
| `dgdr_ra_avg_cyl_032_img.img` + `.lbl` | 84 MB | [PDS Geosciences — LRO Diviner GDR L3, cylindrical](https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gdr_l3/cylindrical/img/) (rock abundance) |
| `dgdr_st_avg_cyl_032_img.img` + `.lbl` | 84 MB | same directory (regolith temperature anomaly) |
| `ETOPO_2022_v1_60s_N90W180_surface.nc` | 456 MB | [NOAA NCEI — ETOPO 2022, 60 arc-second](https://www.ngdc.noaa.gov/thredds/fileServer/global/ETOPO2022/60s/60s_surface_elev_netcdf/ETOPO_2022_v1_60s_N90W180_surface.nc) |

For the south pole (`moon_polar`, [#26](https://github.com/FionaL7/AnalogAtlas/issues/26)) — all four are PDS3 `.IMG` + `.LBL` on one south polar stereographic grid, so one reader handles them. ~380 MB total:

| File | Size | Source |
| --- | --- | --- |
| `ldem_75s_240m.img` + `.lbl` | 29 MB | [PDS Geosciences — LRO LOLA GDR, polar](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/) (topography, 240 m/px) |
| `AVGVISIB_75S_120M_201608.IMG` + `.LBL` | 116 MB | [PGDA — Lunar Polar Illumination](https://pgda.gsfc.nasa.gov/products/69) (mean solar illumination over 18.6 yr) |
| `LPSR_75S_120M_201608.IMG` + `.LBL` | 116 MB | same (permanently shadowed regions) |
| `AVGVISIB_75S_120M_201608_EARTH.IMG` + `.LBL` | 116 MB | same (mean Earth visibility, i.e. direct comms) |

The PGDA files download from `imbrium.mit.edu`; the links on the product page are the reliable ones.

For Mars (`mars`, [#38](https://github.com/FionaL7/AnalogAtlas/issues/38)) — ~2.3 GB total:

| File | Size | Source |
| --- | --- | --- |
| `Mars_MGS_MOLA_DEM_mosaic_global_463m.tif` | 2.1 GB | [USGS Astrogeology — MOLA DEM mosaic, 463 m](https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif) |
| `Mars_MGS_TES_Albedo_mosaic_global_7410m.tif` | 17 MB | [USGS Astrogeology — TES albedo mosaic](https://planetarymaps.usgs.gov/mosaic/Mars_MGS_TES_Albedo_mosaic_global_7410m.tif) |
| `tes_ruffdust.png` | 30 MB | [ASU — TES dust cover index (coloured rendering)](https://www.mars.asu.edu/data/tes_ruffdust/large/tes_ruffdust.png); decoded to a relative 0–1 index by hue |
| `tes_ti_putzig2007_20ppd.npy` | 52 MB | Assembled by `rasters.fetch_tes_ti()` from the [JMARS WMS](http://ms-mars.mars.asu.edu/tes_nightside_ti_putzig_2007?SERVICE=WMS&REQUEST=GetCapabilities) (the ASU `NBmap2007.tif` is only a coloured rendering) |
| `h2o_sr_5x5.tab` | 100 KB | [PDS Geosciences — Odyssey GRS water-equivalent hydrogen, 5° bins](https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/odgm_xxxx/data/smoothed/h2o_sr_5x5.tab) |
| `hydrous_crism.json` | 125 KB | Trek feature service `Hydrous_Mineral_Detections_CRISM_clon0` — down on 15 Nov 2026; `hydrous_count` stays NaN without it |

MOLA at 463 m is block-averaged ×4 to ~1.85 km before slope is measured, the same baseline as the Moon and Earth.

For validation ([#16](https://github.com/FionaL7/AnalogAtlas/issues/16)) — only needed to re-run `scripts/05_validate.py`. The labels it derives are saved to `data/index/{body}_craters.parquet`, so a machine that has the index does not need this download:

| File | Size | Source |
| --- | --- | --- |
| `robbins/lunar_crater_database_robbins_2018.csv` | 92 MB zipped, 227 MB unpacked | [USGS Astrogeology — Moon Crater Database v1 (Robbins)](https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_robbins) ([direct zip](https://astrogeology.usgs.gov/ckan/dataset/f89f5478-b69a-486c-b9b5-30d7b0c5ad2b/resource/c4f25cc2-4f8a-4207-a845-5e176da3ac5a/download/lunar_crater_database_robbins_2018)) |

Unpack the bundle's `data/*.csv` straight into `data/raw/robbins/`. It holds 1,296,796 craters with D ≥ 1 km; `analogatlas/craters.py` reads three of its columns.

Exact filenames are set in [`analogatlas/config.py`](analogatlas/config.py). LOLA LDEM_16 (1.9 km/px) and ETOPO 60s (1.85 km/px) sample at nearly the same resolution, which is what makes slope and relief comparable between the two bodies. The polar DEM is finer (240 m/px) and is block-averaged to 1.92 km before slope is measured, so it lands on the same baseline.

</details>

<details>
<summary><strong>Outputs</strong> — what the pipeline writes to <code>data/index/</code> (click to expand)</summary>

- `{body}_meta.parquet` — one row per tile: coordinates and physical features
- `{body}_img.npy`, `{body}_shade.npy` — `(N, 512)` float16 CLIP embeddings, row-aligned with the parquet
- `{body}_craters.parquet` — Robbins crater labels per lunar tile, for validation only ([#16](https://github.com/FionaL7/AnalogAtlas/issues/16)); never a search feature
- `validation.json` — how the search scores against independent data: crater retrieval, where each known analog ranks for its role, and the hold-one-out model check

`body` is `moon`, `moon_polar`, `mars` or `earth`. `moon_polar` is the lunar south pole on its own polar stereographic grid: past ~60° an equirectangular tile stops being square on the ground, so the pole cannot share the `moon` grid.

Moon: 5,376 tiles, 5.5 MB per matrix. Earth: ~11.7k tiles, ~12 MB per matrix.

`data/` and `.venv/` are not in git. See [docs/PLAN.md](docs/PLAN.md#open-decisions) for how the built index is shared between machines.

</details>

## Data sources and credits

Every dataset, with its source and status, is listed in [docs/RESOURCES.md](docs/RESOURCES.md). NASA: LRO (LOLA, Diviner, LROC WAC via Moon Trek, Mini-RF), Mars Trek, GIBS / Worldview, ASTER GDEM, NASA POWER. Space agency partners: CSA (RADARSAT RCM, SAR tutorial), ESA (Copernicus DEM, Sentinel-1/2). Other: USGS Astrogeology, ASU, NOAA ETOPO 2022.

Model weights: CLIP `ViT-B-32` / `laion2b_s34b_b79k` via [open_clip](https://github.com/mlfoundations/open_clip) (LAION), used for image and text embeddings.

## Use of AI tools

This project was built with AI assistance, disclosed as the Space Apps rules require:

- **Claude Code** (Anthropic) was used to write and review code and documentation. Commits it co-authored carry a `Co-Authored-By: Claude` trailer, so the AI-assisted history is auditable.
- **Verdict summaries are LLM-drafted, human-reviewed.** Each report card's verdict *tier* is rule-based from our measured data (`analogatlas/verdict.py`); the ~100-word summary beneath it is drafted by an LLM (`scripts/07_verdicts.py`) strictly from that card's numbers, then read by the team before shipping. The model is named in the app next to every summary and recorded in `data/index/verdicts.json`.
- The solution idea, the challenge approach, and the scientific interpretation are the team's own.
- No AI-generated imagery, video or audio is used in the project or its submission materials.
