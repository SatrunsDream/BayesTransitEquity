"use client";
import { useState, useEffect } from "react";
import type { TractFeature, ScenarioFeature, Metadata } from "@/types";

type GeoFC<F> = { type: "FeatureCollection"; features: F[] };

interface GeoDataState {
  baseline:   GeoFC<TractFeature> | null;
  scenarioA:  GeoFC<ScenarioFeature> | null;
  scenarioB:  GeoFC<ScenarioFeature> | null;
  neighbors:  Record<string, string[]>;
  metadata:   Metadata | null;
  loading:    boolean;
  loadingA:   boolean;
  loadingB:   boolean;
  error:      string | null;
}

// Build a lookup map geoid → feature for O(1) access
export function buildLookup<F extends { properties: { geoid: string } }>(
  fc: GeoFC<F> | null
): Map<string, F> {
  const m = new Map<string, F>();
  if (!fc) return m;
  for (const f of fc.features) m.set(f.properties.geoid, f);
  return m;
}

export function useGeoData(loadScenarioA: boolean, loadScenarioB: boolean) {
  const [state, setState] = useState<GeoDataState>({
    baseline: null, scenarioA: null, scenarioB: null,
    neighbors: {}, metadata: null,
    loading: true, loadingA: false, loadingB: false, error: null,
  });

  // Load baseline, neighbors, metadata at startup
  useEffect(() => {
    async function loadBase() {
      try {
        const [baselineRes, neighborsRes, metaRes] = await Promise.all([
          fetch("/data/baseline.geojson"),
          fetch("/data/neighbors.json"),
          fetch("/data/metadata.json"),
        ]);
        const [baseline, neighbors, metadata] = await Promise.all([
          baselineRes.json(),
          neighborsRes.json(),
          metaRes.json(),
        ]);
        setState(s => ({ ...s, baseline, neighbors, metadata, loading: false }));
      } catch (err) {
        setState(s => ({ ...s, error: String(err), loading: false }));
      }
    }
    loadBase();
  }, []);

  // Lazy-load Scenario A
  useEffect(() => {
    if (!loadScenarioA || state.scenarioA) return;
    setState(s => ({ ...s, loadingA: true }));
    fetch("/data/scenarios/bayesian_top20.geojson")
      .then(r => r.json())
      .then(scenarioA => setState(s => ({ ...s, scenarioA, loadingA: false })))
      .catch(err => setState(s => ({ ...s, loadingA: false, error: String(err) })));
  }, [loadScenarioA, state.scenarioA]);

  // Lazy-load Scenario B
  useEffect(() => {
    if (!loadScenarioB || state.scenarioB) return;
    setState(s => ({ ...s, loadingB: true }));
    fetch("/data/scenarios/det_top20.geojson")
      .then(r => r.json())
      .then(scenarioB => setState(s => ({ ...s, scenarioB, loadingB: false })))
      .catch(err => setState(s => ({ ...s, loadingB: false, error: String(err) })));
  }, [loadScenarioB, state.scenarioB]);

  return state;
}
