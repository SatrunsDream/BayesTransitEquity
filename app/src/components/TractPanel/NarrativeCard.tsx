"use client";

import type { GeoMode, ScenarioProperties, TractProperties } from "@/types";
import { fmtIncome, fmtPct2, shortTractName } from "@/lib/formatters";

type Props = {
  tractProps: TractProperties;
  scenarioProps: ScenarioProperties | null;
  mode: GeoMode;
  rankPctile: number;
};

export function NarrativeCard({
  tractProps,
  scenarioProps,
  mode,
  rankPctile,
}: Props) {
  const name = shortTractName(tractProps.tract_name);
  const exc = tractProps.exceedance_prob;
  const coinFlip = Math.abs(exc - 0.5) < 0.06;
  const income = tractProps.median_income;
  const incomeParadox = income > 80_000 && exc > 0.4;
  const q = tractProps.disadv_quartile ?? 2;

  const parts: string[] = [];
  parts.push(
    `${name} has a ${fmtPct2(exc)} posterior chance of being a transit desert (rank ~${Math.round(rankPctile)}th percentile for desert risk among county tracts).`,
  );

  if (coinFlip) {
    parts.push(
      "This near 50/50 split makes it one of the more uncertain tracts — the posterior straddles the desert threshold.",
    );
  }

  if (incomeParadox) {
    parts.push(
      `Despite median income around ${fmtIncome(income)}, modeled access remains low — consistent with a suburban density confound where income does not guarantee frequent transit.`,
    );
  }

  if (q === 4) {
    parts.push(
      "As a Q4 (most disadvantaged) tract, transit gaps here compound existing socioeconomic burdens.",
    );
  }

  if (mode !== "baseline" && scenarioProps?.crossed_threshold) {
    parts.push(
      `After the targeted intervention (scenario), P(transit desert) falls to ${fmtPct2(scenarioProps.exceedance_prob_scenario)} — this tract exits the high-risk desert zone under the posterior.`,
    );
  }

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50/90 p-3 text-xs leading-relaxed text-slate-700">
      {parts.join(" ")}
    </div>
  );
}
