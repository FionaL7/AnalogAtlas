/**
 * Mocked API responses, typed against the real contract.
 *
 * They exist so the app can be built and demoed before the Earth index (#11)
 * and the API (#13) land. Values are plausible, not real — anything shown to a
 * judge comes from the static export (§4.2), never from here.
 */
import type {
  AnalogsRequest,
  AnalogsResponse,
  SearchRequest,
  SearchResponse,
  Site,
  TwinsResponse,
} from "./types";

/** A few presets from analogatlas/sites.py, including Artemis base regions. */
export const MOCK_SITES: Site[] = [
  // Base regions are all poleward of 80°S, so they belong to `moon_polar` and
  // are drawn in the polar pane -- not to `moon`, whose grid cannot hold them.
  { id: "shackleton-rim", body: "moon_polar", name: "Shackleton rim", lat: -89.67, lon: 129.78,
    is_base_region: true, blurb: "Classic base concept: near-permanent sunlight on the rim, cold traps below." },
  { id: "mons-mouton", body: "moon_polar", name: "Mons Mouton Plateau", lat: -84.6, lon: 31.0,
    is_base_region: true, blurb: "Artemis candidate region; a broad, comparatively flat plateau." },
  { id: "haworth", body: "moon_polar", name: "Haworth", lat: -87.45, lon: -5.17, is_base_region: true },
  { id: "apollo-15", body: "moon", name: "Apollo 15 — Hadley Rille", lat: 26.13, lon: 3.63,
    blurb: "Mare surface cut by a sinuous rille, against the Apennine front." },
  { id: "tycho", body: "moon", name: "Tycho crater", lat: -43.31, lon: -11.36 },
  // The seven Mars sites in docs/TARGET-SITES.md (R1-R7).
  { id: "arcadia-planitia", body: "mars", name: "Arcadia Planitia", lat: 49.02, lon: -171.85,
    blurb: "Human landing zone candidate: ice tens of centimetres below the surface, at low elevation." },
  { id: "deuteronilus-mensae", body: "mars", name: "Deuteronilus Mensae", lat: 45.11, lon: 23.92,
    blurb: "Human landing zone candidate: debris-covered glaciers." },
  { id: "utopia-planitia", body: "mars", name: "Utopia Planitia", lat: 46.74, lon: 117.52,
    blurb: "Human landing zone candidate: ground ice and scalloped terrain, near the Zhurong rover." },
  { id: "jezero-crater", body: "mars", name: "Jezero crater", lat: 18.41, lon: 77.69,
    blurb: "Perseverance rover site: a river delta with carbonates." },
  { id: "gale-crater", body: "mars", name: "Gale crater", lat: -5.37, lon: 137.81,
    blurb: "Curiosity rover site: layered sediments, from clays to sulfates." },
  { id: "oxia-planum", body: "mars", name: "Oxia Planum", lat: 17.28, lon: -25.71,
    blurb: "Rosalind Franklin rover site: very clay-rich plains." },
  { id: "medusae-fossae", body: "mars", name: "Medusae Fossae", lat: -2.17, lon: -164.2,
    blurb: "Wind-carved ridges in soft deposits, and a source of dust." },
  { id: "atacama", body: "earth", name: "Atacama Desert, Chile", lat: -24.1, lon: -69.9 },
];

const earthTile = (lat: number, lon: number) =>
  `earth_${lat >= 0 ? "+" : ""}${lat.toFixed(2)}_${lon >= 0 ? "+" : ""}${lon.toFixed(2)}`;

