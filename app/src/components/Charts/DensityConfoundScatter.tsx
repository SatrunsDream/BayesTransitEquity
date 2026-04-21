"use client";

import { useMemo, useState } from "react";
import { scaleLinear } from "@visx/scale";
import { AxisBottom, AxisLeft } from "@visx/axis";
import type { CountyStats } from "@/hooks/useCountyStats";
import { fmtIncome, fmtPct2, shortTractName } from "@/lib/formatters";

const Q_COLORS = ["#3B82F6", "#8B5CF6", "#F59E0B", "#EF4444"];

type Props = {
  data: CountyStats["scatterData"];
  selectedGeoid?: string | null;
  onSelectTract?: (geoid: string) => void;
  width?: number;
  height?: number;
};

const M = { top: 12, right: 12, bottom: 40, left: 44 };

export function DensityConfoundScatter({
  data,
  selectedGeoid,
  onSelectTract,
  width = 480,
  height = 320,
}: Props) {
  const [hover, setHover] = useState<CountyStats["scatterData"][0] | null>(null);

  const innerW = width - M.left - M.right;
  const innerH = height - M.top - M.bottom;

  const xScale = useMemo(
    () =>
      scaleLinear<number>({
        range: [0, innerW],
        domain: [20_000, 200_000],
        nice: true,
      }),
    [innerW],
  );
  const yScale = useMemo(
    () =>
      scaleLinear<number>({
        range: [innerH, 0],
        domain: [0, 1],
        nice: true,
      }),
    [innerH],
  );

  const rFn = (pop: number) => {
    const r = Math.sqrt(pop) / 50;
    return Math.min(12, Math.max(3, r));
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-900">The density confound</h3>
      <p className="mt-1 text-xs leading-relaxed text-slate-600">
        Median income vs P(transit desert) for all tracts. Bubble size scales with population. Higher-income
        suburban tracts can still show high desert probability — the empirical pattern motivating partial pooling.
      </p>
      <svg width={width} height={height} className="mt-3">
        <g transform={`translate(${M.left},${M.top})`}>
          {data.map((d) => {
            const cx = xScale(d.income) ?? 0;
            const cy = yScale(d.exceedance) ?? 0;
            const r = rFn(d.pop);
            const q = Math.min(4, Math.max(1, d.quartile)) - 1;
            const fill = Q_COLORS[q] ?? "#64748b";
            const sel = selectedGeoid && d.geoid === selectedGeoid;
            return (
              <circle
                key={d.geoid}
                cx={cx}
                cy={cy}
                r={r}
                fill={fill}
                fillOpacity={0.55}
                stroke={sel ? "#0f172a" : "none"}
                strokeWidth={sel ? 2 : 0}
                className="cursor-pointer"
                onMouseEnter={() => setHover(d)}
                onMouseLeave={() => setHover(null)}
                onClick={() => onSelectTract?.(d.geoid)}
              />
            );
          })}
          <AxisBottom
            top={innerH}
            scale={xScale}
            tickFormat={(v) => `${Math.round(Number(v) / 1000)}k`}
            stroke="#94a3b8"
            tickStroke="#94a3b8"
            tickLabelProps={() => ({ fill: "#64748b", fontSize: 9, textAnchor: "middle" })}
          />
          <AxisLeft
            scale={yScale}
            tickFormat={(v) => `${Math.round(Number(v) * 100)}%`}
            stroke="#94a3b8"
            tickStroke="#94a3b8"
            tickLabelProps={() => ({ fill: "#64748b", fontSize: 9, textAnchor: "end" })}
          />
        </g>
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-600">
        {["Q1", "Q2", "Q3", "Q4"].map((lab, i) => (
          <span key={lab} className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: Q_COLORS[i] }} />
            {lab}
          </span>
        ))}
      </div>
      {hover ? (
        <div className="mt-2 rounded border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-700 shadow-sm">
          <div className="font-medium">{shortTractName(hover.name)}</div>
          <div>Income {fmtIncome(hover.income)} · P(desert) {fmtPct2(hover.exceedance)} · Q{hover.quartile}</div>
        </div>
      ) : null}
    </div>
  );
}
