# Imported portfolio risk workflow

The existing stock workspace now connects confirmed XTB imports to portfolio risk.
Open `/`, sign in, select an account and choose **Analiza ryzyka**. The importer,
deduplication, account isolation, reference-price mapping and existing investor ledger
are preserved. No broker connectivity, execution, optimization or recommendations are added.

## Reproducible walkthrough

1. Open `http://localhost:5173/`. For loopback development, `admin1` / `admin1` opens
   the existing visibly synthetic account; `admin` / `admin` opens the empty account.
2. Choose **Analiza ryzyka** and choose **Wczytaj przykład syntetyczny**. This loads a
   separate analysis sandbox; it does not replace account reports or transactions.
3. Choose **Oblicz analizę i scenariusze**. Inspect the descriptive 0–100 index,
   concentration, signed risk contributions and common-period correlations in the tabs.
4. Open **Historia** and **Możliwe spadki**. Compare terminal scenario P/L
   with the maximum observed drawdown within the historical window. Set a loss tolerance.
5. Open **Porównaj wariant**, create a copy and enter AAPL.US 30%, MSFT.US 20%, JNJ.US 20%,
   JPM.US 20%, XOM.US 10%. Calculate the comparison. Capital and observation dates
   match; the report book is untouched. Download the JSON report with inputs and results.

For an actual account, import a complete open-position statement or a complete supported
execution ledger. Choose an analysis action; histories are fetched automatically for the
saved holdings. The UI uses an explicit securities-only scope and does not ask for cash.
Account cash is not stored in the report model and is excluded, not guessed from movements.
No investment history is inferred from a current snapshot or closed-only report.

## Supported scope and valuation

The current UI selects the equity-only slice explicitly, enumerating omitted ETF/other
instruments and excluding unknown account cash. Its seven-tab dashboard, concentration
diagnostics and bounded research index are specified in
[Equity risk dashboard](equity-risk-dashboard.md). The API's original default mixed-asset
scope and example remain supported. The following methods describe that broader API.

The analysis supports long physical equities, ETFs and explicitly supplied cash balances.
The UI defaults to the selected account currency and securities-only scope. Full-account API
requests retain the confirmed-cash requirement. A quoted bond ETF is analyzed as an ETF
share using its price history, not as a directly held bond with invented duration.
CFDs, direct bonds, futures, options, unknown listings and physical short positions remain
outside this calculation. Their presence blocks a whole-account risk claim. The existing
Treasury and investor derivative demonstrations retain their separate documented methods.

Money and current valuation use Decimal. Current quantity times the raw close times dated
FX gives base-currency value. Histories use split/dividend-adjusted closes for total returns.
Adjusted prices are never substituted for raw prices in current quantity valuation. Splits
after the quantity snapshot block valuation until a new reconciled position snapshot is
supplied; complete execution-ledger split reconciliation is not fabricated.
Provider requests begin no later than the quantity snapshot or first execution, even
when the selected simulation window starts later. Uploaded histories must also disclose
all intervening split dates; their corporate-action completeness is user supplied.
The separate `quantity_date` is the latest relevant execution or a closing report that
reduces an imported open position, never earlier than the original snapshot. Current
prices must reach that date. Split review still starts at the original snapshot/first
execution so a later transaction cannot hide an earlier unreconciled split.

The current valuation date is the latest common available date in full input histories.
The historical window is filtered separately, so shortening a stress period does not change
current capital. Prices ending before the quantity snapshot cannot establish current value.
In full-account scope, cash balances must match the valuation date. Unknown total value means
value coverage is unknown, not an invented percentage. Securities-only scope excludes account
cash and labels capital and coverage for the analyzed allocation. It still suppresses metrics
when positions or required histories are incomplete, unsupported or older than the quantity state.

## Data and calendar policy

`POST /api/v1/xtb/risk-history` reuses the public Yahoo chart adapter and existing reviewed
broker-symbol mappings. It retains raw and adjusted closes, split dates, source URLs,
snapshot retrieval time, quote currency and base-currency FX. The UK `.L` mapping is added;
provider symbol and currency must match, so GBP/GBp scaling is still not silently assumed.
FX uses USD reference legs for USD, PLN, EUR, GBP and CHF, rounded explicitly to 12 decimal
places. Same-currency FX is exactly one. FX unit exchange rates have no dividends or share
splits; they use raw exchange rates. Missing equity adjusted prices have no raw-price fallback.

Requests cover at most five years, 20 symbols per fetch, 1,300 observations per series and
50 series per analysis. Source failures are instrument-specific and retain previous UI inputs
with dates and failure messages. Fetching fresh current prices still occurs through explicit
user action; this is not a live feed or background market monitor. Histories and drafts remain
in component memory during account navigation, and JSON export permits manual retention.
They are not synchronized or automatically backed up with the imported report registry.

All required position calendars are intersected, with no forward fill. Covariance, correlation,
VaR and ES share one set of base-currency return pairs. A pair spanning a missing observation
in the union calendar or more than four calendar days is excluded from these risk estimators.
The history curve retains actual common observations: changes across gaps are historical
endpoint changes, not fabricated daily returns. Drawdown is measured at observed common closes,
so unobserved sessions and intraday losses can be worse. Matching dates does not imply matching
market closing times. The UI reports common dates, retained return pairs and skipped pairs.

The benchmark uses exactly the portfolio's period and base currency. Incomplete benchmark
history is disclosed without silently shortening the portfolio sample. Provider-origin labels
inside uploaded JSON are declarations, not cryptographic source attestations. Users must review
their files; both client and Pydantic validation reject malformed or contradictory data.

## Concentration, attribution and ETF evidence

