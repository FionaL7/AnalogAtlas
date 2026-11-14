/** How the search works, and what it does not claim. Numbers here are
 * placeholders until validation.json lands (#16). */
export function Methodology() {
  return (
    <article className="prose-invert mx-auto max-w-2xl text-sm leading-relaxed">
      <h1 className="text-xl font-semibold">How AnalogAtlas decides two places are alike</h1>

      <h2 className="mt-6 font-semibold">Two stages</h2>
      <p className="mt-2 text-muted">
        Global screening splits the Moon and Earth's land into tiles of about 85 × 85 km. Each tile
        gets CLIP embeddings and physical measurements, and search runs across both bodies. The
        strongest new candidates then get a close study with radar surface roughness.
      </p>

      <h2 className="mt-6 font-semibold">Why the comparison is fair</h2>
      <p className="mt-2 text-muted">
        LOLA LDEM_16 is 1.9 km/px and ETOPO 60s is 1.85 km/px, so slope and relief are measured at
        the same baseline on both bodies by construction — not rescaled after the fact.
      </p>

      <h2 className="mt-6 font-semibold">What the numbers are not</h2>
      <ul className="mt-2 list-disc pl-5 text-muted">
        <li>The ranking score mixes a standardised visual score with physical closeness. It is not a 0–1 similarity, so it is never shown.</li>
        <li>Lunar surface temperature extremes are modelled from latitude, not measured.</li>
        <li>Atmosphere and gravity cannot be reproduced on Earth at all. They are listed as limits, not as low scores.</li>
      </ul>

      <h2 className="mt-6 font-semibold">Checked against independent data</h2>
      <p className="mt-2 text-muted">
        Text queries for craters, mare and highlands return terrain whose slopes, measured
        independently from LOLA elevation, match what the query asked for — 0.4° median for "smooth
        flat dark lava plains" against 5.7° for "rugged mountainous highlands", on a 3.9° global
        median.
      </p>
    </article>
  );
}
