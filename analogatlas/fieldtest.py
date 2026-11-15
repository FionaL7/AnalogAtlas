"""What to test at an Earth analog, read from its report card (requirement C6).

The brief asks how studying the Earth site helps Moon exploration. The answer
follows from which dimensions hold: a site whose slopes match is a place to
test rovers, one whose cold matches is a place to cold-soak hardware. Rules,
not ML: each suggestion names the rows it rests on, so it can be checked.

`what_to_test(rows, body)` takes `analog.breakdown()` output (DataFrame or list
of dicts) and returns {"tests": [...], "avoid": [...]}. Pass body="mars" for a
Mars report card:
  tests  something worth testing here, the exploration risk it reduces, and
         the rows that justify it
  avoid  compare rows that break down, so nobody tests the wrong thing here
"""
from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

HOLDS = 0.6      # same threshold the UI uses (web/src/lib/format.ts MATCH_HOLDS)
PARTLY = 0.3

# (title, risk it reduces, detail, {dimension: minimum match}).
# Every listed dimension must be present and reach its minimum.
RULES: list[tuple[str, str, str, dict[str, float]]] = [
    ("Rover mobility and traverse planning",
     "Getting stuck or tipping on slopes",
     "Slopes and relief match, so drive tests, path planners and slope-stability "
     "limits carry over. Traction will read high: Earth gravity is 6x the Moon's.",
     {"Median slope": HOLDS, "Local relief": HOLDS}),
    ("Terrain-relative navigation and hazard detection",
     "Landing on a hazard the camera mistook for flat ground",
     "The terrain looks the same to a vision model, so landing-camera and "
     "hazard-detection algorithms can be trained and checked here.",
     {"Terrain shape (ML)": HOLDS}),
    ("Dust handling and dry excavation",
     "Seals, joints and diggers failing in dry fine material",
     "Hyper-arid, so dry-regolith excavation and ISRU trials run without water "
     "changing the soil. Earth dust is rounder than lunar dust; treat wear as a lower bound.",
     {"Dryness": HOLDS}),
    ("Cold-soak survival of hardware",
     "Batteries, lubricants and electronics failing in deep cold",
     "The coldest surface temperature is close enough to stress heaters, "
     "batteries and lubricants the way a lunar night does.",
     {"Coldest surface": HOLDS}),
    ("Thermal cycling",
     "Fatigue from large day-night temperature swings",
     "A large surface temperature swing, so repeated hot-cold cycling of "
     "joints, panels and seals can be tested outdoors.",
     {"Surface temperature swing": PARTLY}),
    ("Solar power operations",
     "Power budgets built on the wrong sunlight",
     "Strong, clear-sky sunlight, so array output, pointing and dust on panels "
     "can be measured close to airless conditions.",
     {"Solar exposure": HOLDS}),
    ("Surviving long darkness",
     "A base losing power and heat through a long night",
     "Polar night lasts weeks here, so energy storage, heater budgets and crew "
     "routines for long darkness can be rehearsed on site.",
     {"Longest continuous darkness": PARTLY}),
]

# Polar rows with no Earth equivalent still shape what to test, as a caveat.
CAVEATS = {
    "Permanent shadow": "Permanently shadowed craters have no Earth equivalent at this "
                        "scale: ice prospecting in true cold traps cannot be rehearsed here.",
    "Direct-to-Earth comms": "Earth is always in view here; loss-of-signal operations "
                             "need a simulated comms blackout.",
}


