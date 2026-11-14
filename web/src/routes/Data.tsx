/** Data sources, credits and the AI-use declaration (Space Apps R8, R9).
 * Keep in step with README.md "Data sources and credits" and docs/RESOURCES.md. */

interface Source {
  name: string;
  from: string;
  use: string;
  href?: string;
}

const NASA: Source[] = [
  { name: "LROC WAC global mosaic", from: "NASA/GSFC/ASU, via NASA Moon Trek", use: "Moon imagery: embeddings and display", href: "https://trek.nasa.gov/moon/" },
  { name: "LOLA hillshade and LDEM_16", from: "LRO LOLA, NASA/GSFC/MIT (PDS, Moon Trek)", use: "Moon terrain shape, slope, relief" },
  { name: "LOLA south polar products", from: "LRO LOLA / PGDA", use: "Illumination, permanent shadow, Earth visibility at the pole" },
  { name: "Diviner GDR L3", from: "LRO Diviner, PDS Geosciences", use: "Rock abundance, regolith temperature" },
  { name: "Mini-RF global CPR mosaic", from: "LRO Mini-RF, PDS Geosciences", use: "Radar roughness at each lunar site", href: "https://pds-geosciences.wustl.edu/lro/lro-l-mrflro-5-global-mosaic-v1/" },
  { name: "Blue Marble Next Generation", from: "NASA Earth Observatory, via GIBS", use: "Earth imagery: embeddings and display" },
  { name: "ASTER GDEM shaded relief", from: "NASA/METI, via GIBS", use: "Earth terrain pictures" },
  { name: "NASA POWER climatology", from: "NASA LaRC", use: "Earth surface temperature, rain, sunlight on the report card", href: "https://power.larc.nasa.gov/" },
  { name: "MODIS land surface temperature, NDVI, land cover", from: "NASA LP DAAC (MOD11A2, MOD13A2, MCD12Q1), via Google Earth Engine", use: "Environment features for the analog model" },
];

const PARTNERS: Source[] = [
  { name: "RADARSAT Constellation Mission (RCM) ARD", from: "Canadian Space Agency, AWS open data", use: "Earth radar roughness for the close study", href: "https://registry.opendata.aws/rcm-ceos-ard/" },
  { name: "CSA SAR tutorial", from: "Canadian Space Agency", use: "Method for computing CPR from compact polarimetry" },
  { name: "Copernicus DEM GLO-30", from: "ESA / Copernicus, via Google Earth Engine", use: "Earth slope, relief and hillshade" },
  { name: "Sentinel-1", from: "ESA / Copernicus, via Microsoft Planetary Computer", use: "Radar fallback outside Canada" },
];

const OTHER: Source[] = [
  { name: "ETOPO 2022", from: "NOAA NCEI", use: "Earth slope and relief, same scale as LOLA" },
  { name: "TerraClimate", from: "University of Idaho, via Google Earth Engine", use: "Rainfall and aridity for the analog model" },
  { name: "Accessibility to cities 2015", from: "Malaria Atlas Project / Oxford, via Google Earth Engine", use: "Travel time to the nearest city" },
  { name: "CLIP ViT-B-32 (laion2b_s34b_b79k)", from: "LAION, via open_clip", use: "Image and text embeddings", href: "https://github.com/mlfoundations/open_clip" },
  { name: "Software", from: "PyTorch, open_clip, FAISS, scikit-learn, rasterio, FastAPI, React, Vite, Tailwind CSS, Leaflet", use: "Pipeline, API and app" },
];

function Table({ title, rows }: { title: string; rows: Source[] }) {
  return (
    <section className="mt-6">
      <h2 className="font-semibold">{title}</h2>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="pb-1 pr-3">Dataset</th>
              <th scope="col" className="pb-1 pr-3">From</th>
              <th scope="col" className="pb-1">Used for</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-t border-edge align-top">
                <th scope="row" className="py-1.5 pr-3 text-left font-medium">
                  {r.href ? <a href={r.href} target="_blank" rel="noreferrer" className="underline">{r.name}</a> : r.name}
                </th>
                <td className="py-1.5 pr-3 text-muted">{r.from}</td>
                <td className="py-1.5 text-muted">{r.use}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function Data() {
  return (
    <article className="mx-auto max-w-3xl text-sm leading-relaxed">
      <h1 className="text-xl font-semibold">Data and credits</h1>
      <p className="mt-2 text-muted">
        Every analog in AnalogAtlas is backed by open data. Pictures in the app are loaded live from NASA
        Moon Trek and NASA GIBS. Use of these datasets does not imply endorsement by NASA or any other
        agency.
      </p>
      <Table title="NASA data" rows={NASA} />
      <Table title="Space agency partner data" rows={PARTNERS} />
      <Table title="Other data, models and software" rows={OTHER} />

      <section className="mt-8 rounded-lg border border-edge bg-panel p-4">
        <h2 className="font-semibold">Use of AI tools</h2>
        <ul className="mt-2 list-disc pl-5 text-muted">
          <li>
            <strong className="text-ink">Claude Code</strong> (Anthropic) was used to write and review code and
            documentation. Commits it co-authored carry a <code>Co-Authored-By: Claude</code> trailer, so the
            AI-assisted history is auditable.
          </li>
          <li>The solution idea, the challenge approach and the scientific interpretation are the team's own.</li>
          <li>No AI-generated imagery, video or audio is used in the project or its submission materials.</li>
          <li>
            CLIP, an AI model, is part of the method itself: it turns tile pictures and text into vectors for
            search. Its results are always checked against physical measurements.
          </li>
        </ul>
      </section>

      <p className="mt-6 text-xs text-muted">
        Source code: <a href="https://github.com/FionaL7/AnalogAtlas" className="underline">github.com/FionaL7/AnalogAtlas</a>.
        Built for the NASA Space Apps Challenge 2026.
      </p>
    </article>
  );
}
