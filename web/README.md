# web — AnalogAtlas frontend

React + Vite + Tailwind. Issue #15.

```bash
npm install
npm run dev     # http://localhost:5173, runs on mocked responses
npm test        # vitest
npm run build
```

- With no `VITE_API_BASE` set, every API call is served from `src/lib/mocks.ts`,
  so the app runs with no backend. Copy `.env.example` to `.env` and point
  `VITE_API_BASE` at the FastAPI service (`uvicorn api.main:app --reload`) to go live.
- `src/lib/types.ts` mirrors the contract in `docs/ARCHITECTURE.md` §4.2–4.3.
  If the API changes, change it there first.
- `public/data/` is where `scripts/03_export.py` writes the static demo path
  (sites, analogs, report cards, traps, candidates, radar, validation). Pages
  that need a file say so when it is missing; sites fall back to mocks.
- Maps are Leaflet (#24), lazy-loaded behind `src/components/map/MapPane.tsx`.
- Tile pictures are rebuilt in the browser from NASA Moon Trek and GIBS
  (`src/lib/chips.ts`); nothing image-sized is shipped.
- Pages: `/` Atlas, `/sites` and `/sites/:id` field guides, `/discoveries`,
  `/traps`, `/methodology`, `/data`. All but text/picture search work from the
  static export alone.
- **This is never published to npm.** It's an app, not a library: deploy it, don't
  publish it. `"private": true` in `package.json` enforces that — leave it there.
