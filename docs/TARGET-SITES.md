# Target Sites

The Moon and Mars sites we find Earth analogs for. As of 14 Nov 2026.

- **Coordinates:** latitude, longitude in °E (−180 to 180). From the [IAU/USGS Gazetteer of Planetary Nomenclature](https://planetarynames.wr.usgs.gov/) unless noted.
- **`~`** means approximate: the region lies on or near that point, not exactly at it.
- **Machine-readable copy:** `analogatlas/sites.py` (`MOON_BASE_REGIONS`, `MOON_SITES`, `MARS_SITES`).

## Moon: permanent base candidates (south pole)

These are NASA's nine candidate landing regions, announced in Oct 2024 for Artemis III. In Feb 2026 NASA made Artemis III an Earth-orbit test flight, so the **first landing is now Artemis IV (2028)**. The nine regions haven't changed.

- Each region is about 15 × 15 km ([NASA, 2022](https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-moon/)).
- NASA published names and a map, not coordinates ([NASA, 2024](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/)).
- Each coordinate below is the centre of the named feature the region sits on or near.

| ID | Region | Named feature | Lat | Lon | Why it matters | Source |
|---|---|---|---|---|---|---|
| M1 | Peak near Cabeus B | Cabeus B | ~−82.26 | ~−54.58 | Near permanently shadowed regions (PSRs) with ice signatures | [8058](https://planetarynames.wr.usgs.gov/Feature/8058) |
| M2 | Haworth | Haworth crater | ~−87.45 | ~−5.17 | Large PSR crater, a cold trap | [14502](https://planetarynames.wr.usgs.gov/Feature/14502) |
| M3 | Malapert Massif | Mons Malapert | ~−85.98 | ~−1.67 | High massif; good lighting and Earth visibility | [16338](https://planetarynames.wr.usgs.gov/Feature/16338) |
| M4 | Mons Mouton Plateau | Mons Mouton | ~−84.60 | ~31.00 | Flat plateau with long sunlit periods | [16070](https://planetarynames.wr.usgs.gov/Feature/16070) |
| M5 | Mons Mouton | Mons Mouton | ~−84.60 | ~31.00 | Mountain next to the plateau | [16070](https://planetarynames.wr.usgs.gov/Feature/16070) |
| M6 | Nobile Rim 1 | Nobile crater | ~−85.28 | ~53.27 | Crater rim near a PSR | [4321](https://planetarynames.wr.usgs.gov/Feature/4321) |
| M7 | Nobile Rim 2 | Nobile crater | ~−85.28 | ~53.27 | Crater rim near a PSR | [4321](https://planetarynames.wr.usgs.gov/Feature/4321) |
| M8 | de Gerlache Rim 2 | de Gerlache crater | ~−88.48 | ~−88.34 | Rim near Shackleton | [1439](https://planetarynames.wr.usgs.gov/Feature/1439) |
| M9 | Slater Plain | Slater crater | ~−88.08 | ~111.29 | Plain near the pole | [15325](https://planetarynames.wr.usgs.gov/Feature/15325) |
| M10 | Shackleton rim | Shackleton crater | ~−89.67 | ~129.78 | Classic base concept: near-continuous light at the rim, PSR inside. Not one of the nine. | [5450](https://planetarynames.wr.usgs.gov/Feature/5450) |

What these sites share:
- Highland, anorthosite-rich regolith.
- The Sun never rises more than about 1.5° above the horizon, so shadows are long. That's a navigation hazard.
- Extreme temperature contrast. Diviner measures PSRs below ~40 K, while sunlit ridges can exceed ~200 K.
- Steep slopes, a hazard for mobility.
- Cold traps that can hold water ice and other volatiles.

**Covered.** All ten are in the `moon_polar` index (75–90°S, south polar stereographic, 89 tiles of ~85 km). Each lands inside a cell, worst case 40 km from its centre. Built by `scripts/01_tiles.py moon_polar` then `scripts/02_features.py moon_polar` ([#26](https://github.com/FionaL7/AnalogAtlas/issues/26)).

What the index measures for each region, beyond slope and relief — these are the dimensions a base is actually sited on:

| Region | Slope | Relief | Permanent shadow | Illumination avg/max | Earth visibility |
|---|---|---|---|---|---|
| Shackleton rim | 7.7° | 5.30 km | 18.2% | 15.3 / **89.6%** | 26.1% |
| Nobile Rim 1–2 | 9.4° | 9.23 km | 13.7% | 17.0 / 85.8% | 21.5% |
| Haworth / Malapert Massif | 8.3° | 7.84 km | 23.5% | 10.5 / 84.5% | 28.6% |
| Mons Mouton (+ Plateau) | 8.6° | 7.16 km | 2.8% | 29.3 / 62.5% | **59.9%** |
| de Gerlache Rim 2 | 4.6° | 2.80 km | 8.0% | 21.8 / 78.5% | 29.9% |
| Slater Plain | 6.5° | 4.44 km | 19.7% | 17.4 / 68.2% | 24.2% |
| Peak near Cabeus B | 6.9° | 4.37 km | 9.3% | 26.3 / 58.7% | 53.7% |

This is a validation result, not just a data dump: the pipeline independently reproduces why these regions were picked. Shackleton's rim comes out as the best-lit point in the index, and Mons Mouton Plateau has the most Earth visibility and the least permanent shadow, matching "flat plateau with long sunlit periods".

Note the 85 km tiles are coarser than the ~15 × 15 km regions, so Haworth and Malapert Massif (≈50 km apart) share a cell, as do the two Nobile Rim sites and the two Mons Mouton entries.

**To check:** USGS has a data release of [Artemis III candidate landing site navigational grids](https://www.usgs.gov/data/down-selected-artemis-iii-candidate-landing-site-navigational-grids) (DOI 10.5066/P1MEQ6UK). It may contain the region outlines. It needs a browser to download.

## Moon: lava-tube habitats

Pits that may open into lava tubes, which could shelter a base from radiation and temperature swings. Coordinates are exact, from the [LROC Lunar Pit Atlas](https://lroc.im-ldi.com/atlases/pits/list).

| ID | Site | Lat | Lon | Size | Source |
|---|---|---|---|---|---|
| M11 | Marius Hills pit | 14.0917 | −56.7701 | Opening 55 × 49 m, 40 m deep | [Pit 1](https://lroc.im-ldi.com/atlases/pits/1) |
| M12 | Mare Tranquillitatis pit | 8.3355 | 33.222 | Opening 100 × 88 m, 105 m deep | [Pit 3](https://lroc.im-ldi.com/atlases/pits/3) |

Other lunar presets (Apollo sites, Aristarchus, Tycho and more) are in `MOON_SITES` in `analogatlas/sites.py`.

## Mars: landing and exploration sites (short)

The big regions are hundreds to thousands of km across. Their coordinates are region centres, so a real site would be a specific spot inside them.

| ID | Site | Type | Lat | Lon | Why it matters | Source |
|---|---|---|---|---|---|---|
| R1 | Arcadia Planitia | Human landing zone candidate (ice) | ~49.02 | ~−171.85 | Ice tens of cm below the surface, for in-situ resource use (ISRU); low elevation | [348](https://planetarynames.wr.usgs.gov/Feature/348) |
| R2 | Deuteronilus Mensae | Human landing zone candidate (glaciers) | ~45.11 | ~23.92 | Debris-covered glaciers | [1509](https://planetarynames.wr.usgs.gov/Feature/1509) |
| R3 | Utopia Planitia | Human landing zone candidate | ~46.74 | ~117.52 | Ground ice, scalloped terrain; near the Zhurong rover's landing site | [6260](https://planetarynames.wr.usgs.gov/Feature/6260) |
| R4 | Jezero crater | Perseverance rover site | 18.41 | 77.69 | River delta, carbonates; astrobiology | [14300](https://planetarynames.wr.usgs.gov/Feature/14300) |
| R5 | Gale crater | Curiosity rover site | −5.37 | 137.81 | Layered sediments, from clays to sulfates | [2071](https://planetarynames.wr.usgs.gov/Feature/2071) |
| R6 | Oxia Planum | Rosalind Franklin rover site | ~17.28 | ~−25.71 | Very clay-rich | [15821](https://planetarynames.wr.usgs.gov/Feature/15821) |
| R7 | Medusae Fossae | Wind-carved terrain | ~−2.17 | ~−164.20 | Wind-carved ridges (yardangs), friable deposits, a dust source | [3795](https://planetarynames.wr.usgs.gov/Feature/3795) |
| R8 | Arsia Mons skylights | Cave candidates | ~−8.26 | ~−120.09 | Possible lava-tube skylights on the flanks; the coordinate is the volcano's centre | [394](https://planetarynames.wr.usgs.gov/Feature/394) |

## Known Earth analogs (validation set, not findings)

- These are already well studied. Results near one are tagged "known", and the demo leads with *new* ones.
- Full list with coordinates: `KNOWN_EARTH_ANALOGS` in `analogatlas/sites.py`. It includes the Atacama, Haughton Crater, Death Valley, McMurdo Dry Valleys, Iceland, Hawaii, Rio Tinto, Svalbard, the Mars Desert Research Station, Lanzarote, the Pilbara and Meteor Crater.
- **Idea:** add the sites in ESA's catalogue of planetary analogues, to make the "known" tag more complete.
