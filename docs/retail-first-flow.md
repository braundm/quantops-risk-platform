# Retail portfolio and FX sensitivity

The Polish personal workspace at `/` is a working vertical slice backed by the existing
FastAPI and pure Python risk engine. The existing research application remains at `/research`
and its previous dashboard, methodology and evidence routes. No broker connection is required.

## Run locally

From the repository root, use two terminals after the normal workspace setup:

```powershell
.venv\Scripts\python.exe -m uvicorn quantops_api.main:app --host 127.0.0.1 --port 8000
```

```powershell
pnpm --filter @quantops/web dev --host 127.0.0.1
```

Open `http://localhost:5173/`. Vite proxies `/api` to the loopback API. Docker, a database,
live prices, external LLMs and broker credentials are unnecessary. A deployment serving the
production build must provide an equivalent same-origin `/api` reverse proxy; Vite's development
proxy does not become part of the static production bundle. This workspace is intended for
local use; it does not add hosted authentication or a multi-user persistence service.

## Exercise the flow

1. Open the synthetic demo. It contains fictional instruments and explicitly dated example FX.
2. Inspect signed net value, cash, gross and net security exposure, quotation currencies and
   concentration. Cash is entered once; short quantities and cash liabilities are negative.
3. Set a currency shock, optionally combine it with a common security price shock, and recalculate.
4. Compare no hedge, a selected partial hedge and a full initial-notional hedge. Inspect direction,
   both notionals, initial remaining exposure, terminal payoff and separate entry/holding estimates.
5. Save a comparison point, change quantities or prices and recalculate to compare valuation and
   concentration. This does not represent investor performance or an allocation recommendation.
6. Export the UTF-8 text report with inputs, position impacts, model version, timestamp, scenario ID,
   costs and limitations. The scenario ID identifies the underlying scenario only; the report's
   full request contains the separate forward and cost assumptions.

Any portfolio or scenario input change invalidates displayed results and disables report export
until successful recalculation. Older asynchronous responses cannot replace a newer calculation.

## Current-position CSV

Use `data/retail-synthetic-positions.csv` or the in-app example download. Required columns, in order:

```text
account,symbol,asset_class,currency,quantity,price,multiplier,as_of,source
```

Mapping: account identifier; symbol; `equity`, `etf` or `cash`; ISO currency; signed quantity;
unit price; multiplier (must be 1 for this spot slice); timezone-aware ISO timestamp;
`user` or `synthetic` provenance. Decimal separator is a period; field separator is a comma.
Keep `synthetic` for fictional examples, including modified fictional positions. Unknown symbols
are user declarations, not exchange-catalog verified instruments. Options, CFDs and other
derivatives are rejected, rather than approximated using a linear spot valuation.

Preview validates every row, rejects duplicate account/symbol/currency identities, zero quantities,
non-finite numbers, non-ISO currencies, malformed timestamps, future prices and unsupported
multipliers. It accepts at most 200 positions and 200,000 text characters. The browser additionally
limits file size to 200 kB. Missing FX must be supplied before confirmation. No import is committed
with any row errors; confirmation explicitly replaces current positions. This does not import
transaction history or reconstruct historical investor returns.

New empty portfolios require user-entered FX instead of inheriting demo rates. Local saves are
explicit, unsencrypted browser storage under `quantops.local-portfolio.v1`, not accounts in a
database. Restore validates the saved portfolio through the API. The delete action removes the
stored portfolio, current positions and the new history, cost, survey and exercise session state.
The stateless API never stores portfolios or user prices.
Separate clients do not share portfolio state. Do not use local storage on a shared workstation
for sensitive account information. Existing research-demo APIs are separate.

## Calculation model

All authoritative values come from Python with Decimal amounts. Existing `value_position` and
`run_scenario` calculate valuation and sensitivity. Price and FX shocks compound:

```text
stressed value = quantity * price * FX * (1 + price shock) * (1 + FX shock)
```

Cash has no price shock. FX shocks apply only to the selected quotation currency. Concentration
is largest absolute security value / total absolute security values; cash is excluded. Gross and
net security exposures exclude cash, while net portfolio value includes signed cash and liabilities.
Gross/equity and impact/equity are unavailable for nonpositive equity. None is a universal risk score.

The pure forward model in `quantops_risk.hedging` uses simple ACT/365 carry:

```text
F = S * (1 + base rate * days/365) / (1 + foreign rate * days/365)
N = signed initial foreign exposure * hedge ratio
payoff = N * (F - terminal spot)
entry estimate = abs(N*S) * entry basis points / 10000
holding estimate = abs(N*S) * annual holding basis points / 10000 * days/365
```

