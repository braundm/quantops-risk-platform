# Risk methodology

Methodology version: `1.0.0`; risk-engine package version: `0.1.0`.

QuantOps calculations describe historical or hypothetical market risk. They are not forecasts, maximum-loss guarantees, investment advice, or order instructions. Identical ordered inputs produce identical results. Money and scenario revaluation use `Decimal`; statistical estimators use finite binary floating point and reject `NaN`/infinity.

## Returns and alignment

For adjacent positive closing prices, arithmetic and log returns are:

\[
r_t = \frac{P_t}{P_{t-1}} - 1, \qquad
g_t = \log\left(\frac{P_t}{P_{t-1}}\right).
\]

The authoritative risk path uses close-to-close arithmetic returns. A missing observation removes every adjacent pair touching that gap; the engine never forward-fills or bridges across it. Multi-asset series use an explicit intersection or strict-union calendar policy.

## Point-in-time valuation

For quantity \(q_i\), price \(P_i\), and explicit conversion \(f_i\) in base-currency units per price-currency unit:

\[
V_i = q_i P_i f_i, \qquad V = \sum_i V_i.
\]

All three monetary operands are `Decimal`. Cross-currency positions require a positive FX rate. The required synthetic portfolio is USD-only, so its rate is exactly one. When cost \(C_i\) is available, unrealized P&L is \(q_i(P_i-C_i)f_i\). Position and portfolio totals reconcile within an explicit decimal tolerance.

## Volatility and covariance

Sample volatility uses denominator \(n-1\) and annualizes as:

\[
\sigma_{annual} = \sigma_{sample}\sqrt{N},
\]

where \(N\) defaults to 252 and is included in output metadata. Fewer than two observations return `insufficient_data`, not a misleading number. Covariance uses a multivariate Welford update. Singular positive-semidefinite covariance is accepted because no inverse is required; materially non-positive-semidefinite input is rejected.

## Historical VaR and Expected Shortfall

QuantOps uses a nonnegative-amount-is-loss convention. For portfolio value \(V\) and arithmetic return \(r_t\), observed loss is \(L_t=-Vr_t\). Historical VaR at confidence \(c\) is the empirical \(c\)-quantile of losses, floored at zero when the selected quantile is a gain. Default interpolation is linear with index \((n-1)c\); lower, higher, nearest, and midpoint rules are also explicit options.

Historical Expected Shortfall is the unweighted mean of observed losses at or above the VaR threshold. A single tail observation is returned as `unstable`. When all observations are gains, VaR and ES are zero and ES is also marked `unstable`. Under this convention, a defined ES is never less severe than VaR.

Worked example: returns `[-0.10, -0.05, 0, 0.05, 0.10]`, value `100`, confidence `0.80`. Sorted losses are `[-10, -5, 0, 5, 10]`; linear quantile index `3.2` gives VaR `6`. The only observed loss at or above `6` is `10`, so ES is `10` with unstable finite-sample status.

## Parametric VaR and Expected Shortfall

For monetary exposures \(x\), return covariance \(\Sigma\), mean returns \(\mu\), horizon \(h\), normal quantile \(z_c\), and density \(\phi\):

\[
\sigma_P = \sqrt{h x^T\Sigma x},
\]

\[
\operatorname{VaR}_c = \max(0, -h x^T\mu + z_c\sigma_P),
\]

\[
\operatorname{ES}_c = \max\left(\operatorname{VaR}_c,
-h x^T\mu + \sigma_P\frac{\phi(z_c)}{1-c}\right).
\]

The default mean is zero. These estimates assume linear exposures, multivariate-normal returns, stable covariance, and square-root-of-time scaling—assumptions that commonly deteriorate during stress and are surfaced with every result.

## Drawdown, correlation, and concentration

Signed drawdown is \(D_t=V_t/\max_{s\leq t}V_s-1\). Output includes the nonnegative maximum depth, episode peak, first deepest trough, and first recovery at or above the episode peak, if present.

Correlation uses pairwise-complete observations and returns overlap counts. Constant or insufficient series produce `None`, never `NaN`; small overlaps are marked unstable. Concentration uses gross absolute exposure weights:

\[
w_i=\frac{|x_i|}{\sum_j |x_j|}, \qquad HHI=\sum_i w_i^2,
\qquad N_{effective}=\frac{1}{HHI}.
\]

This prevents offsetting long and short positions from creating a misleadingly small denominator.

## Volatility contributions

For \(\sigma_P=\sqrt{x^T\Sigma x}\):

\[
MC_i=\frac{(\Sigma x)_i}{\sigma_P}, \qquad CC_i=x_iMC_i.
\]

Euler homogeneity gives \(\sum_i CC_i=\sigma_P\). The engine reports the reconciliation difference and tolerance result. Negative diversifying contributions remain negative and are never clipped.

## Deterministic scenarios

Frozen versioned definitions support instrument-price, asset-class, FX, volatility-multiplier, correlation-override, and combined shocks. Price/FX shocks compound in canonical order. Volatility and correlation changes are analytical comparison outputs and do not fabricate a P&L path. Scenario execution never mutates positions or source prices; each result has a content-derived SHA-256 run ID and is labelled hypothetical.

Built-ins are `equity_selloff_15pct`, `oil_spike_25pct`, `gold_down_10pct`, `cross_asset_correlation_breakdown`, and `combined_liquidity_stress`.

## VaR exception backtesting

A one-day exception occurs when realized loss is strictly greater than the prior forecast. Rolling forecasts use only the trailing window and exclude the realized day. The Kupiec proportion-of-failures statistic tests unconditional exception coverage. Results under 250 observations default to `unstable`; the test has low power in small samples and does not test exception independence, model correctness, data revisions, or tail severity.

## Status, versioning, and evidence

Invalid, non-finite, ambiguous, or contradictory input raises a typed `RiskEngineError`. Mathematically valid calculations without enough observations return `insufficient_data` with no numerical value. Evidence identity is built separately from numerical functions using deterministic canonical payload hashes. Any formula or global convention change requires a methodology semantic-version change and updated worked examples/tests.

The independently installable package also carries its scoped methodology at `packages/risk_engine/docs/risk-methodology.md` so the documentation is present in package artifacts.
