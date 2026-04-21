"use client";

import { motion, AnimatePresence } from "framer-motion";

export function InfoModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="max-h-[85vh] max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-bold text-slate-900">Methodology</h2>

            <section className="mt-4 rounded-lg border border-slate-100 bg-slate-50/80 p-3">
              <h3 className="text-sm font-semibold text-slate-800">What is P(transit desert)?</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                <strong>Exceedance probability</strong> is the posterior probability that tract-level job
                accessibility (log₁p jobs within 45 minutes) falls <em>below</em> the county Q25
                threshold. High values mean the model assigns substantial probability to “desert”
                outcomes under that definition.
              </p>
            </section>

            <section className="mt-4 rounded-lg border border-slate-100 bg-slate-50/80 p-3">
              <h3 className="text-sm font-semibold text-slate-800">How is the model built?</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                Tract outcomes use a <strong>spatial hierarchical (BYM2-style)</strong> structure with
                queen adjacency for partial pooling across neighbors. MCMC yields posterior summaries
                (mean, SD, exceedance) exported to GeoJSON; the dashboard uses a Normal approximation for
                fast KDE curves.
              </p>
            </section>

            <section className="mt-4 rounded-lg border border-slate-100 bg-slate-50/80 p-3">
              <h3 className="text-sm font-semibold text-slate-800">The density confound</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                In San Diego, <strong>higher median income does not guarantee</strong> high transit
                access: suburban tracts can show high desert probability. That pattern motivates
                borrowing strength across tracts instead of relying on raw deterministic cutoffs alone.
                Use the <strong>Density confound</strong> chart to explore income vs P(desert).
              </p>
            </section>

            <section className="mt-4 rounded-lg border border-slate-100 bg-slate-50/80 p-3">
              <h3 className="text-sm font-semibold text-slate-800">Scenario interventions (A / B)</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                <strong>Scenario A</strong> targets tracts by Bayesian exceedance rank;{" "}
                <strong>Scenario B</strong> uses a deterministic jobs-based rank. Same intervention
                strength, different target lists — compare crossings and population served in the header
                and sidebar.
              </p>
            </section>

            <section className="mt-4 rounded-lg border border-slate-100 bg-slate-50/80 p-3">
              <h3 className="text-sm font-semibold text-slate-800">Glossary</h3>
              <table className="mt-2 w-full text-left text-xs text-slate-600">
                <tbody className="divide-y divide-slate-200">
                  <tr>
                    <th className="py-1.5 pr-2 font-medium text-slate-700">Posterior mean</th>
                    <td className="py-1.5">Expected log₁p(jobs) under the posterior.</td>
                  </tr>
                  <tr>
                    <th className="py-1.5 pr-2 font-medium text-slate-700">95% CI</th>
                    <td className="py-1.5">Approximate credible interval on the log₁p scale.</td>
                  </tr>
                  <tr>
                    <th className="py-1.5 pr-2 font-medium text-slate-700">W₂</th>
                    <td className="py-1.5">Wasserstein distance vs a well-served reference (log₁p scale).</td>
                  </tr>
                  <tr>
                    <th className="py-1.5 pr-2 font-medium text-slate-700">JSD</th>
                    <td className="py-1.5">Jensen–Shannon divergence between Normal surrogates (neighbors).</td>
                  </tr>
                  <tr>
                    <th className="py-1.5 pr-2 font-medium text-slate-700">Q25 threshold</th>
                    <td className="py-1.5">County 25th percentile of accessibility — desert cutoff.</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <p className="mt-4 text-[10px] text-slate-500">
              Keyboard: <kbd className="rounded bg-slate-100 px-1">I</kbd> methodology ·{" "}
              <kbd className="rounded bg-slate-100 px-1">Esc</kbd> close panel or modal
            </p>

            <button
              type="button"
              className="mt-4 w-full rounded-lg bg-slate-800 py-2 text-sm font-medium text-white hover:bg-slate-700"
              onClick={onClose}
            >
              Close
            </button>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
