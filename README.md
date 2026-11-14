# AnalogAtlas

Search engine for planetary analogs, built for the NASA Space Apps 2026 challenge [*Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/).

- **Earth analogs for a Moon-base site.** Rank Earth's land tiles by similarity to a lunar site, then show a report card of where the analogy holds and where it breaks down.
- **Find terrain on the Moon.** Describe an Earth landscape in words, or upload an image, and get the matching lunar terrain.
- **Both directions.** The same search, Earth → Moon or Moon → Earth.

Similarity is not just "looks alike": CLIP embeddings find candidates, and slope, relief, rock cover, temperature and radar roughness — measured from NASA data on both bodies — decide whether the analogy actually holds.

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

### macOS / Linux

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
python scripts/01_tiles.py moon     # grid + tile download (~5.4k Moon tiles, ~11k requests to NASA Trek)
python scripts/02_features.py moon  # DEM/Diviner stats + CLIP embeddings (~5 min on an M1)
```

### Windows (PowerShell)

```powershell
uv venv --python 3.12
.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
python scripts\01_tiles.py moon
python scripts\02_features.py moon
```

Pass `earth` instead of `moon` for the GIBS + ETOPO fallback path (~11.7k tiles). The main Earth path is moving to Google Earth Engine — see [docs/PLAN.md](docs/PLAN.md).

If HTTPS downloads fail with a certificate error, your certificate store is probably missing a root one of the data hosts relies on. We hit this on Windows with spaceappschallenge.org.

## Raw data

Download once into `data/raw/`. **Take the `.lbl` label file next to each `.img`** — the PDS3 reader in `analogatlas/rasters.py` parses it for the array shape and scaling, so an `.img` alone won't load. ~656 MB total.

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

Exact filenames are set in [`analogatlas/config.py`](analogatlas/config.py). LOLA LDEM_16 (1.9 km/px) and ETOPO 60s (1.85 km/px) sample at nearly the same resolution, which is what makes slope and relief comparable between the two bodies. The polar DEM is finer (240 m/px) and is block-averaged to 1.92 km before slope is measured, so it lands on the same baseline.

## Outputs

`data/index/`, which is everything the search needs:

- `{body}_meta.parquet` — one row per tile: coordinates and physical features
- `{body}_img.npy`, `{body}_shade.npy` — `(N, 512)` float16 CLIP embeddings, row-aligned with the parquet

`body` is `moon`, `moon_polar` or `earth`. `moon_polar` is the lunar south pole on its own polar stereographic grid: past ~60° an equirectangular tile stops being square on the ground, so the pole cannot share the `moon` grid.

Moon: 5,376 tiles, 5.5 MB per matrix. Earth: ~11.7k tiles, ~12 MB per matrix.

`data/` and `.venv/` are not in git. See [docs/PLAN.md](docs/PLAN.md#open-decisions) for how the built index is shared between machines.

## Data sources and credits

Every dataset, with its source and status, is listed in [docs/RESOURCES.md](docs/RESOURCES.md). NASA: LRO (LOLA, Diviner, LROC WAC via Moon Trek, Mini-RF), GIBS / Worldview, ASTER GDEM, NASA POWER. Space agency partners: CSA (RADARSAT RCM, SAR tutorial), ESA (Copernicus DEM, Sentinel-1/2). Other: NOAA ETOPO 2022.

## Use of AI tools

This project was built with AI assistance, disclosed as the Space Apps rules require:

- **Claude Code** (Anthropic) was used to write and review code and documentation. Commits it co-authored carry a `Co-Authored-By: Claude` trailer, so the AI-assisted history is auditable.
- The solution idea, the challenge approach, and the scientific interpretation are the team's own.
- No AI-generated imagery, video or audio is used in the project or its submission materials.

Model weights: CLIP `ViT-B-32` / `laion2b_s34b_b79k` via [open_clip](https://github.com/mlfoundations/open_clip) (LAION), used for image and text embeddings.
