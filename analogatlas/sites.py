"""Reference locations.

KNOWN_EARTH_ANALOGS: well-studied analog sites (approximate coordinates). Search
results near one of these are tagged "known"; everything else is a candidate
*new* analog, which is what the challenge asks us to surface.

MOON_SITES: presets for the "find Earth analogs for this lunar site" view.

MOON_BASE_REGIONS: NASA's Artemis candidate landing regions, plus Shackleton.
All are poleward of 80 S, so they belong to the `moon_polar` index, NOT to
`moon` (60 S to 60 N). Passing them to nearest_tile() on the `moon` index
would clamp to the index edge and answer for a place ~25 deg away.
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
    # added for the analog model (#29); field-test and literature analog sites
    "Axel Heiberg Island (Expedition Fiord), Canada": (79.41, -90.73),
    "Manicouagan Crater, Canada": (51.38, -68.70),
    "Vredefort Dome, South Africa": (-27.00, 27.50),
    "Gosses Bluff, Australia": (-23.82, 132.31),
    "Wolfe Creek Crater, Australia": (-19.17, 127.80),
    "Shoemaker Crater, Australia": (-25.87, 120.88),
    "Tenoumer Crater, Mauritania": (22.92, -10.40),
    "Aorounga Crater, Chad": (19.10, 19.25),
    "Kamil Crater, Egypt": (22.02, 26.09),
    "Teide, Tenerife, Spain": (28.27, -16.64),
    "Mount Etna, Italy (ARCHES)": (37.75, 14.99),
    "Lava Beds National Monument, USA": (41.71, -121.51),
    "Undara lava tubes, Australia": (-18.25, 144.60),
    "Namib Desert (Sossusvlei), Namibia": (-24.73, 15.30),
    "Ladakh (Tso Kar), India": (33.30, 77.99),
    "Salar de Uyuni, Bolivia": (-20.13, -67.49),
    "Licancabur, Bolivia/Chile": (-22.83, -67.88),
    "Shark Bay (Hamelin Pool), Australia": (-26.40, 114.16),
    "El Pinacate, Mexico": (31.77, -113.50),
    "Bonneville Salt Flats, USA": (40.76, -113.89),
    "Makhtesh Ramon, Israel (D-MARS / AMADEE-20)": (30.60, 34.80),
}

# What each known analog is an analog *for* (training labels for learn.py).
#   target:  "moon" and/or "mars"
#   roles:   volcanic, impact, polar, arid, aqueous, lava_tube
#   surface: True if the site is used for what its *surface* is like (field
#            tests, terrain, regolith). False for process analogs whose surface
#            looks nothing like the Moon or Mars (forested or eroded impact
#            structures, lakes, springs); learn.py trains on surface sites only.
def _a(target, roles, surface=True):
    return {"target": tuple(target.split()), "roles": tuple(roles.split()), "surface": surface}


ANALOG_INFO = {
    "Atacama Desert (Yungay), Chile": _a("mars moon", "arid"),
    "Haughton Crater, Devon Island, Canada": _a("mars moon", "impact polar"),
    "Death Valley, USA": _a("mars", "arid"),
    "McMurdo Dry Valleys, Antarctica": _a("mars", "polar arid"),
    "Mauna Kea, Hawaii (PISCES)": _a("moon mars", "volcanic"),
    "Kilauea, Hawaii": _a("moon mars", "volcanic"),
    "Holuhraun / Askja, Iceland": _a("moon mars", "volcanic"),
    "Craters of the Moon, Idaho, USA": _a("moon mars", "volcanic lava_tube"),
    "Meteor Crater, Arizona, USA": _a("moon", "impact arid"),
    "San Francisco Volcanic Field (Cinder Lake), USA": _a("moon", "volcanic arid"),
    "Mars Desert Research Station, Utah, USA": _a("mars", "arid"),
    "Rio Tinto, Spain": _a("mars", "aqueous", surface=False),
    "Svalbard (Bockfjorden), Norway": _a("mars", "volcanic polar"),
    "Lanzarote (PANGAEA), Spain": _a("moon mars", "volcanic lava_tube"),
    "Ries Crater, Germany": _a("moon", "impact", surface=False),
    "Lonar Crater, India": _a("moon mars", "impact", surface=False),
    "Sudbury Basin, Canada": _a("moon", "impact", surface=False),
    "Mistastin Lake Crater, Canada": _a("moon", "impact", surface=False),
    "Dallol / Danakil Depression, Ethiopia": _a("mars", "aqueous arid"),
    "Pilbara, Australia": _a("mars", "aqueous arid"),
    "Arkaroola, Australia": _a("mars", "arid"),
    "Qaidam Basin, China": _a("mars", "arid"),
    "Wadi Rum, Jordan": _a("mars", "arid"),
    "Mojave Desert (Desert RATS), USA": _a("moon mars", "arid volcanic"),
    "Pavilion Lake, Canada": _a("mars", "aqueous", surface=False),
    "Axel Heiberg Island (Expedition Fiord), Canada": _a("mars", "polar aqueous"),
    "Manicouagan Crater, Canada": _a("moon mars", "impact", surface=False),
    "Vredefort Dome, South Africa": _a("moon", "impact", surface=False),
    "Gosses Bluff, Australia": _a("mars moon", "impact arid"),
    "Wolfe Creek Crater, Australia": _a("moon mars", "impact arid"),
    "Shoemaker Crater, Australia": _a("mars", "impact arid"),
    "Tenoumer Crater, Mauritania": _a("moon mars", "impact arid"),
    "Aorounga Crater, Chad": _a("mars", "impact arid"),
    "Kamil Crater, Egypt": _a("moon", "impact arid"),
    "Teide, Tenerife, Spain": _a("mars moon", "volcanic"),
    "Mount Etna, Italy (ARCHES)": _a("moon", "volcanic"),
    "Lava Beds National Monument, USA": _a("moon mars", "lava_tube volcanic"),
    "Undara lava tubes, Australia": _a("moon mars", "lava_tube volcanic", surface=False),
    "Namib Desert (Sossusvlei), Namibia": _a("mars", "arid"),
    "Ladakh (Tso Kar), India": _a("mars", "arid polar"),
    "Salar de Uyuni, Bolivia": _a("mars", "arid aqueous"),
    "Licancabur, Bolivia/Chile": _a("mars", "volcanic arid"),
    "Shark Bay (Hamelin Pool), Australia": _a("mars", "aqueous", surface=False),
    "El Pinacate, Mexico": _a("moon mars", "volcanic arid"),
    "Bonneville Salt Flats, USA": _a("mars", "arid aqueous"),
    "Makhtesh Ramon, Israel (D-MARS / AMADEE-20)": _a("mars", "arid"),
}
assert set(ANALOG_INFO) == set(KNOWN_EARTH_ANALOGS)

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
