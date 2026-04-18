/** Format a job count with comma separator */
export function fmtJobs(n: number): string {
  return n < 1 ? "<1" : Math.round(n).toLocaleString();
}

/** Format a probability as percentage with 1 dp */
export function fmtPct(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

/** Format a probability as "49.98%" with 2 dp */
export function fmtPct2(p: number): string {
  return `${(p * 100).toFixed(2)}%`;
}

/** Format income as "$42.1k" */
export function fmtIncome(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}k`;
  return `$${Math.round(n)}`;
}

/** Format population with comma */
export function fmtPop(n: number): string {
  return Math.round(n).toLocaleString();
}

/** Format Wasserstein distance: "34,618" */
export function fmtWass(w: number): string {
  if (w >= 1_000) return `${Math.round(w / 1_000).toLocaleString()}k`;
  return Math.round(w).toString();
}

/** Shorten a tract name: "Census Tract 133.17; San Diego County; California" → "Tract 133.17" */
export function shortTractName(name: string): string {
  const m = name.match(/Census Tract ([^;]+)/i);
  return m ? `Tract ${m[1].trim()}` : name.split(";")[0].trim();
}

/** Advantage quartile label */
export function quartileLabel(q: number): string {
  return ["Q1 (least disadvantaged)", "Q2", "Q3", "Q4 (most disadvantaged)"][q - 1] ?? `Q${q}`;
}

/** Delta arrow indicator */
export function deltaIndicator(delta: number): string {
  if (delta < -0.001) return `↓ ${fmtPct(Math.abs(delta))} pp`;
  if (delta > 0.001)  return `↑ ${fmtPct(delta)} pp`;
  return "—";
}
