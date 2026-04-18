/**
 * distances.ts
 * Distributional distance metrics between two Gaussian posteriors.
 * All parameters on the log1p(jobs) scale.
 */

/**
 * 2-Wasserstein distance between N(μ₁,σ₁) and N(μ₂,σ₂).
 * Closed-form: W₂² = (μ₁-μ₂)² + (σ₁-σ₂)²
 * NOTE: This is on the log1p scale. We multiply by exp(mean) to get
 *       approximate job-scale magnitude for display.
 */
export function w2Gaussian(
  mu1: number, sigma1: number,
  mu2: number, sigma2: number,
): number {
  return Math.sqrt(Math.pow(mu1 - mu2, 2) + Math.pow(sigma1 - sigma2, 2));
}

/**
 * Jensen-Shannon Divergence between N(μ₁,σ₁) and N(μ₂,σ₂).
 * Numerically estimated via 500-point grid integration.
 * Returns value in [0, ln(2)] ≈ [0, 0.693].
 */
export function jsdGaussian(
  mu1: number, sigma1: number,
  mu2: number, sigma2: number,
  nPts = 500,
): number {
  const xMin = Math.min(mu1, mu2) - 4 * Math.max(sigma1, sigma2);
  const xMax = Math.max(mu1, mu2) + 4 * Math.max(sigma1, sigma2);
  const dx = (xMax - xMin) / nPts;

  let jsd = 0;
  for (let i = 0; i < nPts; i++) {
    const x = xMin + (i + 0.5) * dx;
    const p = normalPdf(x, mu1, sigma1);
    const q = normalPdf(x, mu2, sigma2);
    const m = 0.5 * (p + q);
    if (p > 1e-12) jsd += 0.5 * p * Math.log(p / m) * dx;
    if (q > 1e-12) jsd += 0.5 * q * Math.log(q / m) * dx;
  }
  return Math.max(0, jsd);
}

/**
 * Hellinger distance between N(μ₁,σ₁) and N(μ₂,σ₂).
 * Closed-form: H² = 1 - √(2σ₁σ₂/(σ₁²+σ₂²)) · exp(−(μ₁-μ₂)²/(4(σ₁²+σ₂²)))
 */
export function hellingerGaussian(
  mu1: number, sigma1: number,
  mu2: number, sigma2: number,
): number {
  const s1sq = sigma1 * sigma1;
  const s2sq = sigma2 * sigma2;
  const coef = Math.sqrt((2 * sigma1 * sigma2) / (s1sq + s2sq));
  const exp = Math.exp(-(Math.pow(mu1 - mu2, 2) / (4 * (s1sq + s2sq))));
  const h2   = 1 - coef * exp;
  return Math.sqrt(Math.max(0, h2));
}

function normalPdf(x: number, mu: number, sigma: number): number {
  const z = (x - mu) / sigma;
  return Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI));
}

/** Classify JSD for color coding */
export function jsdLabel(jsd: number): "low" | "moderate" | "high" {
  if (jsd < 0.05) return "low";
  if (jsd < 0.2)  return "moderate";
  return "high";
}
