"use client";

import { useMemo } from "react";
import type { FeatureCollection } from "geojson";
import type { TractProperties } from "@/types";

export interface CountyStats {
  sortedExceedance: number[];
  exceedanceBins: Array<{ lo: number; hi: number; count: number }>;
  scatterData: Array<{
    geoid: string;
    income: number;
    exceedance: number;
    pop: number;
    quartile: number;
    name: string;
  }>;
}

const N_BINS = 20;

function buildBins(values: number[]): CountyStats["exceedanceBins"] {
  const bins: CountyStats["exceedanceBins"] = [];
  const w = 1 / N_BINS;
  for (let b = 0; b < N_BINS; b++) {
    const lo = b * w;
    const hi = (b + 1) * w;
    const count = values.filter((v) => v >= lo && (b === N_BINS - 1 ? v <= hi : v < hi)).length;
    bins.push({ lo, hi, count });
  }
  return bins;
}

export function useCountyStats(baseline: FeatureCollection | null): CountyStats | null {
  return useMemo(() => {
    if (!baseline?.features?.length) return null;
    const exceedance: number[] = [];
    const scatterData: CountyStats["scatterData"] = [];
    for (const f of baseline.features) {
      const p = f.properties as TractProperties;
      const e = p.exceedance_prob ?? 0;
      exceedance.push(e);
      scatterData.push({
        geoid: p.geoid,
        income: p.median_income ?? 0,
        exceedance: e,
        pop: p.pop_total ?? 0,
        quartile: p.disadv_quartile ?? 1,
        name: p.tract_name ?? p.geoid,
      });
    }
    const sortedExceedance = [...exceedance].sort((a, b) => a - b);
    return {
      sortedExceedance,
      exceedanceBins: buildBins(exceedance),
      scatterData,
    };
  }, [baseline]);
}
