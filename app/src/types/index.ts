// ── GeoJSON property schemas ────────────────────────────────────────────────

export interface TractProperties {
  geoid: string;
  tract_name: string;

  // Posterior distribution (log1p jobs scale)
  posterior_mean: number;
  posterior_sd: number;
  ci_lower_95: number;
  ci_upper_95: number;

  // Back-transformed to job scale
  posterior_mean_jobs: number;

  // Derived equity metrics
  exceedance_prob: number;   // P(jobs < Q25 @ 45 min)
  p_transit_desert: number;  // same as exceedance_prob
  wasserstein_dist: number;  // W₂ distance from well-served reference

  // Entropy (may be null)
  entropy: number | null;

  // Demographics
  pop_total: number;
  pct_no_vehicle: number;
  median_income: number;
  pct_poverty: number;

  /** Enriched by scripts/export_frontend.py from ACS (optional on stale exports) */
  disadvantage_z?: number | null;
  disadv_quartile?: number | null;
}

export interface ScenarioProperties extends TractProperties {
  exceedance_prob_scenario: number;
  exceedance_prob_delta: number;
  p_transit_desert_scenario: number;
  crossed_threshold: boolean;
  exceedance_delta_ci_lower: number;
  exceedance_delta_ci_upper: number;
}

export interface TractFeature {
  type: "Feature";
  geometry: GeoJSON.Geometry;
  properties: TractProperties;
}

export interface ScenarioFeature {
  type: "Feature";
  geometry: GeoJSON.Geometry;
  properties: ScenarioProperties;
}

export type GeoMode = "baseline" | "A" | "B";

export type LayerMetric =
  | "exceedance_prob"
  | "posterior_mean"
  | "wasserstein_dist"
  | "ci_width"
  | "delta";

// ── App state ────────────────────────────────────────────────────────────────

export interface AppState {
  selectedGeoid: string | null;
  mode: GeoMode;
  layerMetric: LayerMetric;
  disadvantageFilter: number; // 0 = all tracts, 4 = Q4 only
  showDesertOnly: boolean;
  showTargets: boolean;
}

// ── Metadata schema ──────────────────────────────────────────────────────────

export interface CountySummary {
  spearman_equity: number;
  n_probable_deserts: number;
  n_ambiguous: number;
  hook_geoid: string;
  composite_deficit_n: number;
  wasserstein_q1_mean: number;
  wasserstein_q4_mean: number;
  wasserstein_county_mean: number;
}

export interface ScenarioMeta {
  id: string;
  label: string;
  description: string;
  n_targets: number;
  n_crossings: number;
  pct_pop_served: number;
}

export interface Metadata {
  run_id: string;
  generated: string;
  county: string;
  n_tracts: number;
  q25_threshold_jobs: number;
  q25_threshold_log1p: number;
  /** Optional y standardisation from model (not required for map if q25_threshold_log1p set) */
  y_mean?: number;
  y_sd?: number;
  color_scale?: Record<string, unknown>;
  county_summary: CountySummary;
  intervention: {
    scenario_a: ScenarioMeta;
    scenario_b: ScenarioMeta;
    efficiency_ratio: number;
    bayesian_target_geoids: string[];
    det_target_geoids: string[];
  };
}

// ── KDE data ─────────────────────────────────────────────────────────────────

export interface KDEPoint {
  x: number; // log1p(jobs) scale
  y: number; // density
}

export interface NeighborCurve {
  geoid: string;
  tractName: string;
  mu: number;
  sigma: number;
  exceedance: number;
  w2: number;         // Wasserstein W₂ distance from selected tract
  color: string;
}