Positive exposure sells foreign currency forward; negative exposure buys. Zero hedge has zero
payoff and costs. Terminal portfolio impact is unhedged scenario impact + payoff - both cost
estimates. Results are undiscounted terminal sensitivities, not an executed forward or broker quote.
Forward carry is embedded in F; the holding-cost input is an additional estimate and should exclude
that carry to avoid double counting. Initial-notional full hedges can become oversized after an
asset-price decline; the comparison flags this. An unchanged FX exposure is assumed through the
selected maturity; intervening withdrawals, exposure changes or instrument maturities invalidate
that match. The model excludes interim collateral, liquidity, counterparty, basis and settlement
risk. A forward, leveraged FX/CFD position and currency ETF are not equivalent products.

## Actual, synthetic and deferred capabilities

Actual: manual portfolios; strict preview/confirm CSV; local save/restore/delete; Decimal valuation;
signed exposures and concentration; combined hypothetical price/FX scenarios; terminal forward
comparisons; entry/holding estimates; before/after valuation; report export; Polish responsive UI;
aligned historical risk, interactive charts, a cost budget and optional goals/limits survey.

Synthetic: demonstration symbols, positions, prices, FX, history, educational exercise paths and
the pre-existing research risk dataset.
Demo dates are intentionally fixed. Data older than 24 hours triggers visible price/FX warnings.
Mixing user and synthetic inputs is explicitly labelled; editing fictional holdings retains their
synthetic origin. Rates copied from the demo retain synthetic provenance.

Deferred: transaction/flow import and investor performance reconstruction; saved scenario
library; a complete transaction-linked cost ledger; constrained allocation optimization;
market-data validation of educational exercises; derivative valuation; tenant authentication and PostgreSQL
persistence; read-only MT5/Bossa adapters. No live integration or entire retail MVP completion is
claimed. Existing risk-core historical calculations remain available and independently tested.

Broker-specific adapters require separate documented implementation. MT5 requires a local terminal
bridge; Bossa access and data-display conditions must be verified before implementation. Neither
is connected, and this slice adds no brokerage SDK, credentials or order submission.

## Historical risk and charts

The history CSV columns are `date,symbol,price,fx_to_base,source`. Preview and explicit confirmation
validate at most 20,000 rows / 1.5 MB. Every non-base-cash holding requires identical observation
dates, including foreign cash (price 1). Same-currency rows must use the same dated FX, base FX
must equal 1, and duplicate date/symbol pairs or ambiguous symbol/currency mappings are rejected.
There is no gap filling. Each date reprices the current fixed quantities using dated prices and FX;
base-currency cash remains constant. This is not the investor's realized performance.

The existing pure risk core computes empirical VaR, ES, sample volatility, drawdown and correlations.
At least 252 returns and enough observations to expect five tail observations are required (500
returns at 99% confidence). Insufficient samples suppress numeric risk metrics. VaR/ES fractions
are applied to positive current net equity for monetary amounts. The horizon is one observation;
calendar gaps are flagged, volatility is not annualized, and VaR is not a maximum loss.
Prices must be reviewed for corporate actions; dividends, taxes, flows and transaction costs are
not reconstructed. The 340-date example is fixed and visibly synthetic. Chart readouts are
keyboard-accessible; changing portfolio inputs or confidence invalidates previous risk results.

## Costs, preferences and education

The separate cost budget accepts actual, estimated or user-entered monetary fees. One-time fees
and annual recurring fees are separate; monthly amounts multiply by 12. Fees marked included in
prices are excluded, preventing double counting. This budget is not automatically deducted from
price history or the forward model. Changing base currency clears the budget.

The optional survey distinguishes willingness to take losses from financial capacity, checks
percentage/amount consistency and liquidity needs, and applies a user-selected concentration
threshold. It does not determine product suitability or provide investment recommendations.
Survey and cost state remain in memory for the session; only the current portfolio has an explicit
local save action. Export includes completed risk/cost/survey results alongside scenario inputs.

The education exercise uses four server-side deterministic synthetic paths. The browser sees 40
observations initially; each decision reveals five more, for ten trials. An HMAC-signed cursor binds
the exercise and cumulative statistics, expiring after one hour or API restart. This local prototype
uses one API process: multiple workers would need a shared cursor key. Cursors can be replayed and
paths revisited, so this is an educational demonstration, not a tamper-proof strategy evaluation.
Directional returns, costs, an always-up benchmark and Brier calibration are computed by Python.
Each trial uses an equal independent nominal; sums are not compounded strategy returns. Skips
have zero return and cost and do not enter directional accuracy or calibration. The benchmark
trades each trial and incurs its entered cost. No market edge can be inferred from ten synthetic trials.
