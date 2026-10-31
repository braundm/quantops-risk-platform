# Equity risk dashboard

The **Analiza ryzyka** workspace focuses on fully funded, long physical equities.
Seven keyboard-accessible tabs expose Overview, Concentration, Diversification,
Possible declines, History, Allocation comparison, and Data/methodology. Numerical
diagnostics are computed in the framework-independent risk engine, not by an LLM
or by a client-side scoring formula. Charts display returned values.

## Reproduce the demonstration

1. Start the API and web application using the repository quickstart.
2. Sign in to the visibly synthetic local `admin1` profile and select **Analiza ryzyka**.
3. Choose **Wczytaj przykład syntetyczny**, then **Oblicz analizę i scenariusze**.
4. Inspect the index and expand its scoring rules. Select a company in Concentration,
   a pair in the correlation matrix, and a scenario in Possible declines.
5. In Allocation comparison, create a copy, enter weights totaling exactly 100%, and
   calculate the comparison. Reports and actual position quantities are unchanged.
6. Export the JSON report to retain the inputs, sources, version and results together.

This five-company demonstration uses invented prices, FX, sectors and identities.
Its source URLs and all metadata are explicitly synthetic. It is not observed market
performance. The original mixed-asset API example remains available for compatibility.

## Explicit analysis scope

The UI sends `scope: securities_only` and `asset_scope: equities_only`. Cash and
non-equity holdings are outside the selected allocation; `out_of_scope` enumerates
omitted instruments next to a prominent subset notice. Their values do not enter
the denominator. Coverage and capital therefore describe the selected equity slice,
not the entire account or the investor's wealth. Unknown/incomplete position states,
physical shorts, missing histories, intervening splits and unsupported listings still
block complete claims. No leverage, execution, brokerage connection or advice is added.

The API defaults to the existing `all_supported` asset scope for older clients and
retains full-account confirmed-cash rules. The equity-only asset scope requires the
explicit securities-only account scope. A mixed allocation or cash-bearing variant
does not receive an equity-only composite score.

## Risk index: 0–100

`equity-diagnostics@1.0.0` provides a **descriptive research heuristic**, not a
calibrated probability, safety rating, suitability decision or capital guarantee.
Higher numbers mean greater measured concentration or historical price risk.

| Component | Weight | 0-point anchor | 100-point anchor |
| --- | --- | --- | --- |
| Largest issuer/listing group weight | 25% | 5% | 50% |
| HHI of issuer/listing group weights | 25% | 0.05 | 0.50 |
| Annualized historical volatility | 25% | 10% | 60% |
| Maximum observed simulated drawdown depth | 25% | 5% | 60% |

Each component is `clip(100 * (value - lower) / (upper - lower), 0, 100)`.
The composite is the weighted sum, rounded to the nearest integer, ties upward.
Bands are 0–24 lower, 25–49 moderate, 50–74 elevated and 75–100 high.
These thresholds and weights are explicit product choices, not empirically calibrated
boundaries or regulatory standards. Concentration intentionally has half the total weight.

A complete score requires at least 252 common valid return observations, finite
volatility/drawdown, a complete eligible allocation and a valuation no more than seven
calendar days old. Explicitly synthetic histories can demonstrate the index with old
dates but retain synthetic labeling. Provider/user histories retain the freshness gate.
An insufficient, stale or mixed allocation returns a typed status and a null score.
Missing evidence never becomes a zero-risk score. The VaR/ES sample gate is separate
and may require more observations, particularly at 99% confidence.

The index omits company fundamentals, default probabilities, liquidity, political risk,
full economic FX exposure and sector dependence. Sector/issuer metadata coverage is
shown separately; unknown classifications are never inferred from company names.

## Concentration and dependence

HHI is the sum of squared group weights; effective holdings are `1 / HHI`.
Documented common `issuer_id` values consolidate share classes/listings. Without an
identity, a listing remains separate, and identity coverage is disclosed. Effective
holdings describe capital distribution and do not count independent risk factors.

Weighted mean correlation excludes diagonal/undefined cells and zero-weight positions.
Each defined pair is weighted by the product of its two portfolio weights. The
diversification ratio is the weighted mean standalone annual volatility divided by
portfolio annual volatility; it is undefined when the denominator is zero. Neither
metric guarantees that historical relationships persist during future market stress.
Signed Euler contributions retain their existing reconciliation and zero-volatility rules.

## Loss scenarios and history

Market presets apply hypothetical equity declines of 10%, 20% and 35% with unchanged FX.
Custom position/class/FX shocks retain existing precedence and multiplicative FX rules.
The single-company table applies a separate 50% decline to each held equity, keeping
other positions and FX unchanged. Rows are independent scenarios with no probability.

Historical curves describe current initial weights followed by buy-and-hold, not actual
transaction-based investor returns. The drawdown chart uses observed common closes and
an expanding previous peak. It does not invent intraday data or fill missing sessions.
Terminal scenario P/L and maximum drawdown are displayed separately. Tolerance messages
explicitly compare terminal loss, not the largest intermediate drawdown.

The report contract is `imported-allocation-risk@1.1.0`. Existing history, covariance,
VaR/ES, Decimal monetary valuation and independent-variant methods remain in
[the imported portfolio methodology](imported-portfolio-risk.md). Verification outcomes
and limitations are recorded in [progress](progress.md).
