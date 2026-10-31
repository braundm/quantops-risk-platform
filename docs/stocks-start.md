# Stock-only personal start

> Superseded UI: the default workspace now uses [XTB report import](xtb-report-import.md).
> The manual flow below documents the earlier implementation and retained legacy API/data.

The default `/` and `/stocks` routes implement a portfolio-tracking start: create a local user,
complete a risk/knowledge questionnaire, then add existing stock holdings to an empty portfolio.
The flow is inspired by the portfolio organization of [myfund.pl](https://myfund.pl/).
The prior investor ledger remains at `/investor`; the personal workshop remains at `/personal`.
Their existing data is not automatically imported into the new user profiles.

## Local users and questionnaire

Up to ten UUID-identified users have separate browser-local profiles and holdings under
`quantops.stock-users.v1`. Switching users preserves their data; deleting a user removes only
that user's questionnaire and positions. There are no hosted accounts, passwords or durable
tenant storage. Users of the same browser can access these local profiles. Invalid stored data
is not silently replaced: the UI provides download and explicit clearing.

The questionnaire covers purpose, horizon, willingness and capacity to lose a percentage of
invested capital, liquidity needs, and familiarity with stocks, bonds, ETFs, options and futures.
It also asks about losses, diversification and leverage. Deterministic rules choose introductory,
standard or detailed explanations and flag willingness exceeding capacity or short horizons.
All profiles receive the same stock catalog. This is educational feature tailoring, not product
suitability assessment, asset selection or buy/sell recommendations.

## Catalog and market lookup

The fixed catalog contains 20 US equities and 20 large Warsaw-listed equities from the WIG20
universe. The Polish catalog uses PKO, ORLEN, KGHM, Pekao, Allegro, PZU, Erste Bank Polska, LPP,
mBank, Dino, CD Projekt, Żabka, PGE, Alior, Kęty, Tauron, Budimex, Pepco, Kruk and Modivo.
Ticker mappings include EBP.WA and MDV.WA. The catalog does not automatically track index changes
and is not an assertion of future or continuously synchronized WIG20 membership.
See [GPW Benchmark's index description](https://gpwbenchmark.pl/karta-indeksu?isin=PL9999999987)
and the [September 2026 constituent context](https://alvesty.pl/wiedza/jak-dziala-gpw-rynek-glowny-newconnect-catalyst-i-najwazniejsze-indeksy-gieldowe).

Manual entry requires an allowlisted stock, historical purchase date and **current** number of
shares. A bounded read-only Yahoo Finance request retrieves daily close history from seven days
before purchase through yesterday; purchase dates are bounded to 1990 onward. The newest
completed daily close and the last close on/before purchase (within seven days) are disclosed
with their actual dates, retrieval timestamp and source link. Nontrading dates use an explicitly
labeled previous-session reference; missing purchase references remain missing. Currency,
ordered unique dates and finite positive prices are validated. Provider failures do not invent
prices or replace saved holdings. Changing the stock/date invalidates the pending quote.

The user chooses an actual entered purchase price, an explicitly estimated reference cost,
or unknown cost. A market close is not evidence of the user's execution price. Provider split
events since purchase suppress cost comparisons pending reconciliation; current shares must be
entered correctly. The provider's historical closes may reflect split adjustments. Dividends,
fees, taxes, corporate-action reconciliation and investor cashflow performance are not inferred.

## Valuation and limits

The pure risk engine computes quantity times the dated close using Decimal. Known comparable
costs use quantity times the entered/reference cost per current share; the difference is a
native-currency unrealized change, not total investor return. Unknown costs and split reviews
suppress that comparison, including aggregate comparison for the affected currency bucket.
USD and PLN totals remain separate. No FX conversion or cross-currency total is fabricated;
individual quote dates can differ and are displayed. Stored quotes are client-supplied snapshots
when revalidated for valuation; their original source labels do not establish cryptographic trust.

Up to 100 positions are accepted per user, with unique UUIDs. Validation occurs before saving;
errors preserve the last saved positions. Live price refresh is explicit per position. Quotes
are delayed historical references, not an executable or guaranteed live feed.

CSV and broker API imports are visible planned capabilities only in this new flow. Bonds, ETFs,
options, futures and forex remain deferred here even when questionnaire knowledge is high.
Existing legacy workshop capabilities remain available on their original routes.