# Mars: the same idea, on the rows `analog.mars_rows` produces.
MARS_RULES: list[tuple[str, str, str, dict[str, float]]] = [
    ("Rover mobility and traverse planning",
     "Getting stuck or tipping on slopes",
     "Slopes and relief match, so drive tests, path planners and slope-stability "
     "limits carry over. Traction will read high: Earth gravity is 2.6x Mars's.",
     {"Median slope": HOLDS, "Local relief": HOLDS}),
    ("Terrain-relative navigation and hazard detection",
     "Landing on a hazard the camera mistook for flat ground",
     "The terrain looks the same to a vision model, so landing-camera and "
     "hazard-detection algorithms can be trained and checked here.",
     {"Terrain shape (ML)": HOLDS}),
    ("Wheel and soil mechanics",
     "Wheels sinking or slipping in loose ground (as Spirit and Opportunity did)",
     "The ground is about as loose or as rocky as the Mars site, so wheel sinkage, "
     "slip and digging forces can be measured in comparable material.",
     {"Surface material": HOLDS}),
    ("Dust on hardware",
     "Dust coating solar panels, optics and seals",
     "Dusty air here, so dust build-up on panels, cleaning methods and seal wear "
     "can be tested. Mars dust is finer and electrostatically charged; treat results as a lower bound.",
     {"Dust": HOLDS}),
    ("Drilling for ground ice (ISRU)",
     "Drills jamming or ice melting and refreezing in the hole",
     "Frozen ground under a dry surface, so ice drilling, sampling and water "
     "extraction can be rehearsed in the right kind of ground.",
     {"Ground ice": HOLDS}),
    ("Life detection at low biomass",
     "False positives from Earth contamination, false negatives from weak instruments",
     "Hyper-arid soil holds very little life or organic matter, so life-detection "
     "instruments and clean sampling can be tested near Mars-like detection limits.",
     {"Dryness": HOLDS}),
    ("Cold-soak survival of hardware",
     "Batteries, lubricants and electronics failing in deep cold",
     "The coldest surface temperature is close enough to stress heaters, "
     "batteries and lubricants the way a Mars night does.",
     {"Coldest surface": HOLDS}),
    ("Thermal cycling",
     "Fatigue from large day-night temperature swings",
     "A large surface temperature swing every day, as on Mars, so repeated "
     "hot-cold cycling of joints, panels and seals can be tested outdoors.",
     {"Surface temperature swing": PARTLY}),
    ("Remote-sensing ground truth",
     "Misreading orbital maps of the landing site",
     "The ground is about as bright as the Mars site, so cameras and "
     "spectrometers can be calibrated against a similar surface.",
     {"Surface brightness (albedo)": HOLDS}),
]

MARS_CAVEATS = {
    "Water-altered minerals": "Orbiters see water-altered minerals at the Mars site. We have no "
                              "global Earth mineral map, so check this site's geology before "
                              "planning sample-science tests.",
    "Near-surface water": "The hydrogen at the Mars site is regional (about 300 km) and has no "
                          "matching Earth measurement: do not plan water-extraction tests on it.",
}

BODY_RULES = {"moon": (RULES, CAVEATS, "Moon"), "mars": (MARS_RULES, MARS_CAVEATS, "Mars")}


def _records(rows) -> list[dict]:
    if isinstance(rows, pd.DataFrame):
        rows = rows.to_dict("records")
    return list(rows)


def _match(row: dict) -> float | None:
    m = row.get("match")
    if m is None:
        return None
    try:
        m = float(m)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(m) else m


def what_to_test(rows: Iterable[dict] | pd.DataFrame, body: str = "moon") -> dict[str, list[dict]]:
    """`body`: "mars" for a Mars report card; anything else uses the Moon rules."""
    rules, caveats, name = BODY_RULES.get(body, BODY_RULES["moon"])
    recs = _records(rows)
    by_dim = {r["dimension"]: r for r in recs}

    tests = []
    for title, risk, detail, need in rules:
        matches = {d: _match(by_dim[d]) if d in by_dim else None for d in need}
        if all(m is not None and m >= need[d] for d, m in matches.items()):
            tests.append(dict(title=title, risk=risk, detail=detail,
                              based_on=list(need),
                              strength=round(min(matches.values()), 3)))
    tests.sort(key=lambda t: -t["strength"])

    avoid = []
    for r in recs:
        m = _match(r)
        if r.get("kind", "compare") == "compare" and m is not None and m < PARTLY:
            avoid.append(dict(dimension=r["dimension"],
                              reason=f"{r['dimension']} breaks down here "
                                     f"({name} {r.get('moon')}, Earth {r.get('earth')})"))
    for dim, text in caveats.items():
        if dim in by_dim:
            avoid.append(dict(dimension=dim, reason=text))
    return dict(tests=tests, avoid=avoid)