export function mockSearch(req: SearchRequest): SearchResponse {
  const k = req.k ?? 12;
  const lunar = req.body !== "earth";
  return {
    results: Array.from({ length: k }, (_, i) => {
      // polar hits must stay inside 75-90°S or they fall outside the pane
      const lat =
        req.body === "moon_polar" ? -89.5 + i * 1.1
        : req.body === "moon" ? -12.3 + i * 2.8
        : req.body === "mars" ? -5.6 + i * 1.4
        : -24.1 + i * 0.77;
      const lon = 45 - i * 2.8;
      const tile_id =
        req.body === "moon_polar" ? `moonsp_${3 + (i % 5)}_${4 + Math.floor(i / 5)}`
        : req.body === "moon" ? `moon_6_${12 + i}_${34 + i}`
        : req.body === "mars" ? `mars_7_${60 + i}_${200 + i}`
        : earthTile(lat, lon);
      return {
        tile_id,
        lat: Number(lat.toFixed(2)),
        lon: Number(lon.toFixed(2)),
        score: Number((0.82 - i * 0.015).toFixed(3)),
        known_analog: !lunar && i === 2 ? "Atacama Desert (Yungay), Chile" : null,
        tile_url: `/mock-tile.svg`,
      };
    }),
  };
}

/**
 * Candidate locations, each with the label the API would give it.
 *
 * A tile's `known_analog` depends on *where it is* - `analog.known_analog_name`
 * tags anything within 150 km of a well-studied site. The mock used to assign
 * the label by list position, which put "new" on the tile at 77.50°S 162.00°E:
 * McMurdo Dry Valleys, one of the most studied analog sites on Earth. Since
 * "new, unrecognized analog" is the claim this project is judged on, the mock
 * must not get that backwards. Coordinates here are real, and the known ones
 * carry the same names as KNOWN_EARTH_ANALOGS in analogatlas/sites.py.
 */
const MOCK_CANDIDATES: Array<[number, number, string | null]> = [
  [-77.50, 162.00, "McMurdo Dry Valleys, Antarctica"],
  [75.38, -89.68, "Haughton Crater, Devon Island, Canada"],
  [-24.08, -69.92, "Atacama Desert (Yungay), Chile"],
  // Unstudied terrain, spread over real land so the map does not render a
  // straight line of dots through the Southern Ocean.
  [21.00, 17.50, null],    // Tibesti, Chad
  [-21.20, 119.40, null],  // Pilbara, Australia
  [37.50, 94.00, null],    // Qaidam Basin, China
  [31.77, -113.50, null],  // Pinacate, Mexico
  [-24.70, 15.30, null],   // Namib, Namibia
  [14.24, 40.30, null],    // Danakil, Ethiopia
  [29.57, 35.42, null],    // Wadi Rum, Jordan
  [43.42, -113.52, null],  // Craters of the Moon, Idaho
  [-30.30, 139.30, null],  // Arkaroola, Australia
  [19.98, 76.51, null],    // Lonar, India
  [64.90, -16.80, null],   // Askja, Iceland
];

export function mockAnalogs(req: AnalogsRequest): AnalogsResponse {
  const k = req.k ?? 12;
  // From Earth the analogs are Moon tiles (or Mars tiles, with dst_body),
  // inside that index's 60°S-60°N.
  const toMoon = req.src_body === "earth";
  const toMars = toMoon && req.dst_body === "mars";
  const results = MOCK_CANDIDATES.map(([lat, lon, known], i) => ({
    tile_id: toMars ? `mars_7_${50 + i}_${100 + i}`
      : toMoon ? `moon_6_${20 + i}_${40 + i}` : earthTile(lat, lon),
    lat: toMoon ? Math.max(-58, Math.min(58, lat)) : lat,
    lon,
    score: Number((0.74 - i * 0.02).toFixed(3)),
    visual_cos_scaled: Number(Math.max(0.05, 0.97 - i * 0.04).toFixed(3)),
    physical: Number(Math.max(0.05, 0.81 - i * 0.05).toFixed(3)),
    known_analog: toMoon ? null : known,
    model_score: toMoon ? null : Number(Math.max(0.1, 0.99 - i * 0.03).toFixed(3)),
    tile_url: `/mock-tile.svg`,
  }));
  return {
    src_tile: {
      tile_id: req.src_body === "moon_polar" ? "moonsp_5_5"
        : req.src_body === "mars" ? "mars_7_51_183"
        : toMoon ? earthTile(req.lat, req.lon) : "moon_6_0_90",
      lat: req.lat,
      lon: req.lon,
    },
    results: (req.new_only ? results.filter((r) => r.known_analog === null) : results).slice(0, k),
  };
}

