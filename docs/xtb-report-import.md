# XTB report-based portfolio workspace

The default `/` and `/stocks` pages add instruments exclusively through user-supplied XTB
CSV, XLSX or ZIP reports. Public catalog search remains a reference browser at `/instruments`.
It does not add portfolio positions. Bossa appears as a clearly unavailable importer.
No authenticated broker connection or order execution is implemented.

## Account and import flow

Register a [local login and password](local-workspace.md), complete or skip the questionnaire,
and select your brokers. Create each XTB account separately
with a display name, broker account number and ISO currency. Multiple accounts in the same
currency are supported. Choose a file or paste CSV, inspect the preview and confirm the import.
Open-position exports require explicit confirmation that they contain the complete snapshot;
purchase/sale ledgers require confirmation of complete history before holdings can be reconstructed.

Up to 50 accounts per profile and 20,000 records per account are supported. Data is stored in
browser local storage under `quantops.xtb-books.v1.<profile UUID>`; quota failures preserve the
previous save. It is local presentation state, not authentication or hosted tenant storage.
Reports are submitted to the application's stateless API for parsing and validation, not to a
broker or price provider. The original report is not retained by this feature. Do not add request
body logging for these routes. JSON backup downloads include sensitive normalized report data.
Existing manual holdings are retained separately and can be downloaded; they are never silently
combined with imported holdings. Cross-tab changes block writes until the page is reloaded.
The workspace separates Overview, Portfolio, Brokers/accounts, Import, History and Settings.
The password gate does not encrypt these local report records or authenticate API ownership.

## Supported semantics

- Closed Positions and Cash Operations are history, not an authoritative current portfolio.
  The owner-supplied ZIP was verified to contain an XLSX workbook with these two sections and
  no Open Positions section. Personal files, account identifiers and financial amounts are not
  checked in. A closed-only import yields `unknown`, rather than an empty portfolio.
- Open Positions supplies a dated full snapshot. A newer full snapshot replaces previous open
  records, including an explicitly empty section. Older snapshots are rejected. Subsequent
  closes with matching position IDs reduce snapshot quantities; new purchases need another report.
- A table with transaction `ID` instead of `Position ID` represents a purchase/sale ledger.
  Unsold stock/ETF buys remain open. Sells reduce units and average cost proportionally;
  oversells reject the whole merge. Equal-time events use deterministic natural numeric ID order.
  A partial ledger remains `incomplete`. Ledgers and open snapshots cannot be mixed.
- Stable event IDs include account, kind, broker ID and closing timestamp. Exact overlapping
  history is deduplicated; conflicting history rejects the merge atomically. Snapshot quantities
  may legitimately change between reports. Re-importing an unchanged report preserves prices.
- CFD BUY/SELL denotes the position direction, never an assumed physical stock execution.
  CFD and unclassified records are retained but not valued by the stock model. Physical and CFD
  quantities sharing a ticker remain separate. Realized P/L and matching Close trade cash entries
  are shown separately; cash movement is explicitly not account balance.

Recognized headers include the supplied XTB English export schema and bounded Polish aliases.
Dates are UTC. Excel serial dates use the 1900 date system; the 1904 system is rejected.
An export's Date to (UTC) takes precedence over a later date entered in the UI. Metadata account
numbers and currencies must match the selected account when present. Currency prefixes in
standard report filenames are also checked. CSV without this metadata requires user verification.
Unsupported schemas fail explicitly; this does not claim every historical/localized XTB format.

## Prices and valuation limits

Reference prices reuse the existing bounded Yahoo Finance daily-close adapter. Only imported
physical holdings identified in the packaged XTB public catalog can request prices. Reviewed
listing suffixes cover US, PL, DE, FR, NL, ES, IT, BE, CH and PT; provider currency and any returned
symbol must match. Unknown listings, CFDs and unsupported quote identifiers fail without invented
prices. GBP/GBX scaling, symbol changes and corporate-action reconciliation need reviewed mappings.

Refresh prices explicitly; optional refresh runs every 15 minutes while the page is visible.
This is a daily-close reference, not live pricing or background monitoring. A refresh currently
supports up to 20 unique physical instruments; larger portfolios need a bounded quote queue.
Provider outages retain existing prices and dates. Valuation uses Decimal quantities and prices,
separate native-currency totals and version `imported-spot@1.0.0`. Splits suppress cost/P&L
comparison pending review. Missing coverage remains partial; fees, dividends, FX effects, CFD
financing/multipliers and option Greeks are outside this calculation. Imported values are
user-supplied snapshots, not server-attested broker balances.

## Parser boundaries and verification

Files are limited to 8 MiB, expanded archives to 32 MiB and 512 members. Archives are read in
memory without filesystem extraction. Unsafe paths, encryption, duplicate members, formulas,
DTDs/entities, non-finite numbers and excessive rows/cells are rejected. CSV accepts UTF-8,
UTF-16 and CP1250, with comma, semicolon or tab delimiters. XLSX parsing reads sheet rows directly,
because real exports can carry incorrect A1-only dimensions. No Excel or live service is required.

Synthetic tests cover missing open sections, account isolation, deduplication, conflicts, full
and empty snapshot replacement, partial sales, oversells, unsafe files, splits, CFD separation,
provider failures, reload and desktop/mobile accessibility. See `docs/progress.md` for outcomes.

Brand assets come from the official [XTB SVG](https://xas-cdn.xtb.com/build/twigImages/svg-icons/logo/logo_xtb.svg)
and [Bossa SVG](https://bossa.pl/themes/custom/b30_theme/logo.svg). Their trademarks identify the
report source and do not imply affiliation.

## Next work

The [imported portfolio risk workflow](imported-portfolio-risk.md) now connects this
importer to adjusted price/FX history, concentration, signed volatility attribution,
VaR/ES, historical and hypothetical scenarios and independent allocation comparisons.
Its whole-account gates require supported holdings, dated data and confirmed cash.

1. Reconcile full open positions, cash balances, transfers, fees, dividends and corporate actions;
   add encrypted durable storage, access control and a tested backup restore flow.
2. Extend the implemented price/FX history adapter beyond its 20-symbol fetch limit and
   add independently verified ETF holdings and richer economic exposure metadata. Keep
   incomplete data visibly separate from a complete portfolio analysis.
3. Add CFD contract multipliers, financing, margin and stress calculations, then Bossa report
   adapters using verified samples. Options require contract identity, expiry, strike, multipliers
   and appropriate market data before Greeks can be calculated.
