"use client";

import type { LayerMetric } from "@/types";

const LABELS: Record<LayerMetric, { title: string }> = {
  exceedance_prob: { title: "P(transit desert)" },
  posterior_mean: { title: "Posterior mean (log₁p jobs)" },
  wasserstein_dist: { title: "Wasserstein distance" },
  ci_width: { title: "95% CI width (log₁p)" },
  delta: { title: "Δ exceedance (scenario)" },
};

const GRADIENTS: Record<LayerMetric, string> = {
  exceedance_prob: "from-blue-500 via-amber-400 to-red-500",
  posterior_mean: "from-violet-700 via-violet-400 to-amber-400",
  wasserstein_dist: "from-indigo-100 to-indigo-700",
  ci_width: "from-indigo-100 to-indigo-700",
  delta: "from-teal-500 via-slate-200 to-rose-300",
};

const TICKS: Record<LayerMetric, string[]> = {
  exceedance_prob: ["0%", "25%", "50%", "75%", "100%"],
  posterior_mean: ["4", "6", "8", "10", "12"],
  wasserstein_dist: ["0", "30k", "60k", "90k", "120k+"],
  ci_width: ["Narrow", "—", "—", "—", "Wide"],
  delta: ["−1", "−0.5", "0", "+0.5", "+1"],
};

export function MapLegend({ metric }: { metric: LayerMetric }) {
  const L = LABELS[metric];
  const ticks = TICKS[metric];
  const grad = GRADIENTS[metric];
  return (
    <div className="pointer-events-none absolute bottom-8 left-3 z-10 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 shadow-md backdrop-blur-sm">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-600">
        {L.title}
      </div>
      <div className={`mt-1 h-2 w-40 rounded-full bg-gradient-to-r ${grad}`} />
      <div className="mt-1 grid w-40 grid-cols-5 gap-0 text-[8px] text-slate-500">
        {ticks.map((t, i) => (
          <span key={i} className="text-center leading-tight">
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}
