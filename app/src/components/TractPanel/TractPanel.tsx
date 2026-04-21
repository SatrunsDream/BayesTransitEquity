"use client";

import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link2 } from "lucide-react";
import type { GeoMode, Metadata, ScenarioProperties, TractProperties } from "@/types";
import type { CountyStats } from "@/hooks/useCountyStats";
import { Badge } from "@/components/shared/Badge";
import { StatCard } from "@/components/shared/StatCard";
import { PosteriorPlot } from "@/components/TractPanel/PosteriorPlot";
import { NeighborComparisonPlot } from "@/components/TractPanel/NeighborComparisonPlot";
import { NeighborJsdBars } from "@/components/TractPanel/NeighborJsdBars";
import { InterventionDiff } from "@/components/TractPanel/InterventionDiff";
import { RankBar, exceedancePercentile } from "@/components/TractPanel/RankBar";
import { NarrativeCard } from "@/components/TractPanel/NarrativeCard";
import { ExceedanceHistogram } from "@/components/Charts/ExceedanceHistogram";
import {
  fmtIncome,
  fmtPct2,
  fmtPop,
  shortTractName,
  quartileLabel,
  deltaIndicator,
} from "@/lib/formatters";
import { w2Gaussian, jsdGaussian, hellingerGaussian, jsdLabel } from "@/lib/distances";
import { NEIGHBOR_COLORS } from "@/lib/colorScales";

type Props = {
  onClose: () => void;
  props: TractProperties | null;
  scenarioProps: ScenarioProperties | null;
  mode: GeoMode;
  metadata: Metadata | null;
  neighborGeoids: string[];
  neighborLookup: Map<string, TractProperties>;
  countyStats: CountyStats | null;
};

