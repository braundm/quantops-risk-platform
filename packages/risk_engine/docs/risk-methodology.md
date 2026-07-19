# QuantOps risk methodology 1.0.0

This document describes package version `0.1.0` and methodology semantic version
`1.0.0`. Results are deterministic for identical ordered numerical inputs. Statistical
results use binary floating point; money and scenario revaluation use `Decimal` without
automatic rounding. Callers own display and settlement-currency rounding.

These methods describe hypothetical or historical market risk. They are not forecasts,
maximum-loss guarantees, or investment advice.

## Returns and calendars

Prices are adjacent close-to-close observations. Arithmetic return is

\[
r_t = P_t/P_{t-1}-1,
\]

and log return is

\[
g_t = \log(P_t/P_{t-1}).
\]

Prices must be finite and strictly positive. Missing values either raise a typed error
or drop every adjacent pair touching the missing value. The engine never bridges such a
gap and never forward-fills. Multi-asset input must choose an explicit intersection or
strict-union calendar. Dates are labels and no business calendar is guessed.

## Point-in-time valuation

For position quantity \(q_i\), price \(P_i\), and explicit base-currency conversion
rate \(f_i\) (base currency per price-currency unit), market value is

\[
V_i = q_i P_i f_i, \qquad V = \sum_i V_i.
\]

All operands must be `Decimal`. Cross-currency positions require a positive FX rate;
same-currency positions use exactly one. Every portfolio must share one base currency.
Unrealized P&L, when cost basis is supplied, is \(q_i(P_i-C_i)f_i\). Short positions
therefore have signed market value and P&L.

## Volatility and covariance

Sample variance uses denominator \(n-1\); fewer than two returns produce the typed
`insufficient_data` status rather than NaN. Annualized volatility is

\[
\sigma_{ann} = \sigma_{sample}\sqrt{N},
\]

where `periods_per_year` defaults to 252 and is always exposed. Rolling windows are
complete trailing windows only. Multivariate sample covariance uses an online Welford
update. Singular positive-semidefinite covariance matrices are accepted because
portfolio variance \(x^T\Sigma x\) requires no matrix inverse. Materially negative
variance is rejected; round-off-sized negative values are set to zero.

## Historical VaR and Expected Shortfall

All tail measures use a **nonnegative amount is loss** convention. Given arithmetic
portfolio return \(r_t\) and current value \(V\), observed loss is \(L_t=-Vr_t\).
Historical VaR at confidence \(c\) is the empirical \(c\)-quantile of losses, floored
at zero if that quantile is a gain. Linear interpolation is the default; lower, higher,
nearest, and midpoint are available. Interpolation uses index \((n-1)c\).

Historical Expected Shortfall is the unweighted mean of observed losses greater than
or equal to the interpolated VaR threshold. The inclusive boundary is intentional and
visible in assumptions. One tail observation is a defined estimate but has `unstable`
status. When all observations are gains and VaR is floored to zero, ES is zero with
`unstable` status. With this convention, defined ES is never below VaR.

Worked example: returns `[-0.10, -0.05, 0, 0.05, 0.10]`, current value 100, confidence
0.80, linear interpolation. Losses are `[10, 5, 0, -5, -10]`; sorted losses are
`[-10, -5, 0, 5, 10]`. The quantile index is 3.2, so VaR is 6. The only observed loss
at or above 6 is 10, so ES is 10 and is flagged unstable.

## Parametric VaR and Expected Shortfall

For base-currency exposures \(x\), return covariance \(\Sigma\), expected asset returns
\(\mu\), horizon \(h\), and standard-normal quantile \(z_c\):

\[
\sigma_P = \sqrt{h x^T\Sigma x},\qquad
\operatorname{VaR}_c = \max(0,-h x^T\mu + z_c\sigma_P).
\]

Normal Expected Shortfall is

\[
\operatorname{ES}_c = \max(\operatorname{VaR}_c,
-h x^T\mu + \sigma_P\phi(z_c)/(1-c)).
\]

The default mean is zero. These formulas assume linear exposures, multivariate normal
returns, stable covariance, and square-root-of-time scaling. Those assumptions commonly
fail during stress. No covariance inversion or regularization is performed.

## Drawdown

At each point the conventional signed series is \(D_t=V_t/\max_{s\le t}V_s-1\).
Reported maximum drawdown is the nonnegative depth `-min(D)`. The engine reports the
running-peak date for the deepest episode, its first deepest trough, and the first later
value that reaches or exceeds that episode peak. Recovery is `None` if absent.

## Correlation and concentration

Correlation uses pairwise-complete observations and supplies a full overlap-count
matrix. Fewer than two observations or a constant series produces `None`, never NaN.
Defined pairs below the configured overlap warning threshold have `unstable` status.
Historical correlation is descriptive, regime-dependent, and especially unstable in
small or stressed samples.

Concentration uses gross absolute exposures. If \(w_i=|x_i|/\sum_j|x_j|\), then

\[
HHI = \sum_i w_i^2, \qquad N_{effective}=1/HHI.
\]

This avoids netting a long and short exposure into a misleadingly small denominator.
A zero-gross portfolio has insufficient status.

## Volatility contribution

For \(\sigma_P=\sqrt{x^T\Sigma x}\), marginal and component contributions are

\[
MC_i=(\Sigma x)_i/\sigma_P,\qquad
CC_i=x_iMC_i.
\]

Euler homogeneity gives \(\sum_i CC_i=\sigma_P\). The output includes the numerical
reconciliation difference and flag. Negative components are valid diversifying
contributions and are never clipped.

## Scenarios

Scenario definitions, positions, shocks, and results are frozen typed objects. Price,
asset-class, FX, volatility, and correlation changes are applied in a documented
canonical phase order. Price and FX changes compound. Correlation overrides and
volatility multipliers are analytical comparison outputs; they do not fabricate a
revaluation path. Runs contain a content-derived SHA-256 identifier, are deterministic,
do not mutate positions, and are always labelled hypothetical. The versioned built-ins
are `equity_selloff_15pct`, `oil_spike_25pct`, `gold_down_10pct`,
`cross_asset_correlation_breakdown`, and `combined_liquidity_stress`.

## VaR exception backtesting

A one-day exception occurs only when realized loss is strictly greater than the VaR
forecast made from prior observations. The rolling historical helper never includes the
realized day in its forecast window. For \(x\) exceptions in \(n\) forecasts and expected
rate \(p=1-c\), the Kupiec statistic compares Bernoulli likelihood at \(p\) with the
unrestricted rate \(x/n\). Its p-value uses the chi-square distribution with one degree
of freedom.

The output is `unstable` below 250 observations by default. Kupiec has low power in small
samples and tests unconditional coverage only—not exception independence, model
correctness, revised-data leakage, or tail severity. Regime labels are carried as
evidence labels and do not affect calculations.

## Invalid and insufficient input

Malformed, non-finite, ambiguous, or contradictory input raises a subclass of
`RiskEngineError`. A mathematically valid calculation lacking observations returns an
immutable result with `insufficient_data` and `None` value; calling `require_value()`
converts that state into typed `InsufficientDataError`. Undefined correlation cells use
`None`. Public numerical paths never intentionally propagate NaN.

## Evidence and versioning

Every externally meaningful result embeds methodology `1.0.0`. Evidence payloads and
calculation parameters are hashed by a separate deterministic builder, keeping identity
and I/O concerns outside pure numerical functions. Changing a formula or global
convention requires a methodology semantic-version change and updated worked examples.
