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
            <h2 className="text-lg font-bold text-slate-900">Methodology (short)</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              Tract accessibility is modeled with a BYM2 spatial hierarchy on{" "}
              <strong>log1p(jobs reachable within 45 minutes)</strong>. The map shows{" "}
              <strong>exceedance probability</strong> — the posterior probability that
              accessibility falls below the county Q25 threshold (desert definition).
            </p>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              The <strong>curve panel</strong> uses a Normal approximation N(μ, σ) using
              posterior mean and SD exported from MCMC (well-mixed chains; see paper).
            </p>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              <strong>Scenarios A / B</strong> apply a calibrated parametric shift to
              posterior draws (nb07): same strength, different top-20 target lists
              (Bayesian exceedance rank vs lowest deterministic jobs). GeoJSON stores
              scenario exceedance and Δ.
            </p>
            <button
              type="button"
              className="mt-6 w-full rounded-lg bg-slate-800 py-2 text-sm font-medium text-white hover:bg-slate-700"
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
