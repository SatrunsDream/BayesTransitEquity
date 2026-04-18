"use client";

import type { GeoMode, LayerMetric, Metadata } from "@/types";
import { StatCard } from "@/components/shared/StatCard";

type Props = {
  mode: GeoMode;
  onMode: (m: GeoMode) => void;
  layerMetric: LayerMetric;
  onLayer: (m: LayerMetric) => void;
  showDesertOnly: boolean;
  onDesertOnly: (v: boolean) => void;
  showTargets: boolean;
  onTargets: (v: boolean) => void;
  showHook: boolean;
  onHook: (v: boolean) => void;
  disadvantageFilter: number;
  onDisadvantage: (q: number) => void;
  nVisible: number;
  nTotal: number;
  metadata: Metadata | null;
  loadingA: boolean;
  loadingB: boolean;
};

const LAYERS: { id: LayerMetric; label: string }[] = [
  { id: "exceedance_prob", label: "P(transit desert)" },
  { id: "posterior_mean", label: "Posterior mean (log1p)" },
  { id: "ci_width", label: "Uncertainty (CI width)" },
  { id: "wasserstein_dist", label: "Wasserstein" },
];

export function ControlSidebar({
  mode,
  onMode,
  layerMetric,
  onLayer,
  showDesertOnly,
  onDesertOnly,
  showTargets,
  onTargets,
  showHook,
  onHook,
  disadvantageFilter,
  onDisadvantage,
  nVisible,
  nTotal,
  metadata,
  loadingA,
  loadingB,
}: Props) {
  const cs = metadata?.county_summary;
  const intv = metadata?.intervention;

  return (
    <aside className="flex w-60 flex-shrink-0 flex-col overflow-y-auto border-r border-slate-200 bg-white">
      <div className="border-b border-slate-100 p-3">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Mode</div>
        <div className="mt-2 flex flex-col gap-1">
          {(
            [
              ["baseline", "Baseline"],
              ["A", loadingA ? "Scenario A …" : "Scenario A (Bayesian)"],
              ["B", loadingB ? "Scenario B …" : "Scenario B (Deterministic)"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => onMode(k)}
              className={`rounded-lg border px-3 py-2 text-left text-xs font-medium transition ${
                mode === k
                  ? "border-blue-500 bg-blue-50 text-blue-900"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-b border-slate-100 p-3">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Layer</div>
        <div className="mt-2 space-y-1">
          {LAYERS.map((L) => (
            <label key={L.id} className="flex cursor-pointer items-center gap-2 text-xs text-slate-700">
              <input
                type="radio"
                name="layer"
                checked={layerMetric === L.id}
                onChange={() => onLayer(L.id)}
              />
              {L.label}
            </label>
          ))}
          {mode !== "baseline" ? (
            <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-700">
              <input
                type="radio"
                name="layer"
                checked={layerMetric === "delta"}
                onChange={() => onLayer("delta")}
              />
              Δ Exceedance
            </label>
          ) : null}
        </div>
      </div>

      <div className="border-b border-slate-100 p-3 space-y-2">
        <label className="flex items-center gap-2 text-xs text-slate-700">
          <input type="checkbox" checked={showDesertOnly} onChange={(e) => onDesertOnly(e.target.checked)} />
          Highlight P ≥ 50% (baseline)
        </label>
        {mode !== "baseline" ? (
          <label className="flex items-center gap-2 text-xs text-slate-700">
            <input type="checkbox" checked={showTargets} onChange={(e) => onTargets(e.target.checked)} />
            Show 20 targets (outline)
          </label>
        ) : null}
        <label className="flex items-center gap-2 text-xs text-slate-700">
          <input type="checkbox" checked={showHook} onChange={(e) => onHook(e.target.checked)} />
          Highlight hook tract
        </label>
      </div>

      <div className="border-b border-slate-100 p-3">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Disadvantage filter
        </div>
        <input
          type="range"
          min={0}
          max={4}
          step={1}
          value={disadvantageFilter}
          onChange={(e) => onDisadvantage(Number(e.target.value))}
          className="mt-2 w-full"
        />
        <div className="mt-1 flex justify-between text-[10px] text-slate-500">
          <span>All</span>
          <span>Q4 only</span>
        </div>
        <p className="mt-1 text-[10px] text-slate-500">
          Showing {nVisible} / {nTotal} tracts (opacity)
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2 p-3">
        <StatCard label="Probable deserts" value={cs?.n_probable_deserts ?? "—"} />
        <StatCard label="Spearman ρ" value={cs?.spearman_equity?.toFixed(4) ?? "—"} />
        <StatCard label="Ambiguous" value={cs?.n_ambiguous ?? "—"} />
        <StatCard label="Composite deficit" value={cs?.composite_deficit_n ?? "—"} />
      </div>

      {mode !== "baseline" && intv ? (
        <div className="border-t border-slate-100 p-3 text-[10px] text-slate-600">
          <div className="font-semibold text-slate-800">Intervention (nb07)</div>
          <div className="mt-1">
            A: <strong>{intv.scenario_a.n_crossings}</strong> crossings ·{" "}
            <strong>{intv.scenario_a.pct_pop_served}%</strong> pop.
          </div>
          <div>
            B: <strong>{intv.scenario_b.n_crossings}</strong> crossings ·{" "}
            <strong>{intv.scenario_b.pct_pop_served}%</strong> pop.
          </div>
          <div className="mt-1 text-teal-800">
            Efficiency A/B: <strong>{intv.efficiency_ratio}×</strong>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
