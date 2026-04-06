# nb04 MCMC — automated recommendations
- max R-hat (tracked parameters): 1.0874 (target <= 1.01)
- min bulk ESS: 36.2 (target >= 400 rule-of-thumb)
- parameters with R-hat > 1.01: 8
- parameters with bulk ESS < 400: 8

If fixed effects (alpha, beta) fail thresholds while sigma/rho pass:
  - Increase `model.draws` (e.g. 4000–8000) and/or `model.tune`.
  - Slightly increase `model.fixed_obs_sigma` (e.g. 0.06–0.10) as a sensitivity run.
  - Try `model.likelihood: student_t` for robustness (same obs_noise mode).
