# Public Bossa and XTB instrument catalog

The `/instruments` page and `GET /api/v1/broker-catalog` expose a packaged public
specification snapshot. They make no authenticated broker connection and do not
execute orders, fetch account holdings or supply investment recommendations.
The original stock valuation flow remains limited to its 40 reviewed Yahoo symbols;
catalog membership does not extend that flow's price mapping or risk calculations.

## Verified source coverage on 2026-10-11

| Source | Reference entries | Coverage |
| --- | ---: | --- |
| XTB Poland public specification | 12,599 | All advertised pages across ten categories |
| Bossa foreign instrument PDF, effective 2026-06-22 | 5,632 | All 111 table pages, counted against ISIN occurrences |
| BOSSAFX public instrument specifications | 178 | All instrument rows embedded in the public page |
| Bossa domestic equities/PDA, NewConnect, GlobalConnect, options, futures, ETFs, bonds, certificates | 0 imported | Public endpoints returned empty lists; coverage unavailable |
| Total | 18,409 | Partial overall coverage; no claim of all Bossa instruments |

Primary sources are the [XTB public specification](https://www.xtb.com/pl/specyfikacja-instrumentow),
the [Bossa foreign list](https://bossa.pl/oferta/rynek-zagraniczny), and the
[BOSSAFX specification](https://bossafx.pl/oferta/instrumenty).
The snapshot retains each source's exact URL, retrieval time, optional effective date,
SHA-256, expected count, imported count and coverage status. Sources marked complete
mean complete extraction of that source, not current account eligibility or complete
broker-wide coverage. XTB pagination is not an atomic provider snapshot; the importer
checks counts and overlaps, but cannot detect every concurrent replacement.

## Identity and units

UUIDv5 identity includes broker, instrument type, source market and source symbol.
The same underlying's physical equity and CFD remain separate. Source symbols are
not translated into Yahoo symbols or conflated across exchanges. Source ADR, ADS,
GDR and REIT categories remain available within the equity grouping. ETF, ETC, ETN,
other ETP and CFD have separate classifications. The API also reserves explicit types
for options, futures, bonds, rights, warrants and certificates; missing Bossa sources
do not justify manufacturing their series or inferring eligibility from XTB.

Only explicitly supplied ISO 4217 currencies populate `currency`; GBX is retained
as a source quotation unit, not silently converted to GBP. The BOSSAFX parser does
not infer settlement currency from a ticker or contract description. Contract size,
leverage and other specifications retain source strings and are not calculation inputs.
All records have `valuation_status=reference_only`. No generic quantity-times-price
rule is applied to CFD, futures, options or bond quotations.

## Reproduction and refresh

The application serves packaged `apps/api/quantops_api/data/broker_catalog.json`
without any live calls. Explicit maintenance commands, from the repository root:

```text
.venv\Scripts\python.exe scripts/fetch_xtb_catalog.py
.venv\Scripts\python.exe scripts/fetch_bossa_catalog.py
python scripts/extract_bossa_pdf.py
.venv\Scripts\python.exe scripts/build_broker_catalog.py
```

The extraction command needs optional `pdfplumber` in its chosen interpreter;
this is not an application or unit-test dependency. The Codex bundled document
runtime supplied it for the observed extraction. The extractor checks every page's
ISIN and row counts and binds the extracted rows to the PDF hash. Unexpected layouts,
new XTB categories, duplicate identities, pagination overlaps or count mismatches
fail before replacement of the packaged snapshot. Review a new Bossa PDF's date,
classification and layout before changing the fixed source URL.

XTB raw pages are resumable with `scripts/fetch_xtb_catalog.py --resume` under ignored
`data/generated/xtb-pages`; the default command rejects an existing manifest. For a new refresh,
use a fresh cache (archive the previous ignored directory first): cached pages must
not be mixed with a new manifest. The current snapshot was built from a fresh cache.
If domestic Bossa feeds recover, the builder deliberately stops for schema review
rather than silently claiming coverage. An official instrument export or functioning
public reference feed is still needed to populate domestic instruments and option series.

## Remaining platform work

1. Complete Bossa domestic reference data, expiring series, terms and eligibility checks;
   implement reviewed price-provider identifiers and dated data for the broader catalog.
2. Add explicit derivative position contracts, signed exposure, multiplier/settlement,
   margin, financing, expiry and rollover treatment; options additionally require call/put,
   strike, exercise rules, volatility inputs, Greeks and deterministic repricing tests.
3. Connect authenticated durable portfolio storage, ledger import, corporate actions,
   FX and scheduled data-quality monitoring; verify the outstanding infrastructure,
   backup, migration and original release gates before calling the platform fully operational.

Useful subsequent additions are concentration/margin alerts, scenario limits and clear
data-coverage reporting. The new catalog itself does not establish production readiness.
