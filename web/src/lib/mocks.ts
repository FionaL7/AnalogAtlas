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
  { id: "shackleton-rim", body: "moon", name: "Shackleton rim", lat: -89.67, lon: 129.78,
    is_base_region: true, blurb: "Classic base concept: near-permanent sunlight on the rim, cold traps below." },
  { id: "mons-mouton", body: "moon", name: "Mons Mouton Plateau", lat: -84.6, lon: 31.0,
    is_base_region: true, blurb: "Artemis candidate region; a broad, comparatively flat plateau." },
  { id: "haworth", body: "moon", name: "Haworth", lat: -87.45, lon: -5.17, is_base_region: true },
  { id: "apollo-15", body: "moon", name: "Apollo 15 — Hadley Rille", lat: 26.13, lon: 3.63,
    blurb: "Mare surface cut by a sinuous rille, against the Apennine front." },
  { id: "tycho", body: "moon", name: "Tycho crater", lat: -43.31, lon: -11.36 },
  { id: "atacama", body: "earth", name: "Atacama Desert, Chile", lat: -24.1, lon: -69.9 },
];

const earthTile = (lat: number, lon: number) =>
  `earth_${lat >= 0 ? "+" : ""}${lat.toFixed(2)}_${lon >= 0 ? "+" : ""}${lon.toFixed(2)}`;

export function mockSearch(req: SearchRequest): SearchResponse {
  const k = req.k ?? 12;
  return {
    results: Array.from({ length: k }, (_, i) => {
      const lat = req.body === "moon" ? -12.3 + i * 2.8 : -24.1 + i * 0.77;
      const lon = 45 - i * 2.8;
      const tile_id = req.body === "moon" ? `moon_6_${12 + i}_${34 + i}` : earthTile(lat, lon);
      return {
        tile_id,
        lat: Number(lat.toFixed(2)),
        lon: Number(lon.toFixed(2)),
        score: Number((0.82 - i * 0.015).toFixed(3)),
        known_analog: req.body === "earth" && i === 2 ? "Atacama Desert (Yungay), Chile" : null,
        tile_url: `/mock-tile.svg`,
      };
    }),
  };
}

export function mockAnalogs(req: AnalogsRequest): AnalogsResponse {
  const k = req.k ?? 12;
  const known = [null, "McMurdo Dry Valleys, Antarctica", null, "Haughton Crater, Devon Island, Canada"];
  const results = Array.from({ length: k + 2 }, (_, i) => {
    const lat = -77.5 + i * 3.1;
    const lon = 162 - i * 4.3;
    return {
      tile_id: earthTile(lat, lon),
      lat: Number(lat.toFixed(2)),
      lon: Number(lon.toFixed(2)),
      score: Number((0.74 - i * 0.02).toFixed(3)),
      visual_cos_scaled: Number(Math.max(0.05, 0.97 - i * 0.04).toFixed(3)),
      physical: Number(Math.max(0.05, 0.81 - i * 0.05).toFixed(3)),
      known_analog: known[i % known.length],
      tile_url: `/mock-tile.svg`,
    };
  });
  return {
    src_tile: { tile_id: "moon_6_0_90", lat: req.lat, lon: req.lon },
    results: (req.new_only ? results.filter((r) => r.known_analog === null) : results).slice(0, k),
  };
}

export function mockTwins(src_tile_id: string, earth_tile_id: string): TwinsResponse {
  return {
    moon: { tile_id: src_tile_id, lat: -89.5, lon: 0, slope_med: 4.7, relief_km: 1.2, t_min_k: 50 },
    earth: { tile_id: earth_tile_id, lat: -77.5, lon: 162, slope_med: 5.1, relief_km: 1.0,
             visual_cos_scaled: 0.91 },
    climate: { TS_MIN: -55.2, TS_MAX: 8.1, PRECTOTCORR: 0.02, ALLSKY_SFC_SW_DWN: 3.1 },
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
      { dimension: "Surface rock cover", moon: "0.8%", earth: "no global Earth equivalent",
        match: null, kind: "no_equivalent", note: "Diviner rock abundance - landing-hazard proxy" },
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
