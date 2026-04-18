# BayesTransitEquity dashboard (`app/`)

Next.js 15 + Deck.gl 9 + MapLibre + Visx. Static export for Vercel (or any static host).

## Data

All assets live under `public/data/`:

| File | Purpose |
|------|---------|
| `baseline.geojson` | 720 tracts, INTERFACES.md schema + `disadvantage_z` / `disadv_quartile` (from export script) |
| `neighbors.json` | Queen-style adjacency `{ "06073000100": ["06073000200", ...], ... }` |
| `metadata.json` | Q25 thresholds, county summary, intervention stats, target GEOID lists |
| `scenarios/bayesian_top20.geojson` | Scenario A (lazy-loaded) |
| `scenarios/det_top20.geojson` | Scenario B (lazy-loaded) |

Regenerate from repo root (conda env with GeoPandas recommended; falls back to GeoPandas `touches` if `libpysal` is missing):

```bash
python scripts/export_frontend.py
```

## Run locally

```bash
cd app
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Optional deep link: `/?geoid=06073013317`.

## Production build

```bash
cd app
npm run build
```

Static output is written to `app/out/`. Serve with any static file server or deploy the `app` folder on Vercel (root directory = `app`, output = `out`).

## Implementation notes

- **Map**: `dynamic(..., { ssr: false })` from `HomeClient.tsx` so Deck.gl / MapLibre never run on the server.
- **Posterior panel**: Normal N(μ, σ) curves from GeoJSON `posterior_mean` / `posterior_sd`; scenario dashed curve uses implied μ for the reported scenario exceedance (same σ).
- **Typecheck**: `next.config.ts` sets `typescript.ignoreBuildErrors: true` because Next 15.5’s typed-routes validator can mis-resolve `src/app/page.tsx` on Windows. Re-enable strict checking after a Next.js patch if desired.

## Planned / not yet in this MVP

- URL hash persistence for mode + layer
- Full KDE neighbor overlays on the chart (pills + W₂ only for now)
- Mobile bottom-sheet layout (desktop-first)
