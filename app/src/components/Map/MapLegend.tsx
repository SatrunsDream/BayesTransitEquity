"use client";

import type { LayerMetric } from "@/types";

const LABELS: Record<LayerMetric, { title: string; low: string; mid: string; high: string }> = {
  exceedance_prob: {
    title: "P(transit desert)",
    low: "0%",
    mid: "50%",
    high: "100%",
  },
  posterior_mean: {
    title: "Posterior mean (log₁p jobs)",
    low: "Low",
    mid: "Mid",
    high: "High",
  },
  wasserstein_dist: {
    title: "Wasserstein distance",
    low: "0",
    mid: "Mid",
    high: "High",
  },
  ci_width: {
    title: "95% CI width (log₁p)",
    low: "Narrow",
    mid: "—",
    high: "Wide",
  },
  delta: {
    title: "Δ exceedance (scenario)",
    low: "Improved",
    mid: "0",
    high: "Worse",
  },
};

export function MapLegend({ metric }: { metric: LayerMetric }) {
  const L = LABELS[metric];
  return (
    <div className="pointer-events-none absolute bottom-8 left-3 z-10 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 shadow-md backdrop-blur-sm">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-600">
        {L.title}
      </div>
      <div className="mt-1 h-2 w-40 rounded-full bg-gradient-to-r from-blue-500 via-amber-400 to-red-500" />
      <div className="mt-1 flex w-40 justify-between text-[9px] text-slate-500">
        <span>{L.low}</span>
        <span>{L.mid}</span>
        <span>{L.high}</span>
      </div>
    </div>
  );
}