Weights include confirmed cash and sum to NAV. The UI shows largest weight, top five, asset
classes, listing currencies, listing countries, issuer countries, sectors and economic currencies.
Listing country is never inferred to be issuer country; listing currency is not claimed to be
the full economic currency exposure. Optional sourced metadata includes an as-of date. A single
economic-currency field is a coarse user-supplied classification, not a multinational revenue model.

Current weights and the sample covariance feed the existing Euler volatility decomposition:
`component_i = weight_i * (covariance * weight)_i / portfolio_volatility`. Components annualize
by sqrt(252), retain negative hedging contributions and reconcile to total volatility. Percentage
contributions are undefined for zero volatility. The engine accepts singular covariance matrices
without adding noise; constant cash correlations are undefined rather than NaN.

ETF composition is optional and never inferred. A supplied composition must cite an HTTPS source,
date and stable issuer IDs with nonnegative weights totaling at most one. The UI reports known
holdings coverage, dates and sources. Pairwise ETF overlap is the sum of minimum known weights
for shared issuer IDs. With partial compositions it is a lower bound. Supplied issuer metadata
also identifies directly held equities included in known ETF holdings. This does not claim
automatic current fund holdings, complete global look-through or independently verified sources.

## History, scenarios and variant comparison

The imported workflow simulates present allocation weights invested at the start of the selected
period, followed by buy-and-hold without rebalancing. Dividends are reinvested once through adjusted
prices. Cash earns no interest; fees, taxes, inflation and transaction costs are excluded. This
is distinct from the existing `/investor` ledger's flow-adjusted end-of-day TWR. That ledger now
also shows drawdown episode dates, peak-to-trough and recovery days, current drawdown and worst
observed month/year from its investment index. First-day fees remain included through an inception
index of one. Unknown initial positions or transactions are never reconstructed.

Drawdown is nonpositive in the curve and maximum depth is nonnegative. Recovery is the first
later observed close reaching the episode's peak. No recovery means the episode remains
unrecovered in supplied history. Calendar returns chain observed returns by ending month/year;
first and last periods are explicitly partial, not full calendar-period results.
Returns crossing an unobserved calendar boundary over a gap longer than seven days
are excluded from monthly/yearly extremes rather than assigned to the ending period.

Historical VaR/ES use a linear empirical quantile at selected 95% or 99% confidence and one
observed-session horizon. At least max(252, ceil(5/(1-confidence))) valid return pairs are required.
ES averages observed losses at or beyond VaR, reports tail count and retains finite-sample status.
VaR is not maximum possible loss. Volatility and contributions from shorter samples remain
explicitly insufficient/unstable evidence. Statistical return calculations use finite floats;
money and scenario revaluation retain Decimal precision.

User scenarios define position, class and FX shocks. Position shock overrides class shock;
they are not added. Price and FX multiply: `new value = old value * (1+price shock)*(1+FX shock)`.
For 400 PLN, price -20% and FX -10% give 288 PLN, a loss of 112 PLN. Cash has FX shocks only;
the base currency cannot be shocked relative to itself. Editable combined examples have no
invented probabilities. Direct-bond rate shocks belong in the separate duration/repricing lab.
Each complete scenario reports P/L, percentage change, terminal value, position contributions,
largest losses and tolerance exceedance. The historical scenario additionally reports the
largest observed drawdown in its window, separately from terminal P/L.

A variant is an independent long-only weight map, with the same capital, common history sample,
confidence, estimator and scenarios. Adding a position requires a reviewed listing and history.
Removing a position or changing cash never edits actual holdings or transactions. Variant weights
must sum exactly to one and are never silently normalized. The initial UI copy rounds weights
to six decimal percentage places, assigns the rounding residual to the largest position and
explicitly describes this presentation rule. Subsequent percentage inputs convert exactly to
Decimal fractions. Before/after risk describes present constant-weight exposures, while the
history curve describes the separately documented buy-and-hold simulation.

## Contracts and checks

### Tabbed equity interface

The normal path selects the saved account, opens the default Overview tab and calculates
the selected equity allocation. Calculation fetches histories for saved physical equities
automatically. Seven tabs separate the overview index, concentration, diversification,
hypothetical declines, simulated history, independent allocation comparison and data/methods.
Changing tabs reuses the result; changing inputs clears it. Chart inspection controls do
not invalidate a calculation. Account/book changes clear histories, drafts and results.

The UI sends both `scope: securities_only` and `asset_scope: equities_only`.
Its separate five-equity synthetic example has no account cash and supplies clearly
synthetic sector/issuer metadata. The original mixed API example remains the default
when the example endpoint is requested without an asset-scope query.

The stress selector supplies hypothetical equity declines of 10%, 20% or 35%, with unchanged
FX. Custom combined shocks remain available. The scenario selector displays one detailed
scenario at a time, including position impacts. Terminal loss tolerance is labeled separately
from intermediate historical drawdown. The independent variant requires exactly 100% weights.

The data tab retains confidence, dates, benchmark, history import/export, provenance and sourced
issuer metadata. Missing evidence suppresses complete scores and identifies required inputs.
The equity risk index's thresholds, weights, eligibility and excluded risks are visible in the UI
and documented in [Equity risk dashboard](equity-risk-dashboard.md).

New routes on the existing XTB boundary are `POST /risk`, `POST /risk-history` and
`GET /risk-example`. They use bounded Pydantic v2 contracts and existing RFC 9457 handlers.
The service-free synthetic example is visibly marked and does not touch reports. JSON reports
include input histories, provenance, balances, scenarios, variant and deterministic results.
Verification commands and observed outcomes are in [progress](progress.md).
