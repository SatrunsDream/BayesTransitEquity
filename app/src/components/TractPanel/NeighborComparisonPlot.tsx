"use client";

import { useMemo } from "react";
import { scaleLinear } from "@visx/scale";
import { AreaClosed, LinePath } from "@visx/shape";
import { AxisBottom } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { computeKDE, credibleIntervals } from "@/lib/kde";

const M = { top: 10, right: 10, bottom: 36, left: 38 };
const W = 320;
const H = 200;

export type NeighborCurveSpec = {
  mu: number;
  sigma: number;
  label: string;
  color: string;
  dashed?: boolean;
};

type Props = {
  /** Selected tract (drawn thicker + light95% band) */
  focal: NeighborCurveSpec;
  /** Adjacent tracts to overlay (Normal approx., same as focal) */
  neighbors: NeighborCurveSpec[];
  q25Log1p: number;
};

export function NeighborComparisonPlot({ focal, neighbors, q25Log1p }: Props) {
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  const focalPts = useMemo(() => computeKDE(focal.mu, focal.sigma, 120, 4), [focal.mu, focal.sigma]);
  const { lo95, hi95 } = credibleIntervals(focal.mu, focal.sigma);
  const focalBand = useMemo(
    () => focalPts.filter((p) => p.x >= lo95 && p.x <= hi95),
    [focalPts, lo95, hi95],
  );

  const neighborPtsList = useMemo(
    () =>
      neighbors.map((n) => ({
        ...n,
        pts: computeKDE(n.mu, n.sigma, 120, 4),
      })),
    [neighbors],
  );

  const { xMin, xMax, yMax } = useMemo(() => {
    let x0 = Math.min(q25Log1p - 0.5, ...focalPts.map((p) => p.x));
    let x1 = Math.max(q25Log1p + 0.5, ...focalPts.map((p) => p.x));
    let yM = Math.max(...focalPts.map((p) => p.y), 1e-6);
    for (const row of neighborPtsList) {
      for (const p of row.pts) {
        x0 = Math.min(x0, p.x);
        x1 = Math.max(x1, p.x);
        yM = Math.max(yM, p.y);
      }
    }
    return { xMin: x0, xMax: x1, yMax: yM * 1.12 };
  }, [focalPts, neighborPtsList, q25Log1p]);

  const xScale = useMemo(
    () => scaleLinear<number>({ range: [0, innerW], domain: [xMin, xMax], nice: true }),
    [innerW, xMin, xMax],
  );
  const yScale = useMemo(
    () => scaleLinear<number>({ range: [innerH, 0], domain: [0, yMax], nice: true }),
    [innerH, yMax],
  );

  return (
    <div className="w-full">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Neighbor comparison (Normal approx.) · log₁p scale
      </div>
      <p className="mt-0.5 text-[9px] leading-snug text-slate-500">
        Curves use tract posterior mean &amp; SD. JSD / Hellinger in the table are between these
        same Gaussian surrogates.
      </p>
      <svg width={W} height={H} className="mt-1">
        <g transform={`translate(${M.left},${M.top})`}>
          {/* Focal 95% band (very light) */}
          <AreaClosed
            data={focalBand}
            x={(d) => xScale(d.x) ?? 0}
            y={(d) => yScale(d.y) ?? 0}
            yScale={yScale}
            curve={curveMonotoneX}
            fill="#E2E8F0"
            fillOpacity={0.45}
          />
          {neighborPtsList.map((row) => (
            <LinePath
              key={row.label}
              data={row.pts}
              x={(d) => xScale(d.x) ?? 0}
              y={(d) => yScale(d.y) ?? 0}
              curve={curveMonotoneX}
              stroke={row.color}
              strokeWidth={1.25}
              strokeOpacity={0.9}
              strokeDasharray={row.dashed ? "4 3" : undefined}
            />
          ))}
          <LinePath
            data={focalPts}
            x={(d) => xScale(d.x) ?? 0}
            y={(d) => yScale(d.y) ?? 0}
            curve={curveMonotoneX}
            stroke={focal.color}
            strokeWidth={2.25}
          />
          <line
            x1={xScale(q25Log1p) ?? 0}
            x2={xScale(q25Log1p) ?? 0}
            y1={0}
            y2={innerH}
            stroke="#EF4444"
            strokeWidth={1}
            strokeDasharray="4 2"
          />
          <AxisBottom
            top={innerH}
            scale={xScale}
            numTicks={4}
            tickFormat={(v) =>
              Math.abs(Number(v) - q25Log1p) < 0.06 ? "Q25" : Number(v).toFixed(1)
            }
            stroke="#94a3b8"
            tickStroke="#94a3b8"
            tickLabelProps={() => ({
              fill: "#64748b",
              fontSize: 9,
              textAnchor: "middle",
            })}
          />
        </g>
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[9px]">
        <span className="font-medium text-slate-800">
          <span style={{ color: focal.color }}>━━</span> {focal.label}
        </span>
        {neighbors.map((n) => (
          <span key={n.label} className="text-slate-600">
            <span style={{ color: n.color }}>━━</span> {n.label}
          </span>
        ))}
      </div>
    </div>
  );
}
