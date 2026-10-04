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
stored portfolio and current positions. The stateless API never stores portfolios or user prices.
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
comparisons; entry/holding estimates; before/after valuation; report export; Polish responsive UI.

Synthetic: demonstration symbols, positions, prices, FX and the pre-existing research risk dataset.
Demo dates are intentionally fixed. Data older than 24 hours triggers visible price/FX warnings.
Mixing user and synthetic inputs is explicitly labelled; editing fictional holdings retains their
synthetic origin. Rates copied from the demo retain synthetic provenance.

Deferred: onboarding survey; historical prices and transaction/flow import for a user's portfolio;
historical VaR/ES, volatility, drawdown and correlation in the personal workspace; saved scenario
library; a complete portfolio cost ledger; constrained allocation optimization; educational
prediction/calibration experiment; derivative valuation; tenant authentication and PostgreSQL
persistence; read-only MT5/Bossa adapters. No live integration or entire retail MVP completion is
claimed. Existing risk-core historical calculations remain available and independently tested.

Broker-specific adapters require separate documented implementation. MT5 requires a local terminal
bridge; Bossa access and data-display conditions must be verified before implementation. Neither
is connected, and this slice adds no brokerage SDK, credentials or order submission.
