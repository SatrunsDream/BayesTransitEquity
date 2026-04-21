"use client";

import { useMemo } from "react";
import { scaleLinear } from "@visx/scale";
import { LinePath } from "@visx/shape";
import { AxisBottom } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { computeKDE, meanImplyingExceedance } from "@/lib/kde";
import { fmtPct2 } from "@/lib/formatters";

const M = { top: 10, right: 10, bottom: 36, left: 38 };
const W = 320;
const H = 200;

type Props = {
  mu: number;
  sigma: number;
  scenarioExceedance: number;
  baselineExceedance: number;
  crossedThreshold: boolean;
  q25Log1p: number;
  deltaCI?: { lower: number; upper: number };
};

export function InterventionDiff({
  mu,
  sigma,
  scenarioExceedance,
  baselineExceedance,
  crossedThreshold,
  q25Log1p,
  deltaCI,
}: Props) {
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  const muScenario = useMemo(
    () => meanImplyingExceedance(q25Log1p, sigma, scenarioExceedance),
    [q25Log1p, sigma, scenarioExceedance],
  );

  const ptsBase = useMemo(() => computeKDE(mu, sigma, 120, 4), [mu, sigma]);
  const ptsScenario = useMemo(() => computeKDE(muScenario, sigma, 120, 4), [muScenario, sigma]);

  const { xMin, xMax, yMax } = useMemo(() => {
    let x0 = Math.min(q25Log1p - 0.5, ...ptsBase.map((p) => p.x));
    let x1 = Math.max(q25Log1p + 0.5, ...ptsBase.map((p) => p.x));
    let yM = Math.max(...ptsBase.map((p) => p.y), 1e-6);
    for (const p of ptsScenario) {
      x0 = Math.min(x0, p.x);
      x1 = Math.max(x1, p.x);
      yM = Math.max(yM, p.y);
    }
    return { xMin: x0, xMax: x1, yMax: yM * 1.12 };
  }, [ptsBase, ptsScenario, q25Log1p]);

  const xScale = useMemo(
    () => scaleLinear<number>({ range: [0, innerW], domain: [xMin, xMax], nice: true }),
    [innerW, xMin, xMax],
  );
  const yScale = useMemo(
    () => scaleLinear<number>({ range: [innerH, 0], domain: [0, yMax], nice: true }),
    [innerH, yMax],
  );

  const deltaPp = (baselineExceedance - scenarioExceedance) * 100;

  return (
    <div className="w-full">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Intervention impact (Normal approx.)
      </div>
      <p className="mt-0.5 text-[9px] leading-snug text-slate-500">
        Gray: baseline posterior N(μ, σ). Teal: implied N(μ*, σ) after scenario so P(below Q25) matches
        scenario exceedance.
      </p>
      <svg width={W} height={H} className="mt-1">
        <g transform={`translate(${M.left},${M.top})`}>
          <LinePath
            data={ptsBase}
            x={(d) => xScale(d.x) ?? 0}
            y={(d) => yScale(d.y) ?? 0}
            curve={curveMonotoneX}
            stroke="#64748b"
            strokeWidth={1.75}
            strokeOpacity={0.9}
          />
          <LinePath
            data={ptsScenario}
            x={(d) => xScale(d.x) ?? 0}
            y={(d) => yScale(d.y) ?? 0}
            curve={curveMonotoneX}
            stroke="#0D9488"
            strokeWidth={2}
            strokeOpacity={0.95}
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
      <div className="mt-2 space-y-1 rounded-lg border border-slate-100 bg-slate-50/90 p-2 text-[10px]">
        <div className="flex justify-between gap-2 text-slate-700">
          <span>Before P(desert)</span>
          <span className="font-mono font-medium">{fmtPct2(baselineExceedance)}</span>
        </div>
        <div className="flex justify-between gap-2 text-slate-700">
          <span>After P(desert)</span>
          <span className="font-mono font-medium text-teal-600">{fmtPct2(scenarioExceedance)}</span>
        </div>
        <div className="flex justify-between gap-2 text-slate-700">
          <span>Δ Exceedance</span>
          <span className="font-mono font-medium">
            ↓ {deltaPp.toFixed(1)} pp
          </span>
        </div>
        {deltaCI != null &&
        Number.isFinite(deltaCI.lower) &&
        Number.isFinite(deltaCI.upper) ? (
          <div className="text-[9px] text-slate-500">
            Δ 95% CI: [{fmtPct2(deltaCI.lower)}, {fmtPct2(deltaCI.upper)}] (exceedance delta)
          </div>
        ) : null}
        {crossedThreshold ? (
          <div className="inline-flex rounded-md bg-teal-100 px-2 py-0.5 text-[10px] font-semibold text-teal-700">
            Exits desert zone (crosses Q25 threshold)
          </div>
        ) : null}
      </div>
    </div>
  );
}
