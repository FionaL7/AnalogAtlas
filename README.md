# AnalogAtlas

Search engine for planetary analogs, built for the NASA Space Apps challenge on terrestrial analogs.

Plan and current status for the team: [docs/PLAN.md](docs/PLAN.md).

* **Find terrain on the Moon**: describe an Earth landscape in words (or upload a photo) and get the matching lunar terrain.
* **Earth analogs for a lunar site**: rank every land tile on Earth by similarity to a lunar site, then show a report card of where the analogy holds and where it breaks down.
* **Lunar twins of an Earth place**: the same search in the other direction.

## Run

```bash
source .venv/bin/activate          # or: uv venv --python 3.12 && uv pip install -r requirements.txt
python scripts/01_tiles.py         # build grids + download tiles  (~5.4k Moon, ~11.7k Earth)
python scripts/02_features.py      # DEM/Diviner stats + CLIP embeddings
# search API (FastAPI) and React frontend: not built yet
```

The raw rasters go in `data/raw/`. They are downloaded once:

| File | URL |
|---|---|
| `ldem_16.img/.lbl` | pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ |
| `dgdr_ra_avg_cyl_032_img.*`, `dgdr_st_avg_cyl_032_img.*` | pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gdr_l3/cylindrical/img/ |
| `ETOPO_2022_v1_60s_N90W180_surface.nc` | ngdc.noaa.gov/thredds/fileServer/global/ETOPO2022/60s/60s_surface_elev_netcdf/ |

## Layout

```
analogatlas/config.py    paths, tile scale, endpoints
analogatlas/tiles.py     Moon (NASA Trek WMTS) and Earth (NASA GIBS WMS) tiling at equal ground scale
analogatlas/rasters.py   PDS3 IMG reader; slope/relief/rock/temperature per tile
analogatlas/embed.py     CLIP image/text embeddings (rotation-averaged hillshades)
analogatlas/analog.py    search, cross-body matching, NASA POWER climate, analog report card
analogatlas/sites.py     known Earth analogs, lunar presets
```
