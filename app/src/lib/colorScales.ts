/**
 * colorScales.ts
 * Metric value → RGBA array for Deck.gl GeoJsonLayer.
 */

import type { LayerMetric } from "@/types";

// Blue → Amber → Red  (safe → coin-flip → desert)
const DESERT_STOPS = [
  { t: 0.0,  r: 59,  g: 130, b: 246 }, // #3B82F6 blue-500
  { t: 0.3,  r: 96,  g: 165, b: 250 }, // #60A5FA blue-400
  { t: 0.5,  r: 245, g: 158, b: 11  }, // #F59E0B amber-500
  { t: 0.75, r: 248, g: 113, b: 113 }, // #F87171 red-400
  { t: 1.0,  r: 239, g: 68,  b: 68  }, // #EF4444 red-500
];

// Purple → Yellow (posterior mean / viridis-like)
const MEAN_STOPS = [
  { t: 0, r: 126, g: 34,  b: 206 }, // purple-700
  { t: 1, r: 245, g: 158, b: 11  }, // amber
];

// White → Indigo (Wasserstein)
const WASS_STOPS = [
  { t: 0, r: 224, g: 231, b: 255 }, // indigo-100
  { t: 1, r: 67,  g: 56,  b: 202 }, // indigo-700
];

// Teal → White → White (delta — only negative deltas shown as teal)
const DELTA_STOPS = [
  { t: 0,   r: 13,  g: 148, b: 136 }, // teal-600 (improved a lot)
  { t: 0.5, r: 241, g: 245, b: 249 }, // slate-100 (no change)
  { t: 1.0, r: 241, g: 245, b: 249 }, // slate-100
];

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function interpolate(
  stops: { t: number; r: number; g: number; b: number }[],
  value: number,
): [number, number, number, number] {
  const v = Math.max(0, Math.min(1, value));
  for (let i = 0; i < stops.length - 1; i++) {
    const lo = stops[i];
    const hi = stops[i + 1];
    if (v <= hi.t) {
      const t = (v - lo.t) / (hi.t - lo.t);
      return [
        Math.round(lerp(lo.r, hi.r, t)),
        Math.round(lerp(lo.g, hi.g, t)),
        Math.round(lerp(lo.b, hi.b, t)),
        210,
      ];
    }
  }
  const last = stops[stops.length - 1];
  return [last.r, last.g, last.b, 210];
}

/** Returns [r, g, b, a] for Deck.gl getFillColor */
export function getColor(
  metric: LayerMetric,
  value: number,
  maxWass = 90000,
  maxMean = 12,
  minMean = 4,
): [number, number, number, number] {
  switch (metric) {
    case "exceedance_prob":
      return interpolate(DESERT_STOPS, value);

    case "posterior_mean": {
      const t = (value - minMean) / (maxMean - minMean);
      return interpolate(MEAN_STOPS, t);
    }

    case "wasserstein_dist":
      return interpolate(WASS_STOPS, value / maxWass);

    case "ci_width": {
      // normalise: typical SD is 0.05–0.25 log1p units
      // ci_width ≈ 2 × 1.96 × sigma ≈ 3.92σ; max shown at σ=0.3
      const norm = Math.min(1, value / (3.92 * 0.3));
      return interpolate(WASS_STOPS, norm);
    }

    case "delta":
      // delta is negative (improved), flip sign and normalise to [0,1]
      return interpolate(DELTA_STOPS, Math.max(0, -value));

    default:
      return [180, 180, 180, 180];
  }
}

/** Line color for selected tract outline */
export const SELECTED_LINE: [number, number, number, number] = [255, 255, 255, 255];
export const TARGET_LINE: [number, number, number, number]   = [251, 191, 36, 255]; // amber-400
export const CROSSED_LINE: [number, number, number, number]  = [20, 184, 166, 255]; // teal-500

/** Neighbour palette for KDE overlays */
export const NEIGHBOR_COLORS = [
  "#F97316", // orange-500
  "#10B981", // emerald-500
  "#8B5CF6", // violet-500
  "#EC4899", // pink-500
];
