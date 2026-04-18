"use client";

import { jsdLabel } from "@/lib/distances";

export type NeighborJsdRow = {
  geoid: string;
  label: string;
  jsd: number;
};

type Props = {
  rows: NeighborJsdRow[];
  /** Highlight rows that are currently on the overlay plot */
  activeGeoids: Set<string>;
  maxHeightPx?: number;
  onRowClick?: (geoid: string) => void;
};

export function NeighborJsdBars({
  rows,
  activeGeoids,
  maxHeightPx = 160,
  onRowClick,
}: Props) {
  if (rows.length === 0) return null;
  const maxJ = Math.max(...rows.map((r) => r.jsd), 1e-6);

  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Jensen–Shannon vs this tract (lower = more similar)
      </div>
      <p className="mt-0.5 text-[9px] text-slate-500">
        Bars use Normal(μ, σ) surrogates. Click a row to toggle it on the plot (up to 3).
      </p>
      <div
        className="mt-2 space-y-1.5 overflow-y-auto pr-1"
        style={{ maxHeight: maxHeightPx }}
      >
        {rows.map((r) => {
          const w = (r.jsd / maxJ) * 100;
          const tone = jsdLabel(r.jsd);
          const barBg =
            tone === "low"
              ? "bg-emerald-400/80"
              : tone === "moderate"
                ? "bg-amber-400/80"
                : "bg-rose-400/80";
          const active = activeGeoids.has(r.geoid);
          return (
            <button
              key={r.geoid}
              type="button"
              onClick={() => onRowClick?.(r.geoid)}
              className={`flex w-full flex-col rounded border px-2 py-1 text-left transition hover:bg-slate-50 ${
                active ? "border-blue-400 bg-blue-50/50" : "border-slate-100 bg-white"
              }`}
            >
              <div className="flex items-center justify-between gap-2 text-[10px]">
                <span className="truncate font-medium text-slate-800">{r.label}</span>
                <span className="shrink-0 font-mono text-slate-600">{r.jsd.toFixed(3)}</span>
              </div>
              <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                <div className={`h-full rounded-full ${barBg}`} style={{ width: `${w}%` }} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
