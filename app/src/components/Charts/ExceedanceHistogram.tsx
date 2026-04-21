"use client";

import { useMemo } from "react";

type Bin = { lo: number; hi: number; count: number };

type Props = {
  bins: Bin[];
  selectedExceedance?: number | null;
  height?: number;
};

function binColor(mid: number): string {
  if (mid < 0.3) return "#3B82F6";
  if (mid < 0.7) return "#F59E0B";
  return "#EF4444";
}

export function ExceedanceHistogram({ bins, selectedExceedance, height = 80 }: Props) {
  const maxC = useMemo(() => Math.max(...bins.map((b) => b.count), 1), [bins]);
  const w = 208;
  const pad = { t: 4, r: 4, b: 18, l: 4 };
  const innerW = w - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const bw = innerW / bins.length;

  const markerInnerX =
    selectedExceedance != null && selectedExceedance >= 0 && selectedExceedance <= 1
      ? selectedExceedance * innerW
      : null;

  return (
    <div className="w-full">
      <svg width={w} height={height} className="block">
        <g transform={`translate(${pad.l},${pad.t})`}>
          {bins.map((b, i) => {
            const mid = (b.lo + b.hi) / 2;
            const h = (b.count / maxC) * innerH;
            const x = i * bw;
            return (
              <rect
                key={i}
                x={x + 0.5}
                y={innerH - h}
                width={bw - 1}
                height={Math.max(h, 0)}
                fill={binColor(mid)}
                fillOpacity={0.75}
              />
            );
          })}
          {markerInnerX != null ? (
            <line
              x1={markerInnerX}
              x2={markerInnerX}
              y1={0}
              y2={innerH}
              stroke="#0f172a"
              strokeWidth={1.5}
            />
          ) : null}
        </g>
        <text x={w / 2} y={height - 4} textAnchor="middle" className="fill-slate-500 text-[8px]">
          0% — P(transit desert) — 100%
        </text>
      </svg>
    </div>
  );
}