/** The rows only the polar index can fill (#26), for the mocked report card. */
const POLAR_ROWS: TwinsResponse["breakdown"] = [
  { dimension: "Sunlight availability", moon: "90% of the time", earth: "~50% of the year",
    match: 0.2, kind: "compare",
    note: "Moon: LOLA illumination model over 18.6 years, best-lit point in the tile. " +
          "Earth sits near 50% at every latitude because it rotates daily, so a " +
          "near-permanently-lit ridge is the one thing no Earth site reproduces" },
  { dimension: "Longest continuous darkness", moon: "permanent inside a PSR; ~14 Earth days elsewhere",
    earth: "123 days of polar night", match: 0.03, kind: "compare",
    note: "Earth figure is geometric polar night, ignoring refraction and terrain" },
  { dimension: "Permanent shadow", moon: "18.2% of the tile",
    earth: "no permanent shadow at this scale", match: null, kind: "no_equivalent",
    note: "LOLA-modelled permanently shadowed regions" },
  { dimension: "Direct-to-Earth comms", moon: "26% of the time", earth: "always available",
    match: null, kind: "no_equivalent",
    note: "A south polar base can lose line of sight to Earth entirely" },
];

/** A Mars report card with every kind of row `analog.mars_rows` can produce. */
function mockMarsTwins(src_tile_id: string, earth_tile_id: string): TwinsResponse {
  return {
    moon: { tile_id: src_tile_id, body: "mars", lat: 18.41, lon: 77.69, slope_med: 1.8,
            relief_km: 0.9, thermal_inertia: 310, albedo: 0.18, weh_pct: 4, t_min_k: 185 },
    earth: { tile_id: earth_tile_id, lat: -24.08, lon: -69.92, slope_med: 2.1, relief_km: 1.1,
             visual_cos_scaled: 0.93 },
    climate: { TS_MIN: -8.4, TS_MAX: 41.2, PRECTOTCORR: 0.01, ALLSKY_SFC_SW_DWN: 7.1 },
    model_score: 0.97,
    field_tests: {
      tests: [
        { title: "Life detection at low biomass",
          risk: "False positives from Earth contamination, false negatives from weak instruments",
          detail: "Hyper-arid soil holds very little life or organic matter, so life-detection instruments and clean sampling can be tested near Mars-like detection limits.",
          based_on: ["Dryness"], strength: 0.98 },
        { title: "Rover mobility and traverse planning", risk: "Getting stuck or tipping on slopes",
          detail: "Slopes and relief match, so drive tests, path planners and slope-stability limits carry over. Traction will read high: Earth gravity is 2.6x Mars's.",
          based_on: ["Median slope", "Local relief"], strength: 0.86 },
      ],
      avoid: [{ dimension: "Water-altered minerals",
                reason: "Orbiters see water-altered minerals at the Mars site. We have no global Earth mineral map, so check this site's geology before planning sample-science tests." }],
    },
    breakdown: [
      { dimension: "Terrain shape (ML)", moon: "-", earth: "-", match: 0.93, kind: "compare",
        basis: "measured", note: "CLIP similarity of hillshade tiles, sun-direction invariant" },
      { dimension: "Median slope", moon: "1.8°", earth: "2.1°", match: 0.9, kind: "compare",
        basis: "measured", note: "MOLA vs the Earth DEM, both measured at ~1.9 km/px" },
      { dimension: "Local relief", moon: "0.90 km", earth: "1.10 km", match: 0.9, kind: "compare",
        basis: "measured", note: "98th-2nd percentile elevation within ~85 km" },
      { dimension: "Surface brightness (albedo)", moon: "0.18", earth: "0.24", match: 0.55,
        kind: "compare", basis: "measured",
        note: "TES albedo vs MODIS albedo: how much sunlight the ground reflects" },
      { dimension: "Surface material", moon: "310 tiu (sand and crusted soil)",
        earth: "27 °C day-night swing", match: 0.65, kind: "compare", basis: "proxy",
        note: "Mars: TES thermal inertia (low = loose dust, high = rock). Earth: MODIS day-night surface swing as a stand-in; air and soil moisture damp it, so read it as a guide" },
      { dimension: "Surface temperature swing", moon: "95 K", earth: "50 K", match: 0.52,
        kind: "compare", basis: "modelled",
        note: "Mars: modelled from latitude, albedo and thermal inertia, not measured. Earth: NASA POWER skin temperature" },
      { dimension: "Dryness", moon: "no liquid water at the surface", earth: "0.01 mm/day",
        match: 0.98, kind: "compare", basis: "measured",
        note: "NASA POWER precipitation; hyper-arid < 0.1 mm/day" },
      { dimension: "Day length", moon: "24 h 37 min", earth: "24 h", match: 0.97, kind: "compare",
        basis: "measured",
        note: "Nearly the same: crew routines, daily thermal cycles and solar-power days carry over" },
      { dimension: "Near-surface water", moon: "4% water-equivalent hydrogen",
        earth: "no comparable global measurement", match: null, kind: "no_equivalent",
        basis: "measured",
        note: "GRS hydrogen in the top metre, averaged over ~300 km: bound in minerals here rather than ice. Regional context only" },
      { dimension: "Water-altered minerals", moon: "12 CRISM detections in the tile",
        earth: "no global Earth mineral layer", match: null, kind: "no_equivalent", basis: "measured",
        note: "CRISM hydrated-mineral detections (clays, sulfates): a sign of past water. Check the Earth site's geology by hand" },
      { dimension: "Atmosphere", moon: "~0.6 kPa, 95% CO₂", earth: "101 kPa, nitrogen and oxygen",
        match: 0, kind: "earth_limit", basis: "measured",
        note: "Under 1% of Earth's pressure: parachutes, rotors, cooling and wind loads on dust all behave differently" },
      { dimension: "Gravity", moon: "3.71 m/s² (38% of Earth's)", earth: "9.81 m/s²", match: 0,
        kind: "earth_limit", basis: "measured",
        note: "Mobility and construction tests overestimate traction and load" },
      { dimension: "Radiation", moon: "~0.67 mSv/day at the surface (Curiosity RAD)",
        earth: "~0.007 mSv/day natural background", match: 0, kind: "earth_limit", basis: "measured",
        note: "A thin atmosphere and no global magnetic field: cosmic rays and solar particle events reach the ground" },
      { dimension: "Sunlight", moon: "~590 W/m² above the atmosphere (43% of Earth's)",
        earth: "~1,361 W/m² above the atmosphere", match: 0, kind: "earth_limit", basis: "measured",
        note: "Mars is 1.52 times farther from the Sun, so solar-power tests on Earth read high" },
      { dimension: "Soil chemistry", moon: "0.5-1% perchlorate salts in the soil (Phoenix)",
        earth: "trace amounts, in the driest deserts only", match: 0, kind: "earth_limit",
        basis: "measured",
        note: "Perchlorates are toxic and change how soil, water and organics react; Earth soils need them added for ISRU and life-detection tests" },
      { dimension: "Global dust storms", moon: "planet-encircling storms every few Mars years",
        earth: "regional storms only", match: 0, kind: "earth_limit", basis: "measured",
        note: "Weeks of dimmed sunlight across the whole planet have no Earth counterpart" },
    ],
  };
}

