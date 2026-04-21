"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { FeatureCollection } from "geojson";
import type { GeoMode, LayerMetric, TractProperties } from "@/types";
import { useGeoData, buildLookup } from "@/hooks/useGeoData";
import { useCountyStats } from "@/hooks/useCountyStats";
import TransitMap from "@/components/Map/TransitMap";
import { MapLegend } from "@/components/Map/MapLegend";
import { MapAttribution } from "@/components/Map/MapAttribution";
import { ControlSidebar } from "@/components/Sidebar/ControlSidebar";
import { TractPanel } from "@/components/TractPanel/TractPanel";
import { InfoModal } from "@/components/shared/InfoModal";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { DensityConfoundScatter } from "@/components/Charts/DensityConfoundScatter";
import { Bus } from "lucide-react";

function zfill11(s: string): string {
  const t = s.trim();
  return t.length === 11 ? t : t.padStart(11, "0");
}

export default function Dashboard() {
  const router = useRouter();
  const [mode, setMode] = useState<GeoMode>("baseline");
  const [layerMetric, setLayerMetric] = useState<LayerMetric>("exceedance_prob");
  const [selectedGeoid, setSelectedGeoid] = useState<string | null>(null);
  const [showDesertOnly, setShowDesertOnly] = useState(false);
  const [showTargets, setShowTargets] = useState(false);
  const [showHook, setShowHook] = useState(false);
  const [disadvantageFilter, setDisadvantageFilter] = useState(0);
  const [infoOpen, setInfoOpen] = useState(false);
  const [showScatter, setShowScatter] = useState(false);
  const [urlReady, setUrlReady] = useState(false);

  const loadA = mode === "A";
  const loadB = mode === "B";
  const geo = useGeoData(loadA, loadB);

  const countyStats = useCountyStats(geo.baseline);

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

  /** Read deep-link query on client only — avoids useSearchParams + dynamic(ssr:false) runtime issues. */
  useEffect(() => {
    const applySearch = () => {
      const sp = new URLSearchParams(window.location.search);
      const g = sp.get("geoid");
      if (g) setSelectedGeoid(zfill11(g));
      const m = sp.get("mode");
      if (m === "A" || m === "B") setMode(m);
      setUrlReady(true);
    };
    applySearch();
    window.addEventListener("popstate", applySearch);
    return () => window.removeEventListener("popstate", applySearch);
  }, []);

  useEffect(() => {
    if (!urlReady) return;
    const params = new URLSearchParams();
    if (selectedGeoid) params.set("geoid", selectedGeoid);
    if (mode !== "baseline") params.set("mode", mode);
    const qs = params.toString();
    router.replace(qs ? `/?${qs}` : "/", { scroll: false });
  }, [selectedGeoid, mode, router, urlReady]);

  useEffect(() => {
    if (mode === "baseline" && layerMetric === "delta") {
      setLayerMetric("exceedance_prob");
    }
  }, [mode, layerMetric]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (e.key === "Escape") {
        if (showScatter) setShowScatter(false);
        else setSelectedGeoid(null);
      }
      if (e.key === "i" || e.key === "I") {
        if (!e.ctrlKey && !e.metaKey && !e.altKey) setInfoOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showScatter]);

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

  const onScatterPick = useCallback(
    (geoid: string) => {
      setSelectedGeoid(zfill11(geoid));
      setShowScatter(false);
    },
    [],
  );

  const selectedExceedance = selectedBaseline?.exceedance_prob ?? null;

  const intv = geo.metadata?.intervention;

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
      <header className="flex h-14 flex-shrink-0 items-center justify-between gap-2 border-b border-slate-800 bg-slate-800 px-4 text-slate-50">
        <div className="flex min-w-0 flex-shrink-0 items-center gap-2">
          <Bus className="h-6 w-6 shrink-0 text-sky-400" strokeWidth={1.75} aria-hidden />
          <div>
            <div className="text-sm font-semibold">BayesTransitEquity · San Diego</div>
            <div className="text-[10px] text-slate-400">Uncertainty-aware transit access</div>
          </div>
        </div>
        <div className="hidden min-w-0 flex-1 items-center justify-center gap-3 text-xs md:flex">
          {mode !== "baseline" && intv ? (
            <div className="flex items-center gap-3">
              <div className="flex flex-col items-center">
                <span className="text-base font-bold text-teal-300">{intv.scenario_a.n_crossings}</span>
                <span className="text-[10px] text-slate-400">Bayesian</span>
              </div>
              <span className="text-slate-500">vs</span>
              <div className="flex flex-col items-center">
                <span className="text-base font-bold text-amber-300">{intv.scenario_b.n_crossings}</span>
                <span className="text-[10px] text-slate-400">Deterministic</span>
              </div>
              <div className="ml-1 text-teal-300">
                <strong>{intv.efficiency_ratio}×</strong> efficiency
              </div>
            </div>
          ) : null}
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => setShowScatter(true)}
            className="rounded-lg border border-slate-600 px-2 py-1.5 text-[11px] font-medium hover:bg-slate-700"
          >
            Confound
          </button>
          <button
            type="button"
            onClick={() => setInfoOpen(true)}
            className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium hover:bg-slate-700"
          >
            Methodology
          </button>
        </div>
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
          countyStats={countyStats}
          selectedExceedance={selectedExceedance}
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
          countyStats={countyStats}
        />
      </div>

      <InfoModal open={infoOpen} onClose={() => setInfoOpen(false)} />

      {showScatter && countyStats ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowScatter(false)}
          role="presentation"
        >
          <div
            className="max-h-[90vh] max-w-2xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="scatter-title"
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 id="scatter-title" className="text-base font-bold text-slate-900">
                Income vs transit desert risk
              </h2>
              <button
                type="button"
                className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
                onClick={() => setShowScatter(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <DensityConfoundScatter
              data={countyStats.scatterData}
              selectedGeoid={selectedGeoid}
              onSelectTract={onScatterPick}
            />
            <p className="mt-3 text-[10px] text-slate-500">
              Click a bubble to select that tract on the map. Press Esc to close.
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
