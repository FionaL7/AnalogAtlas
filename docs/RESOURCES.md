# Resources

As of 14 Nov 2026. The first section is the official resource list from the [challenge page](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/), with tracking parameters removed from the links. The second section is every dataset we use or plan to use, and its status.

Accounts already registered: NASA Earthdata, Copernicus Data Space, JAXA G-Portal, CSA. Still needed: Google Earth Engine (non-commercial use, needs a Google Cloud project).

**Terms:** for non-US-government sites (CSA, ESA, JAXA), follow each site's data-use terms. Credit every dataset in the submission.

## Official resources (from the challenge page)

### NASA: Earth

| Resource | What it is | We use it for |
| --- | --- | --- |
| [NASA Earthdata Search](https://search.earthdata.nasa.gov/) | NASA's main portal for discovering and accessing Earth science observations | Finding ASTER, SRTM and other Earth products |
| [NASA Worldview](https://worldview.earthdata.nasa.gov/) | Interactive viewer for NASA satellite imagery and environmental observations (backed by GIBS) | Earth tile imagery and hillshade (the GIBS fallback in `tiles.py`) |

### NASA: Moon and Mars

| Resource | What it is | We use it for |
| --- | --- | --- |
| [NASA Planetary Data System (PDS)](https://pds.nasa.gov/) | NASA's long-term archive of planetary data from orbital, lander and rover missions: imagery, geoscience, atmospheres, plasma, cartography | Entry point for Moon and Mars data |
| [NASA Lunar Reconnaissance Orbiter (LRO)](https://pds-geosciences.wustl.edu/missions/lro/) | LRO observations from LROC, LOLA, Diviner, LEND, Mini-RF and other instruments | LOLA DEM (on disk), Mini-RF radar and LEND (to do) |
| [NASA LRO Diviner Lunar Data](https://pds-geosciences.wustl.edu/missions/lro/diviner.htm) | Lunar surface temperatures. The page points out that its **polar and resource products** can be compared with cold, ice-bearing or other extreme Earth environments | Rock abundance and temperature (on disk); polar products (to do) |

### Space agency partners

| Agency | Resource | What it is | We use it for |
| --- | --- | --- | --- |
| CSA | [RADARSAT Constellation Mission (RCM)](https://donnees-data.asc-csa.gc.ca/en/dataset/rcm) | Three C-band SAR satellites; images Earth day or night in any weather | Compact-pol radar roughness, the closest Earth match to Mini-RF |
| CSA | [RADARSAT-1](https://donnees-data.asc-csa.gc.ca/en/dataset/radarsat1) | SAR satellite launched in 1995; the whole archive is open | Fallback if RCM doesn't cover a candidate site |
| CSA | [Synthetic Aperture Radar (SAR) Python Tutorial](https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial) | Accessing and visualizing SAR imagery with Python and QGIS | Starting point for the radar close study |
| ESA | [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) | Free and open Sentinel data (land, ocean, atmosphere) with visualization and processing tools | Sentinel-1 radar, Sentinel-2 imagery, Copernicus DEM |
| ESA | [ESA Open Science Catalog](https://opensciencedata.esa.int/) | Catalog of open geoscience datasets, products, experiments and workflows | Not reviewed yet |
| JAXA | [JAXA G-Portal](https://gportal.jaxa.jp/gpr/) | Earth observation products from JAXA missions, searchable by variable | ALOS PALSAR L-band radar (optional) |

## Global Offers (optional free tools)

Free tools for Space Apps participants: [Global Offers](https://www.spaceappschallenge.org/2026/global-offers/). Claim an offer from that page when we need it.

| Offer | What it is | Might help with |
| --- | --- | --- |
| Microsoft Planetary Computer | Petabytes of open Earth data (Copernicus DEM, Sentinel, ASTER, ALOS) via a STAC API; no account needed | Alternative to Earth Engine for the Earth pipeline |
| Google Cloud | $300 credit for 90 days | Earth Engine's Cloud project, data storage, hosting the API |
| Microsoft Azure | $200 credit for 30 days | Hosting |
| Free domain + 1 year of hosting (Porkbun) | A free non-premium domain with SSL | A public URL for the app |
| Meteomatics Weather API | 1,000 queries a day of weather and climate data | Extra Earth climate data |
| GitHub Copilot, Miro, Microsoft Teams | Coding assistant, whiteboard, chat and calls | Team tools |

## Datasets we use

| Dataset | Body | Source | Used for | Status |
| --- | --- | --- | --- | --- |
| LROC WAC global mosaic (tiles) | Moon | [NASA Moon Trek](https://trek.nasa.gov/moon/) | Image embeddings, display | On disk |
| LOLA hillshade (tiles) | Moon | NASA Moon Trek | Terrain-shape embeddings | On disk |
| LOLA LDEM_16 (1.9 km/px) | Moon | PDS Geosciences (LRO) | Slope, relief, elevation | On disk |
| Diviner GDR L3 rock abundance, regolith temperature anomaly | Moon | PDS Geosciences (Diviner) | Landing hazards, surface material | On disk |
| LOLA / Diviner polar products | Moon | PDS Geosciences | South pole: illumination, cold traps, slopes | To do |
| Mini-RF radar (CPR) | Moon | PDS Geosciences (LRO) | Radar roughness close study | To do |
| Copernicus DEM, Sentinel-1, Sentinel-2 | Earth | Copernicus Data Space or Earth Engine | Slope, radar roughness, imagery | To do |
| ETOPO 2022 (60″, ~1.85 km/px) | Earth | NOAA NCEI | Slope and relief on the fallback path; same scale as LOLA | Fallback, in code |
| ASTER GDEM hillshade, Blue Marble | Earth | NASA Worldview / GIBS | Terrain-shape and image embeddings | 2,294 fallback tiles |
| NASA POWER climatology | Earth | [NASA POWER API](https://power.larc.nasa.gov/) | Temperature, precipitation, irradiance | Live API, nothing to download |
| RADARSAT Constellation Mission | Earth | CSA open data | Compact-pol radar, the closest match to Mini-RF | To do |
| ALOS PALSAR | Earth | JAXA G-Portal | L-band radar, shallow subsurface | Optional |
| Mars maps (MOLA, CTX) | Mars | [USGS Astrogeology: Interactive Maps: Mars](https://astrogeology-usgs.hub.arcgis.com/pages/interactive-maps-mars) | Mars extension | Only if we expand Mars; the page needs a browser to render |

Download URLs for the raw rasters are in the [README](../README.md).
