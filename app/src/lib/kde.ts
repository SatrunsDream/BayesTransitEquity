/**
 * kde.ts
 * Generate a Normal PDF KDE from (mean, sigma) parameters.
 * All values on the log1p(jobs) scale.
 */

import type { KDEPoint } from "@/types";

/** Standard Normal PDF */
function normalPdf(x: number, mu: number, sigma: number): number {
  const z = (x - mu) / sigma;
  return Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI));
}

/**
 * Generate N evenly-spaced (x, y) points for a Normal distribution.
 * @param mu     - posterior mean (log1p scale)
 * @param sigma  - posterior SD (log1p scale)
 * @param nPts   - number of evaluation points (default 120)
 * @param spans  - how many SDs either side to cover (default 4)
 */
export function computeKDE(
  mu: number,
  sigma: number,
  nPts = 120,
  spans = 4,
): KDEPoint[] {
  const xMin = mu - spans * sigma;
  const xMax = mu + spans * sigma;
  return Array.from({ length: nPts }, (_, i) => {
    const x = xMin + (i / (nPts - 1)) * (xMax - xMin);
    return { x, y: normalPdf(x, mu, sigma) };
  });
}

/**
 * Area to the LEFT of threshold under Normal(mu, sigma).
 * This is the exceedance probability (P(desert)).
 * Uses the complementary error function approximation.
 */
export function normalCDF(x: number, mu: number, sigma: number): number {
  return 0.5 * (1 + erf((x - mu) / (sigma * Math.SQRT2)));
}

function erf(x: number): number {
  // Abramowitz & Stegun approximation (max error ~1.5e-7)
  const t = 1.0 / (1.0 + 0.3275911 * Math.abs(x));
  const poly =
    t * (0.254829592 +
    t * (-0.284496736 +
    t * (1.421413741 +
    t * (-1.453152027 +
    t * 1.061405429))));
  const result = 1.0 - poly * Math.exp(-x * x);
  return x >= 0 ? result : -result;
}

/**
 * Credible interval bounds — return [lo, hi] in log1p units.
 * - inner50: 25th–75th percentile (±0.674σ)
 * - outer95: 2.5th–97.5th percentile (±1.96σ)
 */
export function credibleIntervals(mu: number, sigma: number) {
  return {
    lo95: mu - 1.96 * sigma,
    hi95: mu + 1.96 * sigma,
    lo50: mu - 0.674 * sigma,
    hi50: mu + 0.674 * sigma,
  };
}

/** Inverse standard-normal CDF via bisection (Phi(z) = p). */
export function quantileStandardNormal(p: number): number {
  const p0 = Math.min(1 - 1e-12, Math.max(1e-12, p));
  let lo = -8;
  let hi = 8;
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) * 0.5;
    if (normalCDF(mid, 0, 1) < p0) lo = mid;
    else hi = mid;
  }
  return (lo + hi) * 0.5;
}

/**
 * For Normal(μ,σ), find μ* such that P(X < threshold) = exceedance.
 * μ* = threshold - σ * Phi^{-1}(exceedance).
 */
export function meanImplyingExceedance(
  threshold: number,
  sigma: number,
  exceedance: number,
): number {
  const p = Math.min(1 - 1e-12, Math.max(1e-12, exceedance));
  const z = quantileStandardNormal(p);
  return threshold - sigma * z;
}
