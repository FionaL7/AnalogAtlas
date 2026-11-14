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
        : -24.1 + i * 0.77;
      const lon = 45 - i * 2.8;
      const tile_id =
        req.body === "moon_polar" ? `moonsp_${3 + (i % 5)}_${4 + Math.floor(i / 5)}`
        : req.body === "moon" ? `moon_6_${12 + i}_${34 + i}`
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
  // From Earth the analogs are Moon tiles, inside the 60°S-60°N Moon index.
  const toMoon = req.src_body === "earth";
  const results = MOCK_CANDIDATES.map(([lat, lon, known], i) => ({
    tile_id: toMoon ? `moon_6_${20 + i}_${40 + i}` : earthTile(lat, lon),
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

export function mockTwins(src_tile_id: string, earth_tile_id: string): TwinsResponse {
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
