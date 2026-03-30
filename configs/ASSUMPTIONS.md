# ASSUMPTIONS.md
All modeling and data assumptions, why they are reasonable, how they could fail,
and how sensitivity will be tested.

---

## Modeling Assumptions

### A001 — Census tracts as the unit of analysis
**Assumption**: Census tracts are a meaningful spatial unit for transit equity analysis.
**Rationale**: Standard in the literature. ~4,000 people per tract balances granularity and sample size.
**How it could fail**: Tracts are administrative units that may not reflect meaningful neighborhoods.
**Sensitivity**: Cross-check key findings at block group level where data permits.

### A002 — Accessibility threshold (TBD min travel time)
**Assumption**: A neighborhood is "accessible" if X jobs/services are reachable within Y minutes.
**Rationale**: Threshold to be set based on literature review and SD-specific context.
**How it could fail**: Threshold is inherently normative. Different thresholds give different maps.
**Sensitivity**: Run full analysis at 30, 45, and 60 minute thresholds. Report all three.
**Status**: Threshold Y not yet decided. Document here when chosen.

### A003 — Schedule-based routing (no real-time data) for Phase 1
**Assumption**: GTFS schedule data is a reasonable proxy for actual service.
**Rationale**: Simplicity. GTFS-RT integration is Phase 2.
**How it could fail**: Schedule adherence varies significantly. Some routes are chronically late.
**Sensitivity**: Phase 2 will add GTFS-RT to produce reliability-adjusted accessibility.

### A004 — Departure window averaging
**Assumption**: Accessibility computed over a morning peak departure window (7-9am) is
representative of commute-time access.
**Rationale**: Standard in the literature for job accessibility studies.
**How it could fail**: Off-peak and evening accessibility may be more relevant for low-income
workers with non-standard schedules.
**Sensitivity**: Run analysis for evening window (5-7pm) and report gap.

### A005 — CAR/BYM spatial structure
**Assumption**: Tract-level accessibility exhibits spatial autocorrelation well-modeled by
queen contiguity (neighboring tracts share information).
**Rationale**: Standard assumption for areal Bayesian spatial models.
**How it could fail**: Transit accessibility may have non-local spatial structure
(e.g., corridor effects along rail lines).
**Sensitivity**: Compare model with and without spatial random effects via LOO-CV.

---

## Data Assumptions

### A006 — ACS 5-year estimates are current enough
**Assumption**: 2019-2023 ACS 5-year estimates adequately represent current demographics.
**Rationale**: Best available small-area demographic data.
**How it could fail**: Rapid gentrification in some SD neighborhoods may mean estimates are stale.
**Sensitivity**: Flag tracts with high population change between 2010 and 2020 decennial.

### A007 — OSM walk network is complete enough for walk-to-stop computation
**Assumption**: OpenStreetMap pedestrian network covers all relevant walkways in SD.
**Rationale**: OSM coverage is generally good in urban San Diego.
**How it could fail**: Missing sidewalks in suburban areas may understate walk times.
**Sensitivity**: Spot-check walk network completeness in low-coverage areas.

### A008 — NCTD GTFS feed is periodically stale and must be refreshed before analysis
**Assumption**: The downloaded NCTD feed accurately reflects current service.
**Rationale**: NCTD feed version "Version_20250205" expired 2025-05-17 (~10 months stale as of March 2026).
MTS feed is current (valid through 2026-06-06). NCTD must be refreshed via
`--force --refresh-mobility-catalog` before any headway, coverage, or service metrics
derived from NCTD data are trusted.
**How it could fail**: Stale feed understates service improvements or reflects discontinued routes.
Any headway or coverage numbers from EDA notebooks 01-02 using the old feed should be
treated as provisional until the feed is refreshed.
**Action required**: `python scripts/download_data.py --config configs/san_diego.yaml --sources gtfs --force --refresh-mobility-catalog`
**Status**: **PARTIALLY ADDRESSED (2026-03-29)** — command was run; Mobility `urls.latest` zip re-downloaded but **feed content is unchanged** (`feed_version` still `Version_20250205`; `calendar.txt` service windows still end **20250516**). Schedule is still **expired relative to analysis date** until NCTD / Mobility publishes a newer bundle. Treat NCTD schedule-based metrics as **provisional** until a newer feed appears.

### A009 — NCTD service is partially outside the study bbox; this is a known scope limitation
**Assumption**: The study bbox `[-117.28, 32.53, -116.93, 33.11]` captures enough NCTD service
to include it as a meaningful second agency in the analysis.
**Rationale**: Only 342 of 1,823 NCTD stops (18.76%) fall inside the bbox. The bbox was designed
around central/south San Diego where MTS operates; North County (NCTD's primary territory)
extends further north and east.
**How it could fail**: With <20% of NCTD stops in scope, NCTD coverage metrics will look
artificially poor. This could bias the equity analysis if North County tracts are included
in the model but NCTD routes are effectively invisible.
**Options**:
  1. Expand bbox northward to ~33.3 to capture more NCTD territory (changes study area definition)
  2. Keep bbox, document NCTD partial coverage as a study limitation, exclude NCTD-only tracts
  3. Run analysis MTS-only and treat NCTD as supplementary / future work
**Status**: OPEN DECISION — document choice in `context/DECISIONS.md` (**D009**) when resolved.
