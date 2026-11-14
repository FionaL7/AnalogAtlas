---
name: radar-roughness
description: Measure radar roughness (CPR) for a Moon site and an Earth candidate, for the close study (#19). Use when a report card needs the radar roughness row, or to check a new candidate's radar coverage.
---

# Radar roughness (CPR)

**CPR** (circular polarization ratio) = one number per place: how much a radar echo gets scrambled.
- ~0.2: smooth, mirror-like (calm water, fine dust)
- ~0.5: typical ground
- 0.8 and up: rough, blocky (fresh crater ejecta)

It senses roughness at roughly the radar wavelength (cm to m): what a lander footpad or rover wheel meets.

## Data
- **Moon:** LRO Mini-RF global CPR mosaic, S-band 12.6 cm, ~1 km/px. CPR is precomputed. Covers 63% of the Moon, but 79-100% at the Artemis south-pole sites.
- **Earth:** RCM compact-pol ARD on AWS, C-band 5.6 cm, 30 m. Free, no account. **Canada only, south of ~70N, and a patchy sample of dates**: always run `find-rcm` first.
- **Outside Canada:** Sentinel-1 via Microsoft Planetary Computer (free, global). It's VV/VH, not CPR: use the VH/VV ratio only to rank Earth sites, and label it as a different measure.

## Steps
1. Moon map, once per device: `python scripts/04_radar.py download-minirf`
2. Moon sites: `python scripts/04_radar.py moon-sites` → `data/index/moon_site_cpr.json`
3. Earth candidate: `python scripts/04_radar.py find-rcm <lat> <lon>`
   - Pick a **snow-free, late-summer** scene (Jul-Sep).
   - None found → tell the human. Options: order through EODMS with their CSA account, or Sentinel-1.
4. Download it: `python scripts/04_radar.py download-rcm <item-id> <short-name>`
5. Summarise: `radar.rcm_box(C.RAW / "rcm" / "<short-name>", *radar.box_around(lat, lon, half_km, C.EARTH_KM_PER_DEG))`

## On Windows with Application Control (rishabh-win)
rasterio and pyarrow DLLs are blocked natively. Run in Docker:
```
MSYS_NO_PATHCONV=1 docker run --rm -e PYTHONPATH=/repo -v "$(pwd -W):/repo" -w /repo python:3.12-slim \
  sh -c "apt-get update -qq && apt-get install -y -qq libexpat1 && pip install -q numpy rasterio python-dotenv==1.2.4 && python <script>"
```
Steps 1-3 need only numpy, no rasterio.

## Check it worked
- Calm water must come out **low** (~0.2). Convention verified on Labrador 2025-09-01: RR/RL gives water 0.23, land 0.55.
- Report `coverage` with every number. Below ~50%, say the value is uncertain.
- Run the tests: `python -m pytest tests/test_radar.py`

## Say on every report card
- **Different wavelengths:** 12.6 cm (Moon) vs 5.6 cm (Earth). They sense slightly different roughness scales.
- **Vegetation:** it scrambles radar on Earth, and the Moon has none. Prefer bare-ground candidates (polar desert, lava, rock barrens).
