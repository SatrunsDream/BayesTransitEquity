"use client";

import { useMemo } from "react";
import { scaleLinear } from "@visx/scale";
import { AreaClosed, LinePath } from "@visx/shape";
import { AxisBottom } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { computeKDE, credibleIntervals, meanImplyingExceedance } from "@/lib/kde";
import { fmtJobs } from "@/lib/formatters";

const M = { top: 8, right: 8, bottom: 32, left: 36 };
const W = 320;
const H = 180;

type Props = {
  mu: number;
  sigma: number;
  q25Log1p: number;
  exceedance: number;
  /** Optional second curve (scenario) — implied μ from target exceedance, same σ */
  scenarioExceedance?: number | null;
  /** County Q25 threshold in job counts (from metadata) */
  q25ThresholdJobs?: number | null;
};

export function PosteriorPlot({
  mu,
  sigma,
  q25Log1p,
  exceedance,
  scenarioExceedance,
  q25ThresholdJobs,
}: Props) {
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  const pts = useMemo(() => computeKDE(mu, sigma, 100, 4), [mu, sigma]);
  const pts2 = useMemo(() => {
    if (scenarioExceedance == null || scenarioExceedance === exceedance) return null;
    const mu2 = meanImplyingExceedance(q25Log1p, sigma, scenarioExceedance);
    return computeKDE(mu2, sigma, 100, 4);
  }, [mu, sigma, q25Log1p, scenarioExceedance, exceedance]);

  const { lo95, hi95 } = useMemo(() => credibleIntervals(mu, sigma), [mu, sigma]);
  const pts95 = useMemo(
    () => pts.filter((p) => p.x >= lo95 && p.x <= hi95),
    [pts, lo95, hi95],
  );

  const xMin = Math.min(...pts.map((p) => p.x), q25Log1p - 0.5);
  const xMax = Math.max(...pts.map((p) => p.x), q25Log1p + 0.5);
  const yMax = Math.max(...pts.map((p) => p.y), 1e-6) * 1.15;

  const xScale = useMemo(
    () =>
      scaleLinear<number>({ range: [0, innerW], domain: [xMin, xMax], nice: true }),
    [innerW, xMin, xMax],
  );
  const yScale = useMemo(
    () => scaleLinear<number>({ range: [innerH, 0], domain: [0, yMax], nice: true }),
    [innerH, yMax],
  );

  return (
    <div className="w-full overflow-hidden">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Posterior (Normal approx.) · log₁p jobs
      </div>
      <svg width={W} height={H} className="mt-1">
        <g transform={`translate(${M.left},${M.top})`}>
          <AreaClosed
            data={pts95}
            x={(d) => xScale(d.x) ?? 0}
            y={(d) => yScale(d.y) ?? 0}
            yScale={yScale}
            curve={curveMonotoneX}
            fill="#BFDBFE"
            fillOpacity={0.55}
          />
          <LinePath
            data={pts}
            x={(d) => xScale(d.x) ?? 0}
            y={(d) => yScale(d.y) ?? 0}
            curve={curveMonotoneX}
            stroke="#1E293B"
            strokeWidth={1.5}
          />
          {pts2 ? (
            <LinePath
              data={pts2}
              x={(d) => xScale(d.x) ?? 0}
              y={(d) => yScale(d.y) ?? 0}
              curve={curveMonotoneX}
              stroke="#0D9488"
              strokeWidth={1.5}
              strokeDasharray="4 3"
            />
          ) : null}
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
            tickValues={[xMin, q25Log1p, xMax].filter((v, i, a) => a.indexOf(v) === i)}
            tickFormat={(v) =>
              Math.abs(Number(v) - q25Log1p) < 0.05 ? "Q25" : Number(v).toFixed(1)
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
      <div className="mt-1 flex flex-wrap justify-between gap-2 text-[9px] text-slate-500">
        <span>
          95% CI (jobs):{" "}
          <strong>
            {fmtJobs(Math.expm1(lo95))} – {fmtJobs(Math.expm1(hi95))}
          </strong>
        </span>
        {q25ThresholdJobs != null ? (
          <span>
            Q25 threshold: <strong>{fmtJobs(q25ThresholdJobs)}</strong> jobs
          </span>
        ) : (
          <span>
            Q25 (from log1p): <strong>{fmtJobs(Math.expm1(q25Log1p))}</strong> jobs
          </span>
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-3 text-[10px] text-slate-600">
        <span>
          P(below Q25): <strong>{(exceedance * 100).toFixed(1)}%</strong>
        </span>
        {pts2 ? (
          <span className="text-teal-700">
            Scenario P(below): <strong>{((scenarioExceedance ?? 0) * 100).toFixed(2)}%</strong>
          </span>
        ) : null}
      </div>
    </div>
  );
}
