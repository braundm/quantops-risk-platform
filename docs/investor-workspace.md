# Investor workspace: prices, ownership and calculations

The default `/` and `/investor` routes are a Polish, browser-local portfolio workspace. The older
workshop is retained at `/personal` and the synthetic research application at `/research`.
The API is stateless: browser storage and downloaded JSON backups provide persistence, not hosted
accounts or database-backed user identity. All analysis runs through deterministic Python code.

## Market data and fictional ownership

The bundled snapshot was fetched on 2026-10-04 from Yahoo Finance's public chart endpoint. Its
common valuation date is 2026-10-01. It includes unadjusted daily closes for AAPL, MSFT, SPY, TLT,
EURUSD=X, CLZ26.NYM and PLN=X (PLN per USD). Exact retrieval timestamps and per-series source URLs
are embedded in the snapshot and shown in Data and Settings. These are historical reference
closes, not executable quotes or a live price feed.

The example deposit, purchase dates, quantities and fees are fictional. Each transaction keeps
its synthetic/user origin independently of price provenance. Editing or importing a mixed book
does not hide synthetic entries. A changed external snapshot loses the trusted-provider label
unless its validated fingerprint matches the bundled or recently fetched provider payload.

The fixed catalog is deliberately limited to six instruments. CLZ26.NYM is the December 2026
standard WTI contract, with 1,000 barrels per contract, not a micro contract. Its configured final
trading date is 2026-11-20; analysis rejects open positions on or after expiry. See the
[CME contract specifications](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html).
The model excludes physical delivery and automatic rolling. The EUR/USD position is a modeled
long/short exposure in base-currency units, not a broker account.

An explicit refresh fetches only allowlisted symbols and fails atomically. Offline tests use the
checked-in snapshot; no external provider or broker credentials are required. A new snapshot
with splits is rejected instead of silently changing share quantities or treating split jumps as
investment performance. The loader requires sufficient finite observations and unique dates.
Refresh does not invent prices when a provider fails. Refreshing beyond the modeled contract's
expiry requires closing that position or extending the supported catalog in a separate change.

## Ledger and performance

The ledger accepts buys, sells, deposits, withdrawals, dividends and fees. UUIDs enforce unique
entries. Decimal values preserve money and quantity precision. Dates must exist in the aligned
price/FX calendar; missing data is not interpolated. Entries are processed in input order within
each date. CSV preview is separate from confirmation; the combined ledger is validated before
replacing the last valid local save. Re-imported UUIDs are rejected.

CSV columns, in order:

```text
id,date,action,symbol,quantity,price,amount_pln,fee_pln,source
```

Use ISO dates, decimal points, `buy|sell|deposit|withdrawal|dividend|fee`, and `synthetic|user`.
Trade quantity and price are in the instrument's units and USD; cash flows and fees are PLN.
Cash entries have zero quantity and price. Trade amount_pln is zero because consideration is
derived from quantity, price and dated FX. Dividend entries require an existing long position.
The export button provides a complete importable example with UUIDs.

Spot trades exchange cash for assets. Weighted-average entry cost is reduced proportionally on
partial sale, and realized P&L includes dated PLN acquisition cost. Derivatives do not add their
whole notional to portfolio equity: their unrealized P&L is quantity times contract multiplier
times price change, converted at dated FX. Closing a derivative realizes its P&L once; reversing
direction opens the remainder at the new entry price. Whole contracts are required for futures.

Equity equals cash plus spot market values plus unrealized derivative P&L. Profit equals equity
minus net external deposits. Fees are deducted once and explicit dividends add cash. TWR chains
daily flow-adjusted returns using end-of-day external flows; it is not a money-weighted IRR.
Nonpositive equity invalidates precise TWR and maximum drawdown. Negative cash and insufficient
cash for the modeled margin reserve produce visible warnings.

The futures and FX model marks cumulative unrealized P&L, without actual daily variation-margin
cash settlement, funding, swaps, taxes, slippage or delivery. Assumed margin (10% WTI, 5% FX) is
shown separately from equity; it is not an exchange or broker margin requirement. Dividends,
financing and costs are not automatically inferred from market prices.

## Charts and risk interpretation

- History switches between equity, profit after flows and TWR. A keyboard slider exposes dates
  and values, and the chart can be downloaded as SVG. Instrument detail includes ownership date,
  days held, entry price, reference price and position P&L.
- Diversification uses absolute gross nominal exposure, including derivative multipliers, rather
  than invested cash or margin. It reports largest weight and effective position count (1/HHI).
  Sector grouping is coarse and does not look through ETF holdings; ETF overlap remains visible
  as a limitation. This is not a complete measure of diversification.
- Correlations and risk contributions describe aligned historical daily position P&L at current
  quantities. Signed covariance contributions may be negative or exceed 100%; they sum to one
  when portfolio variance is positive. They are not causal attributions of realized ledger profit.
- One-day historical VaR and ES use 252 aligned returns at 95% confidence. Fewer observations or
  invalid equity suppress precise risk metrics. Annualized volatility uses a square-root-of-252
  convention. Historical losses are observations, not guaranteed future limits.
- The return/volatility scatter compares the most recent aligned price history (up to 252
  returns, minimum 60). Stocks/ETFs use PLN price changes; FX/futures use quoted USD price changes,
  explicitly labeled. It does not represent leveraged investor returns or an optimal frontier.
  Less volatility is not a guarantee of safety.
- Saved stress scenarios combine equity/ETF, USD/PLN, oil and EUR/USD shocks. PLN cash remains
  unchanged; position-level changes reconcile to shocked equity. No scenario is a forecast.

Markets close at different times, and matching dates does not establish simultaneous quotes.
The UI exposes these assumptions instead of combining all risks into a misleading safety score.

## Storage and backup

Successful analysis saves the book, prices and named scenarios under
`quantops.investor-workspace.v1`. Cash budget and concentration limit use separate browser keys.
JSON backup includes all three. Restore validates the book through the API and checks budget and
limit structure. If storage is unavailable, the UI offers a downloadable copy and displays an
error. Clearing this workspace removes its three keys; the older personal workshop has separate
storage. The next empty visit loads a clearly fictional example, not deleted user ownership.

The cash envelope budget is an independent planning worksheet. Importing portfolio cash does not
create a ledger deposit, and changing envelopes does not change investment P&L. Synthetic learning
exercises are separate from sourced market history and never supply trading recommendations.