export function mockTwins(src_tile_id: string, earth_tile_id: string): TwinsResponse {
  if (src_tile_id.startsWith("mars_")) return mockMarsTwins(src_tile_id, earth_tile_id);
  const polar = src_tile_id.startsWith("moonsp_");
  return {
    moon: { tile_id: src_tile_id, lat: -89.5, lon: 0, slope_med: 4.7, relief_km: 1.2, t_min_k: 50 },
    earth: { tile_id: earth_tile_id, lat: -77.5, lon: 162, slope_med: 5.1, relief_km: 1.0,
             visual_cos_scaled: 0.91 },
    climate: { TS_MIN: -55.2, TS_MAX: 8.1, PRECTOTCORR: 0.02, ALLSKY_SFC_SW_DWN: 3.1 },
    model_score: 0.94,
    field_tests: {
      tests: [
        { title: "Rover mobility and traverse planning", risk: "Getting stuck or tipping on slopes",
          detail: "Slopes and relief match, so drive tests, path planners and slope-stability limits carry over.",
          based_on: ["Median slope", "Local relief"], strength: 0.83 },
        { title: "Dust handling and dry excavation", risk: "Seals, joints and diggers failing in dry fine material",
          detail: "Hyper-arid, so dry-regolith excavation and ISRU trials run without water changing the soil.",
          based_on: ["Dryness"], strength: 0.96 },
      ],
      avoid: [{ dimension: "Surface temperature swing",
                reason: "Surface temperature swing breaks down here (Moon 280 K, Earth 63 K)" }],
    },
    breakdown: [
      { dimension: "Terrain shape (ML)", moon: "-", earth: "-", match: 0.91, kind: "compare",
        note: "CLIP similarity of hillshade tiles, sun-direction invariant" },
      { dimension: "Median slope", moon: "4.7°", earth: "5.1°", match: 0.91, kind: "compare",
        note: "LOLA vs ETOPO, both ~1.9 km/px" },
      { dimension: "Local relief", moon: "1.20 km", earth: "1.00 km", match: 0.83, kind: "compare",
        note: "98th-2nd percentile elevation within ~85 km" },
      { dimension: "Surface temperature swing", moon: "280 K", earth: "63 K", match: 0.23,
        kind: "compare",
        note: "Moon: modelled from latitude, not measured. Earth: NASA POWER skin temperature" },
      { dimension: "Dryness", moon: "no liquid water", earth: "0.02 mm/day", match: 0.96,
        kind: "compare", note: "NASA POWER precipitation; hyper-arid < 0.1 mm/day" },
      // Diviner's cylindrical products stop at ±60°, so the polar index has no
      // rock abundance -- the row is absent there rather than faked.
      ...(polar
        ? POLAR_ROWS
        : [{
            dimension: "Surface rock cover", moon: "0.8%",
            earth: "no global Earth equivalent", match: null,
            kind: "no_equivalent" as const,
            note: "Diviner rock abundance - landing-hazard proxy",
          }]),
      { dimension: "Atmosphere", moon: "vacuum (trace exosphere)", earth: "1 bar at sea level",
        match: 0, kind: "earth_limit",
        note: "No air: no convective cooling and no wind. Dust, thermal and EVA tests behave differently" },
      { dimension: "Gravity", moon: "1.62 m/s² (1/6 g)", earth: "9.81 m/s²", match: 0,
        kind: "earth_limit", note: "Mobility and construction tests overestimate traction and load" },
      { dimension: "Radiation", moon: "~1.4 mSv/day at the surface (Chang'e-4)",
        earth: "~0.007 mSv/day natural background", match: 0, kind: "earth_limit",
        note: "No atmosphere or global magnetic field to shield cosmic rays and solar particle events" },
      { dimension: "Magnetic field", moon: "no global field (local crustal anomalies)",
        earth: "global magnetosphere", match: 0, kind: "earth_limit",
        note: "Earth's field deflects the solar wind; on the Moon it reaches the surface" },
      { dimension: "Day/night cycle", moon: "~29.5 Earth days (~2 weeks light, ~2 weeks dark)",
        earth: "24 hours", match: 0, kind: "earth_limit",
        note: "Long nights drive power and thermal design; some polar peaks are lit almost continuously" },
      { dimension: "Regolith dust", moon: "sharp, unweathered, electrostatically charged",
        earth: "rounded by wind and water", match: 0, kind: "earth_limit",
        note: "Earth dust is a poor stand-in for lunar abrasion, adhesion and seal wear" },
    ],
  };
}
