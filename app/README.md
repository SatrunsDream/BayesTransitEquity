# app/
Next.js + Deck.gl interactive frontend. Deployed on Vercel.

## What This Is
The user-facing map application. Reads precomputed GeoJSON from `public/data/`
and renders an interactive transit equity map for San Diego.

## Key Components
- `components/Map/` — Deck.gl map with heatmap + GeoJSON layers
- `components/PosteriorPanel/` — Distribution viewer for selected tract
- `components/DivergenceView/` — Wasserstein distance comparison between tracts
- `components/InterventionSlider/` — Scenario simulation UI

## Data Contract
This app reads GeoJSON from `public/data/`. Schema defined in `context/INTERFACES.md`.
Do not modify the GeoJSON schema without updating both `scripts/export_frontend.py` and this app.

## Setup
*(To be filled in when frontend development begins)*

## Deployment
Deployed via Vercel. Configuration in `vercel.json` (to be added).
