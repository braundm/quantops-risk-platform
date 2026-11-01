# Native Monte Carlo portfolio research

QuantOps can simulate a validated imported allocation through an optional C++17
engine. In **Analiza ryzyka**, first calculate a complete allocation, then open
**Możliwe spadki** and use **Uruchom Monte Carlo**. Select horizon, scenario count,
assumed annual drift, and the original or validated alternative allocation.
No accounts, quantities or imported reports change.

## Build and run

From the source checkout, with CMake 3.20+ and a C++17 compiler installed:

~~~text
python scripts/build_monte_carlo.py --test
~~~

The helper discovers the bundled Visual Studio 2022 CMake on Windows when CMake
is absent from PATH. It downloads nothing, builds Release artifacts under
native/monte_carlo/build, and runs CTest with --test. Generated binaries are ignored
by Git. Linux/macOS use the available CMake/compiler toolchain.

Start the normal API and frontend as described in the main README. The API loads
the library only on simulation requests. Ordinary risk analysis needs no C++
toolchain or binary. Missing/incompatible libraries produce HTTP 503, never a
silent Python substitute. Deployment currently requires this source layout and a
native build for the target OS/architecture; binaries are not included in wheels.

## Calculation boundary

POST /api/v1/xtb/monte-carlo takes portfolio (the existing RiskRequest), days,
simulations, seed, annual_drift, and allocation (before/after).
Existing holdings, split, currency, complete-valuation and missing-history checks
run first. Stale provider/user valuations are rejected. Explicit synthetic examples
may retain stale dated valuations and carry a corresponding warning.

The service estimates unbiased sample covariance from log changes of adjusted
prices times dated FX to base currency. It requires at least 252 aligned return
observations, skips pairs separated by a missing union-calendar observation or more
than four calendar days, and never fills prices. Annualization assumes 252 common
trading observations per year; calendar gaps limit this approximation.

C++ factors the annual covariance with a semidefinite-aware Cholesky decomposition.
Zero variance, negative correlations and singular perfect correlations are supported
without invented diagonal jitter. Daily multivariate GBM increments evolve position
values under fixed units (buy-and-hold). The default arithmetic GBM drift is zero;
the historical mean is not presented as a forecast. User drift is an assumption for
non-base-cash factors. Base-currency cash has zero drift and variance.
Foreign-currency cash evolves through embedded base-currency FX history.

A local mt19937_64 stream and explicit Box–Muller normals make identical inputs,
seed and build reproducible. Cross-platform floating-point results may differ
slightly. Different instrument universes do not necessarily use paired common
random shocks even when seeds match.

## Evidence and charts

- Initial NAV, fraction of terminal outcomes below initial NAV, mean terminal NAV.
- Signed terminal-loss VaR: initial NAV minus the linearly interpolated lower
  terminal-value quantile at the requested confidence.
- Expected Shortfall: average loss in exactly the worst 1-confidence fraction of
  empirical probability mass, including a fractional boundary observation.
  Ties do not enlarge the tail. Negative loss values represent gains.
- Pointwise 5th/50th/95th percentiles at up to 53 checkpoints and 12 sampled paths.
  A pointwise 90% interval is not a simultaneous path-containment guarantee.
- Thirty terminal-value histogram bins; counts reconcile to scenario count.
- Calibration period, covariance, symbols, valuation date, currency, scope, seed,
  assumptions, synthetic labels and versioned methodology.

The UI has responsive path/band and histogram views, keyboard-readable checkpoints,
and JSON export of inputs plus results. Monetary outputs use display cents; internal
simulation uses double precision. These are modeled outcomes, not ledger performance.

## Bounds and limitations

The native boundary validates dimensions and finite inputs, long-only exposures,
symmetric positive-semidefinite covariance and output buffer capacity. Limits:
1–20 active positions, 1–1260 sessions, 1000–50000 paths, confidence 0.90–0.99,
and assets² * days * paths at most 1,000,000,000. API drift is bounded to -20%
through +20%; the native boundary has an additional absolute 50% guard.
Excessive workloads return 422 before allocating simulation buffers.

This version assumes constant covariance and Gaussian log returns, without jumps,
volatility regimes, liquidity constraints, taxes, costs, inflation or rebalancing.
Adjusted returns already include dividend reinvestment, which is not added twice.
FX is embedded, not shocked again separately. More paths reduce sampling error,
not model or parameter uncertainty. Frequencies are conditional on assumptions,
not calibrated real-world probabilities. VaR is not a maximum possible loss.

## Verification

CTest compares one-asset VaR/ES and mean with closed-form lognormal references,
and checks seed repeatability, zero volatility, independent diversification and
singular correlation. API tests cover invalid inputs, work limits, missing and
short histories, source freshness, all-cash/mixed variants, reproducibility,
histogram totals and missing-library 503. Native-dependent tests skip explicitly
when the optional binary is absent; release hosts must run build-and-CTest.
Browser tests use the real C++ API on desktop/mobile and check chart switching,
stale-result clearing, account preservation and accessibility.
