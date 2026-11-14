"""Reference locations.

KNOWN_EARTH_ANALOGS: well-studied analog sites (approximate coordinates). Search
results near one of these are tagged "known"; everything else is a candidate
*new* analog, which is what the challenge asks us to surface.

MOON_SITES: presets for the "find Earth analogs for this lunar site" view.

MOON_BASE_REGIONS: NASA's Artemis candidate landing regions, plus Shackleton.
All are poleward of 80 S, OUTSIDE the current Moon index (60 S to 60 N), so
don't pass them to nearest_tile() until the polar index exists.
Coordinates are the IAU/USGS gazetteer centre of the named feature each region
sits on or near; regions are ~15x15 km. Source table: docs/TARGET-SITES.md.
"""

KNOWN_EARTH_ANALOGS = {
    "Atacama Desert (Yungay), Chile": (-24.08, -69.92),
    "Haughton Crater, Devon Island, Canada": (75.38, -89.68),
    "Death Valley, USA": (36.50, -117.10),
    "McMurdo Dry Valleys, Antarctica": (-77.50, 162.00),
    "Mauna Kea, Hawaii (PISCES)": (19.82, -155.47),
    "Kilauea, Hawaii": (19.40, -155.28),
    "Holuhraun / Askja, Iceland": (64.90, -16.80),
    "Craters of the Moon, Idaho, USA": (43.42, -113.52),
    "Meteor Crater, Arizona, USA": (35.03, -111.02),
    "San Francisco Volcanic Field (Cinder Lake), USA": (35.30, -111.50),
    "Mars Desert Research Station, Utah, USA": (38.41, -110.79),
    "Rio Tinto, Spain": (37.70, -6.55),
    "Svalbard (Bockfjorden), Norway": (79.40, 13.30),
    "Lanzarote (PANGAEA), Spain": (29.00, -13.70),
    "Ries Crater, Germany": (48.88, 10.57),
    "Lonar Crater, India": (19.98, 76.51),
    "Sudbury Basin, Canada": (46.60, -81.20),
    "Mistastin Lake Crater, Canada": (55.88, -63.30),
    "Dallol / Danakil Depression, Ethiopia": (14.24, 40.30),
    "Pilbara, Australia": (-21.20, 119.40),
    "Arkaroola, Australia": (-30.30, 139.30),
    "Qaidam Basin, China": (37.50, 94.00),
    "Wadi Rum, Jordan": (29.57, 35.42),
    "Mojave Desert (Desert RATS), USA": (35.00, -116.00),
    "Pavilion Lake, Canada": (50.87, -121.74),
}

MOON_SITES = {
    "Apollo 11 - Mare Tranquillitatis": (0.67, 23.47),
    "Apollo 15 - Hadley Rille": (26.13, 3.63),
    "Apollo 17 - Taurus-Littrow valley": (20.19, 30.77),
    "Marius Hills pit (lava-tube skylight)": (14.0917, -56.7701),    # LROC Pit Atlas
    "Mare Tranquillitatis pit (lava-tube skylight)": (8.3355, 33.222),  # LROC Pit Atlas
    "Aristarchus Plateau (pyroclastics)": (24.00, -47.50),
    "Gruithuisen Domes (silicic volcanism)": (36.20, -40.50),
    "Reiner Gamma (swirl)": (7.50, -59.00),
    "Ina (irregular mare patch)": (18.66, 5.30),
    "Copernicus crater": (9.62, -20.08),
    "Tycho crater": (-43.31, -11.36),
}

MOON_BASE_REGIONS = {
    "Peak near Cabeus B": (-82.26, -54.58),   # Cabeus B
    "Haworth": (-87.45, -5.17),               # Haworth crater
    "Malapert Massif": (-85.98, -1.67),       # Mons Malapert
    "Mons Mouton Plateau": (-84.60, 31.00),   # Mons Mouton
    "Mons Mouton": (-84.60, 31.00),           # Mons Mouton
    "Nobile Rim 1": (-85.28, 53.27),          # Nobile crater
    "Nobile Rim 2": (-85.28, 53.27),          # Nobile crater
    "de Gerlache Rim 2": (-88.48, -88.34),    # de Gerlache crater
    "Slater Plain": (-88.08, 111.29),         # Slater crater
    "Shackleton rim (classic base concept)": (-89.67, 129.78),  # Shackleton crater
}

EARTH_PRESETS = {
    "Atacama Desert, Chile": (-24.1, -69.9),
    "Meteor Crater, Arizona": (35.03, -111.02),
    "Craters of the Moon, Idaho": (43.42, -113.52),
    "Lonar Crater, India": (19.98, 76.51),
    "Erta Ale, Ethiopia": (13.60, 40.67),
    "Sahara - Tibesti Mountains, Chad": (21.0, 17.5),
    "Pinacate volcanic field, Mexico": (31.77, -113.50),
    "Namib Desert, Namibia": (-24.7, 15.3),
}