export function TractPanel({
  onClose,
  props,
  scenarioProps,
  mode,
  metadata,
  neighborGeoids,
  neighborLookup,
  countyStats,
}: Props) {
  const [showNeighbors, setShowNeighbors] = useState(false);
  const [pickedNeighbors, setPickedNeighbors] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const q25 = metadata?.q25_threshold_log1p ?? 8.405;
  const q25Jobs = metadata?.q25_threshold_jobs ?? null;

  const excDisplay = useMemo(() => {
    if (!props) return 0;
    if (
      mode !== "baseline" &&
      scenarioProps != null &&
      scenarioProps.exceedance_prob_scenario != null
    ) {
      return scenarioProps.exceedance_prob_scenario;
    }
    return props.exceedance_prob;
  }, [props, scenarioProps, mode]);

  const coinFlip = Math.abs(excDisplay - 0.5) < 0.06;

  const MAX_OVERLAY = 3;

  const rankPctile = useMemo(() => {
    if (!props || !countyStats?.sortedExceedance.length) return 50;
    return exceedancePercentile(countyStats.sortedExceedance, props.exceedance_prob);
  }, [props, countyStats]);

  const neighborJsdRows = useMemo(() => {
    if (!props || neighborGeoids.length === 0) return [];
    const rows = neighborGeoids
      .map((gid) => {
        const n = neighborLookup.get(gid);
        if (!n) return null;
        return {
          geoid: gid,
          label: shortTractName(n.tract_name),
          jsd: jsdGaussian(props.posterior_mean, props.posterior_sd, n.posterior_mean, n.posterior_sd),
        };
      })
      .filter(Boolean) as { geoid: string; label: string; jsd: number }[];
    return rows.sort((a, b) => a.jsd - b.jsd);
  }, [props, neighborGeoids, neighborLookup]);

  const neighborStats = useMemo(() => {
    if (!props || pickedNeighbors.length === 0) return [];
    return pickedNeighbors.map((gid, i) => {
      const n = neighborLookup.get(gid);
      if (!n) return null;
      const w2 = w2Gaussian(props.posterior_mean, props.posterior_sd, n.posterior_mean, n.posterior_sd);
      const jsd = jsdGaussian(props.posterior_mean, props.posterior_sd, n.posterior_mean, n.posterior_sd);
      const hell = hellingerGaussian(props.posterior_mean, props.posterior_sd, n.posterior_mean, n.posterior_sd);
      return {
        gid,
        name: shortTractName(n.tract_name),
        w2,
        jsd,
        hell,
        color: NEIGHBOR_COLORS[i % NEIGHBOR_COLORS.length],
        n,
      };
    }).filter(Boolean) as {
      gid: string;
      name: string;
      w2: number;
      jsd: number;
      hell: number;
      color: string;
      n: TractProperties;
    }[];
  }, [props, pickedNeighbors, neighborLookup]);

  const toggleNeighborOnPlot = (gid: string) => {
    setPickedNeighbors((prev) => {
      if (prev.includes(gid)) return prev.filter((x) => x !== gid);
      if (prev.length >= MAX_OVERLAY) return [...prev.slice(1), gid];
      return [...prev, gid];
    });
  };

  const neighborCurveSpecs = useMemo(() => {
    if (!props || pickedNeighbors.length === 0)
      return { focal: null, neighbors: [] } as {
        focal: null;
        neighbors: readonly [];
      };
    const focal = {
      mu: props.posterior_mean,
      sigma: props.posterior_sd,
      label: shortTractName(props.tract_name),
      color: "#0f172a",
    };
    const neighbors = pickedNeighbors.map((gid, i) => {
      const n = neighborLookup.get(gid);
      if (!n) return null;
      return {
        mu: n.posterior_mean,
        sigma: n.posterior_sd,
        label: shortTractName(n.tract_name),
        color: NEIGHBOR_COLORS[i % NEIGHBOR_COLORS.length],
      };
    }).filter(Boolean) as { mu: number; sigma: number; label: string; color: string }[];
    return { focal, neighbors };
  }, [props, pickedNeighbors, neighborLookup]);

  const jsdNearest = useMemo(() => {
    if (!props || neighborGeoids.length === 0) return null;
    let best = neighborGeoids[0];
    let bestJ = Infinity;
    for (const gid of neighborGeoids) {
      const n = neighborLookup.get(gid);
      if (!n) continue;
      const j = jsdGaussian(props.posterior_mean, props.posterior_sd, n.posterior_mean, n.posterior_sd);
      if (j < bestJ) {
        bestJ = j;
        best = gid;
      }
    }
    const nb = neighborLookup.get(best);
    if (!nb) return null;
    const h = hellingerGaussian(props.posterior_mean, props.posterior_sd, nb.posterior_mean, nb.posterior_sd);
    return { jsd: bestJ, h, label: jsdLabel(bestJ) };
  }, [props, neighborGeoids, neighborLookup]);

  const copyShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  if (!props) {
    const cs = metadata?.county_summary;
    return (
      <aside className="tract-panel flex w-96 flex-shrink-0 flex-col border-l border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-4">
          <h2 className="text-sm font-bold text-slate-700">San Diego County</h2>
          <p className="mt-0.5 text-[11px] text-slate-500">Click any tract on the map to explore</p>
        </div>
        {cs ? (
          <div className="grid grid-cols-2 gap-2 p-4">
            <StatCard label="Probable deserts" value={cs.n_probable_deserts ?? "—"} />
            <StatCard label="Ambiguous" value={cs.n_ambiguous ?? "—"} />
            <StatCard label="Spearman ρ" value={cs.spearman_equity?.toFixed(4) ?? "—"} />
            <StatCard label="Composite deficit" value={cs.composite_deficit_n ?? "—"} />
          </div>
        ) : null}
        {countyStats ? (
          <div className="border-t border-slate-100 px-4 py-3">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              County exceedance distribution
            </div>
            <ExceedanceHistogram bins={countyStats.exceedanceBins} />
          </div>
        ) : null}
      </aside>
    );
  }

  const q = props.disadv_quartile ?? 2;

  return (
    <motion.aside
      className="tract-panel flex w-96 flex-shrink-0 flex-col overflow-y-auto border-l border-slate-200 bg-white shadow-lg"
      initial={{ x: 40, opacity: 0.95 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-100 bg-white px-4 py-3">
        <div>
          <h2 className="text-sm font-bold text-slate-900">{shortTractName(props.tract_name)}</h2>
          <p className="font-mono text-[11px] text-slate-500">{props.geoid}</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {coinFlip ? (
              <Badge tone="amber">Coin-flip</Badge>
            ) : excDisplay >= 0.5 ? (
              <Badge tone="red">Desert &gt;50%</Badge>
            ) : excDisplay >= 0.2 ? (
              <Badge tone="amber">Moderate</Badge>
            ) : (
              <Badge tone="emerald">Lower risk</Badge>
            )}
            <Badge tone="blue">{quartileLabel(q)}</Badge>
            {mode !== "baseline" && scenarioProps?.crossed_threshold ? (
              <Badge tone="emerald">Crossed threshold</Badge>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            title="Copy link to this tract"
            onClick={copyShare}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Copy share link"
          >
            <Link2 className="h-4 w-4" />
          </button>
          {copied ? <span className="text-[10px] text-teal-600">Copied!</span> : null}
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close panel"
          >
            ×
          </button>
        </div>
      </div>

      <div className="px-4 pt-3">
        <NarrativeCard
          tractProps={props}
          scenarioProps={scenarioProps}
          mode={mode}
          rankPctile={rankPctile}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 p-4">
        <StatCard
          label="P(transit desert)"
          value={fmtPct2(excDisplay)}
          sub={
            mode !== "baseline" && scenarioProps
              ? `was ${fmtPct2(props.exceedance_prob)} · ${deltaIndicator(scenarioProps.exceedance_prob_delta)}`
              : undefined
          }
          warn={coinFlip}
        />
        <StatCard label="Post. mean jobs" value={fmtPop(props.posterior_mean_jobs)} />
        <StatCard
          label="95% CI width (log1p)"
          value={(props.ci_upper_95 - props.ci_lower_95).toFixed(2)}
        />
        <StatCard label="Population" value={fmtPop(props.pop_total)} />
        <StatCard label="No-vehicle HH" value={fmtPct2(props.pct_no_vehicle)} />
        <StatCard label="Median income" value={fmtIncome(props.median_income)} />
      </div>

      {countyStats ? (
        <div className="border-t border-slate-100 px-4 py-3">
          <RankBar value={props.exceedance_prob} sortedValues={countyStats.sortedExceedance} />
        </div>
      ) : null}

      <div className="border-t border-slate-100 px-4 py-3">
        <PosteriorPlot
          mu={props.posterior_mean}
          sigma={props.posterior_sd}
          q25Log1p={q25}
          exceedance={props.exceedance_prob}
          scenarioExceedance={
            mode !== "baseline" && scenarioProps ? scenarioProps.exceedance_prob_scenario : null
          }
          q25ThresholdJobs={q25Jobs}
        />
      </div>

      {mode !== "baseline" && scenarioProps ? (
        <div className="border-t border-slate-100 px-4 py-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Intervention impact
          </div>
          <InterventionDiff
            mu={props.posterior_mean}
            sigma={props.posterior_sd}
            scenarioExceedance={scenarioProps.exceedance_prob_scenario}
            baselineExceedance={props.exceedance_prob}
            crossedThreshold={scenarioProps.crossed_threshold}
            q25Log1p={q25}
            deltaCI={{
              lower: scenarioProps.exceedance_delta_ci_lower,
              upper: scenarioProps.exceedance_delta_ci_upper,
            }}
          />
        </div>
      ) : null}

      <div className="border-t border-slate-100 px-4 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Wasserstein distance (vs well-served reference)
        </div>
        <p className="mt-1 text-[9px] leading-snug text-slate-500">
          Lower = closer to the well-served reference tract on the log₁p scale. Q1 (least disadvantaged)
          tracts often sit farther — the density confound.
        </p>
        <div className="mt-2 text-sm text-slate-700">
          This tract:{" "}
          <strong>{props.wasserstein_dist.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong>
        </div>
        {metadata ? (
          <div className="mt-2 space-y-1 text-[11px] text-slate-600">
            <div className="flex justify-between">
              <span>County mean</span>
              <span>{metadata.county_summary.wasserstein_county_mean?.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Q1 (least disadv.) mean</span>
              <span>{metadata.county_summary.wasserstein_q1_mean?.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Q4 (most disadv.) mean</span>
              <span>{metadata.county_summary.wasserstein_q4_mean?.toLocaleString()}</span>
            </div>
          </div>
        ) : null}
        {jsdNearest ? (
          <div className="mt-3 text-[11px] text-slate-600">
            JSD (nearest neighbor): <strong>{jsdNearest.jsd.toFixed(3)}</strong> ({jsdNearest.label}) ·
            Hellinger: <strong>{jsdNearest.h.toFixed(3)}</strong>
          </div>
        ) : null}
      </div>

      <div className="border-t border-slate-100 px-4 py-3">
        <button
          type="button"
          className="text-xs font-medium text-blue-600 hover:underline"
          onClick={() => setShowNeighbors((s) => !s)}
        >
          {showNeighbors ? "Hide neighbors" : "Compare neighbors"}
        </button>
        {showNeighbors ? (
          <div className="mt-3 space-y-4">
            <NeighborJsdBars
              rows={neighborJsdRows}
              activeGeoids={new Set(pickedNeighbors)}
              onRowClick={toggleNeighborOnPlot}
            />

            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                On plot (max {MAX_OVERLAY})
              </div>
              <div className="mt-1 flex max-h-24 flex-wrap gap-1 overflow-y-auto">
                {neighborGeoids.map((gid) => (
                  <button
                    key={gid}
                    type="button"
                    onClick={() => toggleNeighborOnPlot(gid)}
                    className={`rounded-full border px-2 py-0.5 font-mono text-[10px] ${
                      pickedNeighbors.includes(gid)
                        ? "border-blue-500 bg-blue-50 text-blue-800"
                        : "border-slate-200 bg-white text-slate-600"
                    }`}
                  >
                    …{gid.slice(-5)}
                  </button>
                ))}
              </div>
            </div>

            {neighborCurveSpecs.focal && neighborCurveSpecs.neighbors.length > 0 ? (
              <>
                <NeighborComparisonPlot
                  focal={neighborCurveSpecs.focal}
                  neighbors={neighborCurveSpecs.neighbors}
                  q25Log1p={q25}
                />
                <div className="rounded-lg border border-slate-100 bg-slate-50/80 p-2">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                    Pair metrics (Gaussian surrogates · log₁p scale)
                  </div>
                  <table className="mt-1 w-full text-[10px]">
                    <thead>
                      <tr className="text-left text-slate-500">
                        <th className="pb-1 pr-1">Neighbor</th>
                        <th className="pb-1 pr-1">JSD</th>
                        <th className="pb-1 pr-1">Hellinger</th>
                        <th className="pb-1">W₂</th>
                      </tr>
                    </thead>
                    <tbody>
                      {neighborStats.map((s) => (
                        <tr key={s.gid} className="border-t border-slate-200 text-slate-800">
                          <td className="py-1 pr-1">
                            <span style={{ color: s.color }}>●</span> {s.name}
                          </td>
                          <td className="font-mono pr-1">{s.jsd.toFixed(3)}</td>
                          <td className="font-mono pr-1">{s.hell.toFixed(3)}</td>
                          <td className="font-mono">{s.w2.toFixed(3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="text-[10px] text-slate-500">
                Click a bar or pill to add up to {MAX_OVERLAY} neighbors on the plot.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </motion.aside>
  );
}
