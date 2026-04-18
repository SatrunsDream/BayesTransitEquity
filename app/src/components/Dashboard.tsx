"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { FeatureCollection } from "geojson";
import type { GeoMode, LayerMetric, TractProperties } from "@/types";
import { useGeoData, buildLookup } from "@/hooks/useGeoData";
import TransitMap from "@/components/Map/TransitMap";
import { MapLegend } from "@/components/Map/MapLegend";
import { MapAttribution } from "@/components/Map/MapAttribution";
import { ControlSidebar } from "@/components/Sidebar/ControlSidebar";
import { TractPanel } from "@/components/TractPanel/TractPanel";
import { InfoModal } from "@/components/shared/InfoModal";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

function zfill11(s: string): string {
  const t = s.trim();
  return t.length === 11 ? t : t.padStart(11, "0");
}

export default function Dashboard() {
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<GeoMode>("baseline");
  const [layerMetric, setLayerMetric] = useState<LayerMetric>("exceedance_prob");
  const [selectedGeoid, setSelectedGeoid] = useState<string | null>(null);
  const [showDesertOnly, setShowDesertOnly] = useState(false);
  const [showTargets, setShowTargets] = useState(false);
  const [showHook, setShowHook] = useState(false);
  const [disadvantageFilter, setDisadvantageFilter] = useState(0);
  const [infoOpen, setInfoOpen] = useState(false);

  const loadA = mode === "A";
  const loadB = mode === "B";
  const geo = useGeoData(loadA, loadB);

  const baselineLookup = useMemo(() => buildLookup(geo.baseline), [geo.baseline]);
  const scenarioALookup = useMemo(() => buildLookup(geo.scenarioA), [geo.scenarioA]);
  const scenarioBLookup = useMemo(() => buildLookup(geo.scenarioB), [geo.scenarioB]);

  const activeScenarioLookup = mode === "A" ? scenarioALookup : mode === "B" ? scenarioBLookup : null;

  const mapData: FeatureCollection | null = useMemo(() => {
    if (mode === "A" && geo.scenarioA) return geo.scenarioA as unknown as FeatureCollection;
    if (mode === "B" && geo.scenarioB) return geo.scenarioB as unknown as FeatureCollection;
    return (geo.baseline as unknown as FeatureCollection) ?? null;
  }, [mode, geo.baseline, geo.scenarioA, geo.scenarioB]);

  const targetSet = useMemo(() => {
    const m = geo.metadata?.intervention;
    if (!m) return new Set<string>();
    if (mode === "A") return new Set(m.bayesian_target_geoids.map(zfill11));
    if (mode === "B") return new Set(m.det_target_geoids.map(zfill11));
    return new Set<string>();
  }, [geo.metadata, mode]);

  const hookGeoid = zfill11(geo.metadata?.county_summary?.hook_geoid ?? "06073013317");

  useEffect(() => {
    const g = searchParams.get("geoid");
    if (g) setSelectedGeoid(zfill11(g));
  }, [searchParams]);

  useEffect(() => {
    if (mode === "baseline" && layerMetric === "delta") {
      setLayerMetric("exceedance_prob");
    }
  }, [mode, layerMetric]);

  const nTotal = geo.baseline?.features.length ?? 720;
  const nVisible = useMemo(() => {
    if (!geo.baseline) return nTotal;
    if (disadvantageFilter === 0) return nTotal;
    return geo.baseline.features.filter(
      (f) => (f.properties.disadv_quartile ?? 0) === disadvantageFilter,
    ).length;
  }, [geo.baseline, disadvantageFilter, nTotal]);

  const selectedBaseline = selectedGeoid ? baselineLookup.get(selectedGeoid)?.properties ?? null : null;
  const selectedScenario =
    selectedGeoid && activeScenarioLookup
      ? activeScenarioLookup.get(selectedGeoid)?.properties ?? null
      : null;

  const neighborGeoids = selectedGeoid ? geo.neighbors[selectedGeoid] ?? [] : [];
  const neighborLookup = useMemo(() => {
    const m = new Map<string, TractProperties>();
    if (!geo.baseline) return m;
    for (const f of geo.baseline.features) {
      m.set(f.properties.geoid, f.properties);
    }
    return m;
  }, [geo.baseline]);

  const onSelectGeoid = useCallback((g: string | null) => {
    setSelectedGeoid(g ? zfill11(g) : null);
  }, []);

  if (geo.loading || !mapData) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-100">
        <LoadingSpinner />
        {geo.error ? <p className="mt-4 text-sm text-red-600">{geo.error}</p> : null}
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-100">
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-slate-800 bg-slate-800 px-4 text-slate-50">
        <div className="flex items-center gap-2">
          <span className="text-lg" aria-hidden>{String.fromCodePoint(0x1F68C)}</span>
          <div>
            <div className="text-sm font-semibold">BayesTransitEquity · San Diego</div>
            <div className="text-[10px] text-slate-400">Uncertainty-aware transit access</div>
          </div>
        </div>
        <div className="hidden items-center gap-4 text-xs md:flex">
          {mode !== "baseline" && geo.metadata?.intervention ? (
            <div className="rounded border border-slate-600 bg-slate-700/80 px-3 py-1 text-[11px]">
              A: <strong>{geo.metadata.intervention.scenario_a.n_crossings}</strong> crossings · B:{" "}
              <strong>{geo.metadata.intervention.scenario_b.n_crossings}</strong> ·{" "}
              <span className="text-teal-300">{geo.metadata.intervention.efficiency_ratio}×</span> efficiency
            </div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => setInfoOpen(true)}
          className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium hover:bg-slate-700"
        >
          Methodology
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        <ControlSidebar
          mode={mode}
          onMode={setMode}
          layerMetric={layerMetric}
          onLayer={setLayerMetric}
          showDesertOnly={showDesertOnly}
          onDesertOnly={setShowDesertOnly}
          showTargets={showTargets}
          onTargets={setShowTargets}
          showHook={showHook}
          onHook={setShowHook}
          disadvantageFilter={disadvantageFilter}
          onDisadvantage={setDisadvantageFilter}
          nVisible={nVisible}
          nTotal={nTotal}
          metadata={geo.metadata}
          loadingA={geo.loadingA}
          loadingB={geo.loadingB}
        />

        <main className="relative min-h-0 min-w-0 flex-1">
          {(mode === "A" && geo.loadingA) || (mode === "B" && geo.loadingB) ? (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/60">
              <LoadingSpinner label="Loading scenario GeoJSON…" />
            </div>
          ) : null}
          <TransitMap
            data={mapData}
            mode={mode}
            layerMetric={layerMetric}
            selectedGeoid={selectedGeoid}
            onSelectGeoid={onSelectGeoid}
            showDesertOnly={showDesertOnly}
            showTargets={showTargets}
            showHook={showHook}
            disadvantageFilter={disadvantageFilter}
            targetGeoids={targetSet}
            hookGeoid={hookGeoid}
          />
          <MapLegend metric={layerMetric} />
          <MapAttribution />
        </main>

        <TractPanel
          onClose={() => setSelectedGeoid(null)}
          props={selectedBaseline}
          scenarioProps={selectedScenario}
          mode={mode}
          metadata={geo.metadata}
          neighborGeoids={neighborGeoids}
          neighborLookup={neighborLookup}
        />
      </div>

      <InfoModal open={infoOpen} onClose={() => setInfoOpen(false)} />
    </div>
  );
}
