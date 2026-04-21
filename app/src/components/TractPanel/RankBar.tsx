"use client";

import { useMemo } from "react";

type Props = {
  value: number;
  sortedValues: number[];
};

/** Percentile rank [0,100]: higher = more exceedance than other tracts (desert risk). */
export function exceedancePercentile(sortedAsc: number[], value: number): number {
  const n = sortedAsc.length;
  if (n === 0) return 50;
  if (n === 1) return 50;
  let lo = 0;
  let hi = n;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sortedAsc[mid] < value) lo = mid + 1;
    else hi = mid;
  }
  const first = lo;
  let last = first;
  while (last < n && Math.abs(sortedAsc[last] - value) < 1e-9) last++;
  const midRank = (first + last - 1) / 2;
  return (midRank / (n - 1)) * 100;
}

export function RankBar({ value, sortedValues }: Props) {
  const pct = useMemo(() => exceedancePercentile(sortedValues, value), [sortedValues, value]);
  const fillPct = Math.min(100, Math.max(0, pct));
  const barColor =
    pct < 50 ? "bg-emerald-500/90" : pct < 80 ? "bg-amber-500/90" : "bg-rose-500/90";

  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Desert risk percentile
      </div>
      <p className="mt-1 text-[10px] text-slate-600">
        <strong>{Math.round(pct)}th</strong> percentile among {sortedValues.length} San Diego tracts
        (higher = more likely transit desert vs peers).
      </p>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${fillPct}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[9px] text-slate-500">
        <span>Lower risk</span>
        <span>Higher risk</span>
      </div>
    </div>
  );
}
