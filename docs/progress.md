# QuantOps implementation progress

Last updated: 2026-11-01
## Native C++ Monte Carlo — 2026-11-01

Implemented the owner-requested optional C++17 engine, native C ABI, CMake helper,
typed ctypes/API integration, responsive research panel and reproducible JSON export.
The existing risk package is retained. Simulation uses complete validated allocations,
at least 252 aligned base-currency log returns, semidefinite Cholesky, explicit assumed
drift and daily buy-and-hold GBM. FX and adjusted dividends are not counted twice.
All-cash and singular-correlation cases work. Data gaps, non-finite inputs and large
workloads fail explicitly; missing/incompatible native binaries return 503.

Verification evidence:

- .venv/Scripts/python.exe scripts/build_monte_carlo.py --test: MSVC 19.40 Release
  DLL/executable built successfully; CTest 1/1 passed. Checks include closed-form
  one-asset lognormal VaR/ES/mean, repeatability, zero volatility, independent
  diversification and perfect-correlation singular covariance.
- .venv/Scripts/python.exe -m pytest apps/api/tests/test_monte_carlo.py -q
  -p no:cacheprovider: final 18 passed, including missing-export library handling.
- Focused pytest over test_monte_carlo, test_portfolio_risk, test_equity_risk_dashboard,
  test_health and packages/risk_engine/tests: 241 passed, 14 subtests passed before
  the additional loader-only regression. The final loader change passed all 18
  Monte Carlo tests. Cacheprovider was disabled because the pre-existing cache
  directory is not accessible; test behavior and warnings were not suppressed.
- Ruff check of the new Python sources, main integration and build helper: passed.
  Strict mypy on application, native adapter and endpoint: 3 source files passed.
- pnpm --filter @quantops/web build and lint: passed. Vite retains a non-fatal
  bundle-size advisory (approximately 582 kB uncompressed main JS).
- pnpm --filter @quantops/web test: 23 passed across four files.
- pnpm --filter @quantops/web exec playwright test e2e/monte-carlo.spec.ts
  e2e/portfolio-risk.spec.ts --workers=1: 10 passed (desktop/mobile), including
  real native API, chart switching, independent control changes, account isolation,
  unchanged stored reports, missing-data boundaries and axe accessibility checks.
  Desktop path and mobile histogram screenshots were visually inspected.
- Synthetic default smoke: 5,000 paths, 252 sessions, five assets, histogram count
  5,000, approximately 0.35 seconds end-to-end on this host. This is an illustrative
  measurement, not a general performance claim or comparison with Python.
- Documentation checks: 64 Markdown files passed before this progress entry.
  Tracked security scan and all 30 non-ignored untracked source files: zero findings.
  git diff --check: passed. OpenAPI regenerated from the current application,
  preserving earlier route additions and adding the new native simulation contract.

Initial checks found and corrected a bubbling change event that cleared the parent
analysis, a tiny zero-loss ES cancellation error, and missing-export library handling.
The synthetic example is explicitly allowed to use its older dated valuation;
stale provider/user valuations remain blocked. Mathematical/model limitations are
documented, and no broker interaction or trade recommendations were introduced.
The owner subsequently authorized committing and publishing this module on
2026-11-01 as Dominik Braun. The publication excludes earlier overview/benchmark
work and uses the configured GitHub noreply address. The separate
ohlcv-ml-pipeline repository remains unchanged.

Publication verification used an exported Git-index snapshot containing only this
feature on the existing branch. That snapshot passed a fresh MSVC Release build
and CTest, 23 Monte Carlo/OpenAPI API tests, strict typing for 69 API and 17 tooling
files, frontend TypeScript/build/lint, and both desktop/mobile native simulation
browser tests. Its 55 Markdown documents and source security scan passed.
The CI unit and frontend jobs now build and verify the native engine before tests.
The local dependency runner rejects junction-backed task-state directories, so
snapshot frontend checks called the same installed TypeScript, Vite, ESLint and
Playwright executables directly, without changing the published package scripts.


## Final review and owner-authorized publication — 2026-10-31

The owner explicitly requested checking all current work, committing it and publishing it
to GitHub. The existing branch is `agent/portfolio-polish`, with open draft PR #11 against
`main`. The remote was preserved; fetch confirmed zero divergence before the new commit.
This explicit request permits the branch update despite the general earlier publication
gate. It does not close release/service-dependent Definition of Done items or create a tag.

Review corrections: Overview no longer reports an empty portfolio merely because its
position table is displayed on another tab. Current quantity dates now include the latest
relevant execution or partial closure after an imported snapshot. The original snapshot/
first-execution anchor remains separate for split review. Added three Python regression
cases and desktop/mobile assertions for the Overview message. Regenerated OpenAPI and
updated the risk method version and README to match the implemented equity-only UI.

Observed pre-publication verification after these corrections:

```text
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
# Passed; all 264 Python files formatted.
.venv/Scripts/python.exe scripts/typecheck.py
# All 11 isolated strict groups passed.
.venv/Scripts/python.exe apps/api/scripts/export_openapi.py --output apps/api/openapi.generated.json
.venv/Scripts/python.exe -m pytest -m "not integration and not e2e" -q -p no:cacheprovider
# 674 passed, 1 deselected, 20 subtests passed in 27.75 seconds.
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web build
pnpm --filter @quantops/web test
# Passed; final build 405 ms, 23 tests in 5.50 seconds; existing bundle-size advisory.
$env:QUANTOPS_E2E_API_PORT='8057'
$env:QUANTOPS_E2E_WEB_PORT='4227'
pnpm --filter @quantops/web exec playwright test --workers=2
# All 62 desktop/mobile checks passed in 2.3 minutes.
```

The initial full hashed Python dependency audit failed with 19 advisory entries across
msgpack, certifi, filelock and mcp (including a duplicate certifi advisory). No finding
was suppressed. Upgraded only these four packages: certifi 2026.6.17 to 2026.10.23,
filelock 3.31.0 to 4.2.5, msgpack 1.2.1 to 1.2.4 and mcp 1.28.1 to 1.30.0. Added patched
minimum constraints, retained the MCP major-version boundary, and regenerated `uv.lock`.
The workspace was synchronized with `uv sync --locked --all-packages --all-groups`.
Post-upgrade verification:

```text
.venv/Scripts/python.exe -m pytest -m "not integration and not e2e" -q -p no:cacheprovider
# 674 passed, 1 deselected, 20 subtests passed in 25.08 seconds.
.venv/Scripts/python.exe scripts/typecheck.py
# All 11 strict groups passed, including the updated MCP SDK boundary.
.venv/Scripts/uv.exe export --locked --all-packages --all-groups --no-emit-workspace --format requirements.txt --output-file artifacts/ci/python-requirements.txt
.venv/Scripts/python.exe -m pip_audit --requirement artifacts/ci/python-requirements.txt --require-hashes --strict --progress-spinner off
# Exit 0: no known vulnerabilities found.
pnpm audit --prod
# Exit 0: no known vulnerabilities found.
.venv/Scripts/python.exe scripts/security_scan.py
.venv/Scripts/python.exe scripts/docs_check.py
git diff --check
# All passed; documentation covers 61 Markdown files.
```

A separate scan covered all 477 cached/non-ignored untracked Git candidates with zero
secret/hygiene findings. No private source workbook, local environment, report export,
screenshot, build output or dependency-audit artifact is included in the publication set.
The prepared commit includes the complete previously local import-to-risk workflow and
its dependent source/tests/docs, plus the reviewed dependency fixes. Proposed multi-asset
features remain future work. Hosted CI results are distinct from these verified local gates.

Offline distribution verification also passed:

```text
.venv/Scripts/uv.exe build --all-packages --offline --out-dir artifacts/ci/publication-dist
# Built all ten workspace packages as source distributions and wheels.
# Inspected the risk wheel: equity_diagnostics.py and portfolio_history.py are included.
```

## Tabbed equity risk workspace and descriptive risk index — 2026-10-31

Implemented the owner's request for an interactive equity risk dashboard. The default
Overview presents a versioned 0–100 descriptive risk index, followed by separate tabs
for concentration, diversification, hypothetical declines, history, allocation comparison
and data/methods. Added HHI/effective holdings, documented issuer aggregation, selectable
company detail, exposure bars, correlation inspection, capital-versus-risk contributions,
single-company stresses, selectable scenarios and a drawdown curve. Reduced repeated
header/account space specifically in this workspace and retained visible synthetic labels.

The new equity-only API scope enumerates omitted instruments instead of silently claiming
whole-account coverage. Existing mixed-scope API clients and the original mixed example
remain supported. All numerical diagnostics and the four-component heuristic are calculated
in the pure risk engine. Score prerequisites, thresholds, omissions and synthetic freshness
exception are explicit in `equity-risk-dashboard.md` and the UI. No order execution,
broker connection, probability-of-loss claim or investment recommendation was added.

Observed verification using the existing workspace environment:

```text
.venv/Scripts/python.exe -m pytest -m "not integration and not e2e" -q -p no:cacheprovider
# 671 passed, 1 deselected, 20 subtests passed in 28.82 seconds.
# Includes updated OpenAPI, backward-compatible mixed scope and the new equity diagnostics.

.venv/Scripts/python.exe scripts/typecheck.py --group risk --group api
# Both strict groups passed: 43 risk files and 65 API files.

.venv/Scripts/python.exe -m ruff check packages/risk_engine/src/quantops_risk/equity_diagnostics.py packages/risk_engine/tests/test_equity_diagnostics.py apps/api/quantops_api/application/portfolio_risk.py apps/api/quantops_api/api/xtb.py apps/api/tests/test_equity_risk_dashboard.py
.venv/Scripts/python.exe -m ruff format --check packages/risk_engine/src/quantops_risk/equity_diagnostics.py packages/risk_engine/tests/test_equity_diagnostics.py apps/api/quantops_api/application/portfolio_risk.py apps/api/quantops_api/api/xtb.py apps/api/tests/test_equity_risk_dashboard.py
# All lint checks passed; five Python files already formatted.
# Files: equity_diagnostics.py, test_equity_diagnostics.py, portfolio_risk.py,
#        api/xtb.py and test_equity_risk_dashboard.py.

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web build
# ESLint passed; TypeScript/Vite production build passed.
# The pre-existing >500 kB initial-chunk advisory remains; no warning limit was suppressed.

pnpm --filter @quantops/web test
# 4 files / 23 tests passed in 8.59 seconds.

QUANTOPS_E2E_API_PORT=8037 QUANTOPS_E2E_WEB_PORT=4207 QUANTOPS_CAPTURE_RISK=1
pnpm --filter @quantops/web exec playwright test --workers=2
# All 62 desktop/mobile Chromium checks passed in 2.4 minutes.
# Risk checks include axe WCAG A/AA, keyboard tabs, correct -10% scenario P/L,
# insufficient-score status, unknown sectors, omitted ETFs, account isolation,
# old-price blocking, invalid variants, API failure and exported diagnostic provenance.
```

Initial failures were corrected rather than suppressed: cash warning branch placement,
Decimal sum typing, an incorrect sign in the new conservation assertion, unnecessary
TypeScript assertions, ambiguous status selection, and the empty-account setup's incorrect
assumption that an analysis panel already exists before adding a report account. Vitest's
first attempt was blocked by the restricted environment's temporary-file rename; the normal
runtime passed all 23 tests. The full Python/browser runs above are the final behavioral gates.

The verified local API used the workspace virtual-environment launcher with a bundled Python
child process. The first restart guard correctly refused the child-only identity match; the
parent/child commands and workspace path were then verified before restart. A read-only
request through localhost:5173 returned HTTP 200 and a complete five-company synthetic
analysis with score 44 and `equity-diagnostics@1.0.0`. No real-provider freshness is claimed
by this synthetic check. Existing reports and unrelated owner edits were preserved.

Final verification after the synthetic badge and compact header adjustment:

```text
$env:QUANTOPS_E2E_API_PORT='8047'
$env:QUANTOPS_E2E_WEB_PORT='4217'
$env:QUANTOPS_CAPTURE_RISK='1'
pnpm --filter @quantops/web exec playwright test e2e/portfolio-risk.spec.ts --grep 'equity dashboard has' --workers=2
# Both desktop/mobile checks passed in 11.6 seconds, including axe and chart inspection.

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web build
# Both exit 0; final bundle built in 361 ms. Existing size advisory remains.

.venv/Scripts/python.exe scripts/docs_check.py
# Passed for 61 Markdown files.
.venv/Scripts/python.exe scripts/security_scan.py
# Passed with no high-confidence secret/hygiene findings.
git diff --check
# Exit 0; existing OpenAPI line-ending normalization advisory only.
```

An additional `scan_paths` run over every cached and non-ignored untracked Git candidate
returned zero findings without rendering matched values. Inspected actual desktop and mobile
screenshots of the new overview and concentration layouts. Stable, ignored preview copies are
`artifacts/equity-risk-overview.png`, `artifacts/equity-risk-concentration.png` and
`artifacts/equity-risk-diversification.png`. Attached-browser control was unavailable during
the final live check, so visual QA used the passing browser-test captures; the actual application
API proxy was independently verified as described above. No commit or publication has been
performed; release/service-dependent gates remain open.

This file records observed results only. An unchecked item is not implemented or has not yet met its exit evidence.

## Default local accounts and supplied synthetic workbook — 2026-10-11

Implemented the owner's explicit request for `admin`/`admin` (empty) and `admin1`/`admin1`
(preloaded). Source: `C:/Users/domin/Downloads/quantum_ops_portfolio_test.xlsx`; the financial
sections explicitly say DEMO / SYNTHETIC and provenance states it is not an XTB-issued statement.
The normal parser and merger generated a normalized fixture with 20 open lots / 9 instruments,
26 closed positions and 76 cash operations (122 records). No workbook instruction was executed;
no embedded price was represented as a verified provider quote. Source SHA-256 is retained.

Initialization runs only on the loopback development server, preserves existing login/UUID owners
and never overwrites edits or imports on reload. The normal registration password minimum remains
ten characters. Local credentials remain a UI gate, not server authentication or admin permissions.
Parser compatibility adds the known seven-column Sources provenance sheet and the open-position
footer. Both accounts and their synthetic origin are visible on the login/workspace screens.

Observed checks, using the repository Python environment and bundled Node/pnpm runtime:

```text
.venv/Scripts/python.exe scripts/build_local_demo.py SOURCE apps/web/src/data/localDemo.json
# open=20, closed=26, cash=76, unique_symbols=9
.venv/Scripts/python.exe -m pytest apps/api/tests/test_xtb_reports.py -q -p no:cacheprovider
# 21 passed in 1.51s
.venv/Scripts/python.exe -m ruff check scripts/build_local_demo.py apps/api/tests/test_xtb_reports.py apps/api/quantops_api/application/xtb_reports.py
# All checks passed
.venv/Scripts/python.exe -m mypy scripts/build_local_demo.py apps/api/quantops_api
# Success: no issues found in 43 source files
pnpm --filter @quantops/web test
# 23 passed in 4 test files
pnpm --filter @quantops/web lint
# exit 0, no warnings
pnpm --filter @quantops/web typecheck
# exit 0
pnpm --filter @quantops/web build
# exit 0, Vite production bundle built
pnpm --filter @quantops/web exec playwright test e2e/local-demo.spec.ts e2e/local-login.spec.ts e2e/stocks.spec.ts --workers=2
# 10 passed (46.2s), desktop/mobile Chromium, isolated ports 8017/4187
pnpm --filter @quantops/web exec playwright test e2e/local-demo.spec.ts --workers=2
# 2 passed (7.3s), after test typing correction
.venv/Scripts/python.exe scripts/security_scan.py
# Passed: no high-confidence secret or hygiene findings
.venv/Scripts/python.exe scripts/docs_check.py
# Passed for 59 Markdown files
git diff --check
# exit 0; existing OpenAPI CRLF normalization warning only
```

Initial test assumptions were corrected: analysis retains 20 lots while valuation groups nine
instruments, and the navigation label is Historia importów. Strict ESLint required explicit
storage types in the new browser test; final checks above passed without suppressions.
Visual inspection of `artifacts/default-portfolio-mobile-chromium.png` confirmed the synthetic
notice, portfolio rows and contained horizontally scrolling table. Browser checks include axe
WCAG A/AA and page overflow checks. Default-account unit/browser tests demonstrate account
isolation, owner-login collision preservation, production initialization exclusion and retained
edits/import history across reload.

The owner's existing local API process was verified by executable/arguments and restarted with
the updated parser. HTTP checks through the live localhost:5173 proxy imported the actual attached
workbook successfully (20/26/76); web and API health returned 200. No market-provider call was needed.
Working tree and diff were inspected, preserving prior owner changes; no commit or publication.

## Local login, optional questionnaire and workspace navigation — 2026-10-11

Implemented local login/password registration with confirmation, lowercase unique logins,
PBKDF2/SHA-256 password verifiers (600,000 iterations), random per-account salts, tab-local
session state and logout. Plaintext passwords never enter localStorage or API requests.
The UI and docs disclose that this is a client-controlled local access gate, not server
authentication or encrypted report storage. No cloud, broker connectivity or paid service
was introduced. Existing unprotected profiles can be selected explicitly during registration,
preserving their UUID, previous positions and XTB report accounts.

The questionnaire is optional, initially collapsed and immediately skippable. Skip persists
and does not affect financial calculations or access to imports. Settings allows later
completion/editing. Broker setup supports XTB and Bossa together, with Bossa import still
marked unavailable. Broker preferences are editable without removing existing reports.
The six-view layout separates Overview, Portfolio, Brokers/accounts, Import, History and
Settings, adds current-view navigation, next-action cards and an import history table.
Account creation opens Import; confirmation opens Portfolio. Previous calculation,
deduplication, account isolation and provider-outage behavior remain exercised by tests.

Observed verification:

```text
pnpm --filter @quantops/web typecheck
# exit 0: TypeScript passed
pnpm --filter @quantops/web lint
# exit 0: no errors or warnings (including final state)
pnpm --filter @quantops/web build
# exit 0: final TypeScript/Vite production build, 70 modules transformed
pnpm --filter @quantops/web test
# exit 0: 3 files passed, 20 tests passed
QUANTOPS_E2E_API_PORT=8017 QUANTOPS_E2E_WEB_PORT=4187 pnpm --filter @quantops/web exec playwright test stocks.spec.ts local-login.spec.ts --workers=2
# exit 0: 8 passed in 41.5s, desktop/mobile Chromium
QUANTOPS_E2E_API_PORT=8017 QUANTOPS_E2E_WEB_PORT=4187 pnpm --filter @quantops/web exec playwright test local-login.spec.ts --workers=2
# exit 0: 4 passed in 13.7s after final optional-questionnaire presentation/copy adjustment
.venv/Scripts/python.exe scripts/security_scan.py
# exit 0: no high-confidence secret or hygiene findings
.venv/Scripts/python.exe scripts/docs_check.py
# exit 0: documentation checks passed for 59 Markdown files
git diff --check
# exit 0: no whitespace errors
HTTP GET http://localhost:5173/ and http://localhost:5173/api/v1/health
# both HTTP 200; existing local runtime remains running
```

Tests use visibly synthetic accounts/passwords and report fixtures. They cover confirmation
mismatch, rejected passwords, session removal, reload, logout/login, questionnaire skip/later
completion, multi-broker preferences, migration with retained reports and the existing XTB
import/valuation workflow. Axe WCAG A/AA scans and horizontal overflow checks passed on tested
screens. The first browser run found two equally named logout controls on desktop; the sidebar
control now opens account settings, leaving one clear logout action. No tests were suppressed.
No backend calculation changed, so the earlier 623-test Python result was not rerun for this
frontend-only change. Auth and account screenshots were captured with synthetic data and
visually inspected. Unrelated owner changes were preserved; no commit or publication occurred.

## XTB report import and separate local accounts — 2026-10-11

Implemented the report-first `/` and `/stocks` workspace: XTB/Bossa brand selection,
multiple XTB accounts, CSV paste/file upload, XLSX/ZIP, bounded stateless parsing,
preview and explicit snapshot/history confirmation. Bossa import remains unavailable.
The private owner ZIP was read in memory and verified to contain closed-position and
cash-operation history only; current holdings correctly remain unknown. No private
report, account number or financial amount is retained in repository fixtures.

Idempotent event merging, conflicting-history rejection, older-snapshot rejection,
full/empty snapshot replacement and complete-ledger average-cost reconstruction are
implemented. Unsold buys remain open; partial sells reduce units, oversells reject
atomically. CFD direction and quantity remain separate from physical shares, even when
tickers match. Closed P/L is not added to its matching cash settlement. Quote refresh
reuses the existing provider adapter with reviewed listing and currency mapping,
preserves old quotes on provider failure and displays separate native-currency totals.
Splits suppress cost comparison. User-controlled 15-minute refresh requires a visible
page; quotes are completed daily closes, not live prices. Existing manual data is retained.

Final verification commands and observed results:

```text
.venv/Scripts/python.exe -m pytest -m "not integration and not e2e" -q -p no:cacheprovider
# exit 0: 623 passed, 1 deselected, 20 subtests passed in 22.39s
.venv/Scripts/python.exe -m mypy apps/api/quantops_api packages/risk_engine/src/quantops_risk
# exit 0: no issues found in 67 source files
.venv/Scripts/python.exe -m ruff check apps/api/quantops_api apps/api/tests/test_xtb_reports.py packages/risk_engine/src/quantops_risk
# exit 0: all checks passed
pnpm --filter @quantops/web lint
# exit 0: no ESLint errors or warnings
pnpm --filter @quantops/web build
# exit 0: TypeScript and Vite production build passed; 66 modules transformed
QUANTOPS_E2E_API_PORT=8017 QUANTOPS_E2E_WEB_PORT=4187 pnpm --filter @quantops/web exec playwright test stocks.spec.ts --workers=2
# exit 0: 4 passed in 16.8s, desktop/mobile Chromium including axe WCAG A/AA scans
.venv/Scripts/python.exe scripts/security_scan.py
# exit 0: no high-confidence secret or hygiene findings
.venv/Scripts/python.exe scripts/docs_check.py
# exit 0: documentation checks passed for 58 Markdown files
git diff --check
# exit 0: no whitespace errors
```

Browser tests cover preview before persistence, unsold positions, repeat import, multiple
same-currency accounts, profile isolation, reload, provider failure and closed-only file
upload. Backend synthetic tests also exercise XLSX with incorrect A1-only dimensions,
ZIP boundaries, formula/entity rejection, localized CSV, bad/future numbers/dates,
conflicts, partial closes, complete sale, same-time numeric execution ordering and CFD
separation. The checked-in OpenAPI snapshot was regenerated and verified by the full suite.

Initial failures were corrected: CSV sniffing originally rejected metadata rows with fewer
columns; it now detects the table header. Strict typing exposed an optional date and legacy
currency annotation. ESLint rejected FileReader stringification. The first browser run
used obsolete catalog query parameters; the corrected test uses the actual API query.
Sandboxed pnpm failed with EPERM and was rerun outside that restriction. No test was
suppressed to pass; the earlier manual-entry browser scenarios were replaced because
the owner explicitly requested report-only additions. Final screenshots use synthetic
data and were visually inspected. No live provider was required by the test suites.

Remaining: durable protected storage and backup restore, complete cash/corporate-action
reconciliation, bounded quote queue for more than 20 symbols, reviewed GBX/alias mappings,
FX normalization and imported exposure integration with concentration, VaR/ES and
scenarios. CFD financing/multipliers/margin, options and Bossa import need dedicated
verified contracts and data. This change does not complete a release milestone.
No commit, PR update or publication was performed; unrelated owner edits remain.

## Public broker catalog — 2026-10-11

The requested full Bossa/XTB coverage is partially delivered. Added 18,409 packaged
public reference instruments and an accessible `/instruments` browser, searchable by
name/symbol/ISIN with broker/type/market filters, pagination and source details.
All advertised XTB Poland pages were downloaded (12,599 records); all 111 Bossa
foreign PDF table pages were parsed and checked against per-page ISIN counts (5,632);
all public BOSSAFX embedded specification records were normalized (178).
Eight Bossa domestic group endpoints returned empty lists; their coverage remains
unavailable. Options/futures were not manufactured and broader position valuation
remains deferred. No milestone completion, account access, commit or publication is claimed.

Observed checks from the repository root:

```text
.venv\Scripts\python.exe scripts/fetch_xtb_catalog.py
# exit 0: ten categories downloaded, 12,599 advertised entries; four concurrent public reads
# Bossa PDF, BOSSAFX page and domestic endpoints were downloaded with explicit httpx reads.
# scripts/fetch_bossa_catalog.py now records the same fixed URLs for reproducibility;
# its live network workflow was not rerun after adding the script.

.venv\Scripts\python.exe scripts/extract_bossa_pdf.py
# exit 0: 5,632 records / 111 table pages, using bundled pdfplumber via PYTHONPATH
.venv\Scripts\python.exe scripts/build_broker_catalog.py
# exit 0: 18,409 validated entries; overall coverage remains partial

.venv\Scripts\python.exe -m pytest -p no:cacheprovider apps/api/tests/test_stocks.py apps/api/tests/test_broker_catalog.py apps/api/tests/test_health.py tests/test_bossa_pdf_parser.py -q
# exit 0: 22 passed in 4.36 seconds; includes seven new API/parser tests and OpenAPI equality

.venv\Scripts\python.exe scripts/typecheck.py --group api --group tooling
# exit 0: strict API (53 source files) and tooling (15 source files) checks

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web build
# exit 0: ESLint, TypeScript and production Vite build
pnpm --filter @quantops/web exec playwright test e2e/broker-catalog.spec.ts --workers=2
# exit 0: four desktop/mobile tests, including equity/CFD separation, source gaps,
# derivative details, pagination, service errors and axe accessibility checks (10.0 seconds)
pnpm --filter @quantops/web exec playwright test e2e/stocks.spec.ts --workers=2
# exit 0: four existing desktop/mobile stock regressions (11.0 seconds)

.venv\Scripts\ruff.exe check apps/api/quantops_api/application/broker_catalog.py apps/api/quantops_api/api/broker_catalog.py apps/api/tests/test_broker_catalog.py scripts/fetch_xtb_catalog.py scripts/fetch_bossa_catalog.py scripts/build_broker_catalog.py scripts/extract_bossa_pdf.py tests/test_bossa_pdf_parser.py
.venv\Scripts\ruff.exe format --check apps/api/quantops_api/application/broker_catalog.py apps/api/quantops_api/api/broker_catalog.py apps/api/tests/test_broker_catalog.py scripts/fetch_xtb_catalog.py scripts/fetch_bossa_catalog.py scripts/build_broker_catalog.py scripts/extract_bossa_pdf.py tests/test_bossa_pdf_parser.py
# exit 0: new Python sources linted and formatted
.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
git diff --check
# exit 0: 57 Markdown files, repository hygiene/secret gate and whitespace checks
```

Corrected initial findings: the supplied PDF skill path was stale; the installed
26.1009.11318 skill/runtime was located. Plain pypdf text and table borders merged
some PDF cells; the final parser uses pdfplumber text, explicit page-market inheritance,
all source receipt categories and strict ISIN row counts. Ruff/mypy found import,
formatting and reused-variable issues, which were fixed. Two initial browser tests
could not match the source selector's exact accessible label; an explicit label fixed
both, without weakening assertions. A rendered Bossa input page and actual desktop
catalog screenshot were inspected. No delivered PDF was authored.

Sandbox DNS, pnpm workspace access and TestClient execution required scoped escalated
reruns. The initial restricted TestClient run stalled; the successful 22-test run used
the same test contracts outside that restriction. Downloaded raw pages/PDFs and browser
traces remain in ignored generated/test directories; the curated normalized snapshot
is the intended packaged source artifact. Existing owner changes were preserved.

## Stock-only users and manual holdings — 2026-10-05

- [x] Add a local user start, risk/knowledge questionnaire and empty portfolio at `/` and `/stocks`.
- [x] Isolate holdings by UUID profile and preserve the last valid save on validation/provider errors.
- [x] Add 20 US and 20 Polish equities, historical reference lookup and explicit cost basis choice.
- [x] Keep native USD and PLN values separate and suppress unknown/split-affected cost comparisons.
- [x] Mark CSV, broker imports and other instruments as deferred in the new flow.
- [x] Preserve the prior investor ledger at `/investor`, retaining its full browser assertions.

Observed verification:

```text
.venv\Scripts\python.exe -m pytest apps/api/tests/test_stocks.py packages/risk_engine/tests/test_stock_holdings.py -q -o cache_dir=.pytest_cache_publish
# exit 0; 15 passed
.venv\Scripts\python.exe -m pytest -m "not integration and not e2e" -q -o cache_dir=.pytest_cache_publish
# exit 0; 564 passed, 1 deselected, 20 subtests passed in 24.70s
.venv\Scripts\python.exe scripts/typecheck.py --group api --group risk
# exit 0; both strict groups passed
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# exit 0; 231 files formatted
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web build
# exit 0; lint, TypeScript and Vite build passed
pnpm --filter @quantops/web test
# exit 0; 3 files, 20 Vitest tests passed
pnpm --filter @quantops/web test:e2e --workers=2
# 36 prior tests passed; four new tests failed due to label-text selectors
pnpm --filter @quantops/web test:e2e e2e/stocks.spec.ts --workers=2
# exit 0; four new desktop/mobile tests passed after switching to accessible combobox roles
# extended rerun: four passed in 16.3s, including axe on start/survey/portfolio and stale-quote invalidation
# final rerun after profile explanations and form reset: four passed in 17.4s; lint/build also passed
.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
git diff --check
# exit 0; 55 Markdown files; no high-confidence secrets/hygiene findings; no whitespace errors
```

The first API typecheck found a test accessing a non-exported module import; the test now patches
the explicit httpx import and both strict groups pass. No assertions or timeouts were weakened.
Live read-only Yahoo checks succeeded for all 40 allowlisted tickers using a 2026-10-01 request
date, with latest closes dated 2026-10-02 and the correct native currency. Additional API probes
checked historical Apple and PKO closes for 2025-04-04 and the renamed EBP.WA mapping. This live
evidence is separate from offline unit/browser fixtures, which remain visibly synthetic.
Desktop and mobile start/portfolio screenshots were inspected. The API was restarted on port
8000 with the new routes and the frontend remains available on port 5173. No hosted user storage,
broker connectivity or full retail MVP completion is claimed.

## Investor workspace pre-publication verification — 2026-10-05

The owner authorized committing and publishing the existing local investor-workspace, cash-budget,
onboarding and synthetic forecast changes on the existing PR #11 branch. Transaction history,
flow-aware performance and named scenarios are now supported in browser-local storage; durable
hosted tenants and the full retail MVP remain outside the verified scope.

```text
.venv\Scripts\python.exe -m pytest -m "not integration and not e2e" -q -o cache_dir=.pytest_cache_publish
# exit 0; 549 passed, 1 deselected, 20 subtests passed in 22.39s
.venv\Scripts\python.exe scripts/typecheck.py
# exit 0; 11 strict isolated groups passed
.venv\Scripts\ruff.exe check .
# exit 0; all checks passed
.venv\Scripts\ruff.exe format --check .
# exit 0; 225 files already formatted
pnpm --filter @quantops/web lint
# exit 0
pnpm --filter @quantops/web test
# exit 0; 3 files, 20 tests passed
pnpm --filter @quantops/web build
# exit 0; TypeScript and Vite production build passed
pnpm --filter @quantops/web test:e2e --workers=2
# exit 0; all 36 desktop/mobile tests passed (1.6m), including axe checks
.venv\Scripts\python.exe scripts/docs_check.py
# exit 0; 52 Markdown files initially, 53 on the final rerun after the separate pytest cache was created
.venv\Scripts\python.exe scripts/security_scan.py
# exit 0; no high-confidence secret or hygiene findings
git diff --check
# exit 0
```

Initial sandboxed frontend commands failed with EPERM; reruns outside that restriction passed.
The first frontend lint attempt raced with Playwright replacing its results directory; the
subsequent lint passed. The first browser run passed 35 tests and timed out during mobile browser
context teardown for the education exercise; the full two-worker rerun passed all 36 tests without
changing assertions or timeout settings. The first sandboxed Python run stalled and was interrupted;
the subsequent full run reached 100% but failed writing the existing pytest cache. The final full
run used a separate cache directory and exited successfully. Live provider refresh, production
storage and hosted CI for this new commit are not established by these local checks.

## Synthetic forecast quiz — 2026-10-04

- [x] Add a no-lookahead market-direction quiz (12 synthetic charts, confidence, periodic reveal).
- [x] Score hit/miss/sideways with calibration summary (effectiveness, Brier, buckets).
- [x] Cover API invariants and refresh OpenAPI; wire Polish UI panel under Quiz prognoz.

Observed verification:

```text
pytest apps/api/tests/test_retail_next.py -k forecast
# 2 passed
pytest apps/api/tests/test_health.py
# 5 passed (OpenAPI routes + snapshot)
apps/web: tsc + eslint
# passed
```

## YNAB-style cash envelopes — 2026-10-04

- [x] Add a local zero-based cash budget panel (Ready to Assign, envelopes, assigned/activity/available).
- [x] Persist per-user browser state; clear on logout/delete; reset amounts on base-currency change.
- [x] Cover envelope math with Vitest; extend retail e2e through the login/onboarding gate.

Observed verification:

```text
apps/web: vitest run
# 3 files, 20 passed (includes cashBudget tests)
apps/web: tsc -b --pretty false
# passed
apps/web: eslint . --max-warnings 0
# passed
```

E2E for the new budget panel was updated (`enterRetailWorkspace` + envelope assignment). Playwright
browsers were unavailable in this environment (`npx playwright install` required), so the UI e2e
was not executed here; Vitest/typecheck/lint passed.

## Retail history and education follow-up — 2026-10-04

- [x] Add strict historical CSV preview/confirmation and dated-FX repricing of current units.
- [x] Reuse historical risk calculations, suppress insufficient samples, validate aligned dates,
  reject duplicate/ambiguous mappings and label synthetic/stale history.
- [x] Add interactive charts, separate fee budgets, optional goals/limits and a ten-step synthetic
  decision experiment with signed cursors, costs, benchmark and confidence calibration.
- [x] Refine the responsive visual design and clear all new session data on explicit deletion.
- [x] Restore the local Python 3.12 environment after a blocked recreation attempt; remove the
  temporary repair environment. No source or portfolio data was lost.
- [x] Fix the frontend CI API prerequisite and upgrade dependencies flagged by the previous audit.

Observed verification:

```text
.venv/Scripts/python.exe -m pytest -q -o cache_dir=artifacts/pytest-retail-cache
# 531 passed, 1 skipped (isolated PostgreSQL unavailable), 20 subtests passed
.venv/Scripts/python.exe scripts/typecheck.py
# all 11 strict groups passed
.venv/Scripts/python.exe -m ruff check apps/api
.venv/Scripts/python.exe -m ruff format --check apps/api
# passed; 40 files formatted
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# passed; 14 Vitest tests; production bundle built
.venv/Scripts/python.exe -m pip_audit --progress-spinner off --format json --output artifacts/updated-python-audit.json
pnpm audit --prod
# both passed; no known vulnerabilities in the audited installed/production dependencies
pnpm --filter @quantops/web test:e2e --workers=2
# 28 passed (desktop/mobile), including axe accessibility checks
.venv/Scripts/python.exe scripts/docs_check.py
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
# passed; 49 Markdown files; 218 Python files already formatted
.venv/Scripts/python.exe scripts/security_scan.py
git diff --cached --check
# passed after staging all new source files; no secret/hygiene or whitespace findings
# Running Vite proxy: /api/v1/health returned ok; /api/v1/retail/history-demo returned 1020 rows
```

Browser testing first found one desktop contrast issue: the expanded menu overflowed its dark
sidebar. Adding scroll containment corrected the actual layout; no accessibility rule was disabled.
Desktop and mobile history screenshots were visually reviewed. Optional service/production gates
remain separate from these local checks.

Hosted run `37211696446` passed all nine application, PostgreSQL, browser and security jobs.
Its final container job exposed an existing packaging defect: separately resolved wheel builds
collected both Pydantic 2.13.4 and 2.13.5, and wildcard installation demanded both. The API image
now installs its production dependency closure once from `uv.lock` with non-editable workspace
packages, then copies only the environment into the unprivileged runtime. Local Docker is
unavailable; hosted container verification is required for this correction.

The same `uv sync --locked --package quantops-api --no-dev --no-editable` command succeeded in a
temporary Windows environment with 35 packages. Its installed API imported successfully and
produced all 1020 synthetic history rows. The temporary environment was removed afterwards.
This verifies dependency selection and packaging, not the Linux container runtime.

The first follow-up exposed a static test still expecting the retired five-wheel build layout.
Updated its guardrails to require locked production-only non-editable installation, source copies,
an isolated runtime environment and the same non-root user; no runtime safety check was removed.
The focused Dockerfile test passed (1 test); its Ruff lint/format, all documentation checks and
diff whitespace checks passed before publication.

Final hosted evidence: run `37212261658` completed successfully at commit `2cb2515`.
All ten jobs passed, including Python tests, frontend/browser tests, dependency/security checks,
PostgreSQL/pgvector migrations and both container builds/health smoke tests. This is hosted
evidence; no local Docker run or full retail-product completion is claimed.

## Retail first vertical flow — 2026-10-04

- [x] Preserve React/FastAPI, pure valuation/scenario calculations and existing research routes.
- [x] Connect the Polish personal workspace to stateless FastAPI calculations.
- [x] Verify manual/current-position CSV inputs, signed values, cash, quotation-currency exposures
  and concentration; reject unsupported derivatives and contract multipliers.
- [x] Verify combined price/FX sensitivity, short/long hedge direction, no/partial/full forward
  payoffs, separate costs, theoretical carry and oversized initial hedges after asset losses.
- [x] Verify readable report contents, stale-result invalidation, local restore/delete, base-currency
  rate reset, synthetic provenance and responsive keyboard/axe accessibility.
- [x] Document synthetic inputs, missing history, stale prices, no ETF look-through, model exclusions
  and actual/deferred scope in `docs/retail-first-flow.md`.
- [x] Add optional onboarding, user historical-risk data and a synthetic educational experiment
  in the follow-up recorded above.
- [ ] Complete a transaction-linked cost ledger, persistence/tenant authentication and separately
  scoped broker-specific read-only adapters.

Observed scoped gates:

```text
.venv\Scripts\python.exe -m pytest apps/api/tests packages/risk_engine/tests -q -o cache_dir=artifacts/pytest-retail-cache
# exit 0; 190 passed, 1 PostgreSQL integration test skipped, 14 subtests passed

.venv\Scripts\python.exe scripts/typecheck.py --group api --group risk
# exit 0; 35 API files and 30 risk files checked under strict mypy

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
pnpm --filter @quantops/web test:e2e
# exit 0; 14 Vitest tests, production build, 22 desktop/mobile Playwright tests

.venv\Scripts\ruff.exe check <changed Python files>
.venv\Scripts\ruff.exe format --check <changed Python files>
# exit 0; lint passed and all 6 changed Python files already formatted

.venv\Scripts\python.exe scripts/security_scan.py
.venv\Scripts\python.exe scripts/docs_check.py
git diff --check
# exit 0; no high-confidence secret/hygiene findings, 48 Markdown files checked, clean diff
```

Initial verification caught an outdated exact route-set assertion (updated with the three new
retail endpoints), global research-table colors leaking into the light personal workspace (fixed
with scoped colors), and parallel browser tests exhausting the production-default 20/minute limit.
The test server alone uses a 1000/minute budget; a dedicated API test verifies the normal configurable
429 response and Retry-After header. Existing pytest cache permissions required a fresh ignored
`artifacts/pytest-retail-cache`; no test or warning check was disabled. The public OpenAPI snapshot
was regenerated and its existing equality gate passes. The owner subsequently explicitly
authorized recording these changes in Git and publishing them to GitHub on 2026-10-04. This
authorization overrides the prior publication restriction for this change; it does not mark the
retail MVP or master-spec Definition of Done complete. Use the existing branch and draft PR #11.

The entire retail MVP remains open. The completed scope is the specifically requested first flow:
portfolio → exposures → currency scenario → hedge comparison, plus CSV, local data controls,
before/after valuation and report export.

Local preview started with the documented commands on loopback ports 8000 and 5173. A direct
health request and a Vite-proxied demo request returned the healthy API and four synthetic positions.
The Codex browser-panel opening request was queued by the app; use `http://127.0.0.1:5173/` directly
if the preview panel is not visible. Development processes remain running for the owner to inspect.

Pre-publication repository security, documentation and whitespace checks passed again. The commit
contains only the 22 source, test, contract, example and documentation files belonging to this flow;
preview artifacts, build output and test caches are excluded. No merge or release is requested.

## Milestone 0 — discovery and foundation

- [x] Read the authoritative 2,442-line master specification in full.
- [x] Confirm the workspace was empty and unrelated owner work would not be overwritten.
- [x] Inspect system and bundled Python, Node, pnpm, Git, Docker, `uv`, `gh`, Make, and Terraform availability.
- [x] Create the implementation plan and risk register.
- [x] Scaffold the initial monorepo, Compose core, safe local configuration, and continuity files.
- [x] Verify the locked Python workspace install.
- [x] Verify Python format/lint/type checks and backend smoke tests.
- [x] Verify pnpm install, peer dependencies, frontend lint/type checks/tests/build.
- [x] Verify repository hygiene and targeted secret-pattern scan.
- [x] Initialize Git on `main`.
- [x] Create the first scoped commit (`102406d`).

Observed commands:

```text
python --version
# Python 3.13.7

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe --version
# Python 3.12.13

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --version
# v24.14.0

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd --version
# 11.9.0 (bundled verification runtime; project declares current pnpm 11.15.0)

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe --version
# git version 2.53.0.windows.3
```

Unavailable on system `PATH`: `git`, `uv`, `node`, `npm`, `pnpm`, `docker`, `gh`, `make`, and `terraform`. Bundled Git/Node/pnpm are usable by absolute path. Docker-backed checks remain pending.

Verified foundation gates:

```text
.venv\Scripts\uv.exe sync --locked --all-packages
# exit 0; resolved 70 packages, checked 68

.venv\Scripts\ruff.exe check apps/api scripts
# exit 0; All checks passed

.venv\Scripts\ruff.exe format --check apps/api scripts
# exit 0; 12 files already formatted

.venv\Scripts\mypy.exe apps/api
# exit 0; 9 source files, no issues

.venv\Scripts\pytest.exe apps/api/tests -q
# exit 0; 3 passed

pnpm install --frozen-lockfile --offline
# exit 0; lockfile already up to date

pnpm peers check
# exit 0; no peer dependency issues

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# all exit 0; 1 Vitest test passed; Vite 8.1.5 production build completed

.venv\Scripts\python.exe scripts/docs_check.py
# exit 0; 12 repository-owned Markdown files checked
```

Targeted scans found no known private-key, AWS, GitHub, OpenAI-style, or Slack token patterns and no repository-owned file over 1 MiB. This is not yet a substitute for the deeper Milestone 12 security gates.

## Milestone 1 — domain and persistence

- [x] Framework-independent value objects, entities, and repository ports.
- [x] SQLAlchemy mappings and asynchronous repositories.
- [ ] Clean-database Alembic migration and PostgreSQL constraints/indexes.
- [ ] Optimistic concurrency, audit, and transactional outbox integration tests.
- [x] ER model documentation.

Verified domain-package gates:

```text
.venv\Scripts\pytest.exe packages/domain/tests --cov=quantops_domain --cov-branch -q
# exit 0; 34 passed, 6 subtests passed; 84% combined branch coverage

.venv\Scripts\ruff.exe check packages/domain
.venv\Scripts\ruff.exe format --check packages/domain
# both exit 0

.venv\Scripts\mypy.exe packages/domain/quantops_domain packages/domain/tests
# exit 0; 15 source files, no issues

.venv\Scripts\uv.exe build --package quantops-domain --offline
# exit 0; sdist and wheel built
```

Verified persistence gates:

```text
.venv\Scripts\pytest.exe apps/api/tests -m "not integration" -q
# exit 0; 22 passed, 1 deselected

.venv\Scripts\ruff.exe check apps/api
.venv\Scripts\ruff.exe format --check apps/api
# both exit 0; 22 files formatted

.venv\Scripts\mypy.exe apps/api
# exit 0; 21 source files, no issues

PYTHONPATH=apps/api;packages/domain .venv\Scripts\alembic.exe -c apps/api/alembic.ini upgrade head --sql
# exit 0; PostgreSQL DDL compiled through revision 0001, including vector extension,
# semantic scenario versions, named constraints/indexes, and transactional outbox

.venv\Scripts\uv.exe build apps/api --offline
# exit 0; sdist and wheel built
```

The adapters include latest-per-instrument position reads, guarded portfolio updates, exact
`NUMERIC(38,12)` prevalidation, safe UTC handling, and same-transaction audit/outbox staging.
Their offline behavior and SQL shape are tested. A live clean-database upgrade, constraint
execution, pgvector/HNSW creation, and transaction/concurrency integration tests still require an
isolated PostgreSQL database. Therefore Milestone 1 is not complete.

## Milestone 2 — synthetic market and data quality

- [x] Deterministic two-year synthetic dataset and manifest.
- [x] Intentional duplicate, late, missing, and malformed quality cases.
- [ ] Idempotent seed/upsert and quarantine path.
- [x] Lineage and byte-reproducibility tests.

File-generation, validation, and quarantine are implemented; PostgreSQL seed/upsert remains pending, so Milestone 2 is not yet complete.

Verified synthetic-data gates:

```text
.venv\Scripts\pytest.exe -c pipelines/pyproject.toml pipelines/tests --cov=quantops_pipelines --cov-branch -q
# exit 0; 19 passed; 92% combined branch coverage

.venv\Scripts\ruff.exe check pipelines
.venv\Scripts\ruff.exe format --check pipelines
# both exit 0

.venv\Scripts\mypy.exe --config-file pipelines/pyproject.toml pipelines/src/quantops_pipelines pipelines/tests
# exit 0; 10 source files, no issues

PYTHONPATH=pipelines/src .venv\Scripts\python.exe -m quantops_pipelines verify --dataset data/synthetic
# exit 0; status valid

PYTHONPATH=pipelines/src .venv\Scripts\python.exe -m quantops_pipelines generate --output data/synthetic
# exit 0; 2,088 bars; files_written=0; files_unchanged=11
```

Aggregate dataset SHA-256: `2796bd52b205182f471903f42638c6f6751093c658d1017ecf4be03c3c1b1150`.

## Milestone 3 — risk engine

- [x] Returns, valuation, volatility, covariance, VaR, ES, drawdown, concentration, contributions, scenarios, and backtesting.
- [x] Known-example and property tests, methodology documentation, and benchmark evidence.
- [x] Confirm framework independence and no `NaN` leakage.

Verified risk-engine gates:

```text
.venv\Scripts\pytest.exe packages/risk_engine/tests --cov=quantops_risk --cov-branch -q
# exit 0; 99 passed, 14 subtests passed; 98% combined branch coverage

.venv\Scripts\ruff.exe check packages/risk_engine
.venv\Scripts\ruff.exe format --check packages/risk_engine
# both exit 0

.venv\Scripts\mypy.exe packages/risk_engine/src/quantops_risk packages/risk_engine/tests
# exit 0; 28 source files, no issues

.venv\Scripts\uv.exe build packages/risk_engine --offline
# exit 0; sdist and wheel built

.venv\Scripts\python.exe packages/risk_engine/benchmarks/benchmark_risk_engine.py
# Python 3.12.13, Windows 11; 756 observations x 25 instruments; 0.223069 seconds
```

The benchmark is a local observation, not a universal SLA.

## Milestone 4 — application API

- [x] Expose all 31 required versioned `/api/v1` paths with validated request/response schemas.
- [x] Compute deterministic portfolio risk, evidence, and scenario responses through the domain,
  contract, and risk-engine packages.
- [x] Add RFC 9457 problem details, request/correlation IDs, CORS allowlisting, bounded pagination,
  date validation, and rate limiting.
- [x] Protect demo writes, enforce ETag/`If-Match` concurrency, and detect idempotency-key conflicts.
- [x] Export JSON/CSV reports and check a deterministic OpenAPI snapshot for contract drift.
- [ ] Move the critical application path from the process-local adapter to PostgreSQL repositories.
- [ ] Generate the TypeScript client and complete live frontend integration.

Verified application-API gates:

```text
.venv\Scripts\pytest.exe apps/api/tests -q
# exit 0; 39 passed, 1 skipped (PostgreSQL integration unavailable)

.venv\Scripts\ruff.exe check apps/api
.venv\Scripts\ruff.exe format --check apps/api
# both exit 0

.venv\Scripts\mypy.exe apps/api
# exit 0; no issues

.venv\Scripts\uv.exe build apps/api --offline
# exit 0; sdist and wheel built
```

The process-local fallback contains 41 dates for each of four instruments (164 accepted bars),
distinct from the canonical 2,088-bar database fixture. It now exposes deterministic grounded risk
briefs and the 44-case synchronous AI evaluation while returning truthful unavailable responses for
other unconnected capabilities. Dockerfile structure is tested, but a container build and live
PostgreSQL execution remain unverified because Docker is unavailable. Milestone 4 is not complete
until the persistence critical path and generated live client are connected.

## Milestone 5 — frontend product

- [x] Responsive product routes, navigation, design system, and deterministic demo adapter.
- [x] Dashboard, portfolio, scenario, evidence/brief, market, model, pipeline, audit,
  methodology, and architecture views.
- [x] Loading, empty, error, stale, partial, insufficient-history, and offline states.
- [x] Frontend fixture risk/scenario values reconciled to the current API demo service.
- [ ] Generated OpenAPI client and live API integration.
- [x] Automated accessibility scan and keyboard/browser critical-path end-to-end suite.

Verified frontend gates:

```text
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
# both exit 0

pnpm --filter @quantops/web test
# exit 0; 2 files, 14 tests passed

pnpm --filter @quantops/web test:e2e
# exit 0; 14 Playwright tests passed across desktop Chromium and a Pixel 7 viewport
# six representative product routes passed automated WCAG A/AA axe scans in each project

pnpm --filter @quantops/web build
# exit 0; 29 modules; JS 280.54 kB (80.79 kB gzip), CSS 49.11 kB (10.60 kB gzip)
```

Browser QA exercised the landing page, dashboard, scenario selection/custom validation, evidence
briefs, desktop layout, and a 390 x 844 responsive viewport. The automated suite now covers the
landing page plus dashboard, scenario, grounded brief/evidence, model/drift, and pipeline-quality
routes at desktop and mobile sizes. It also verifies skip-link focus, keyboard navigation, scenario
execution, and evidence citation navigation. The mobile navigation scrollbar, scenario-export
decimal rounding, metadata contrast, decorative ARIA, and scrollable-table keyboard access were
corrected from these reviews. Milestone 5 remains incomplete only because the generated OpenAPI
client and live API integration are not connected.

## Milestone 6 — streaming and outbox

- [x] Versioned event-envelope and payload contracts.
- [x] Broker-neutral deterministic replay, idempotent consumer, and outbox-publisher services.
- [x] Duplicate/conflicting-content, late/out-of-order, bounded retry, safe DLQ, and metrics behavior.
- [x] Commit-after-durability ordering, partition replay barriers, and broker-outage simulation.
- [x] Controlled `portfolio.changed.v1` to `risk.recompute.requested.v1` outbox derivation.
- [ ] Live Redpanda producer/consumer adapter and isolated broker integration tests.
- [ ] Replay-driven persisted risk snapshot update and optional live UI updates.

Verified event-contract gates:

```text
.venv\Scripts\pytest.exe -c packages/data_contracts/pyproject.toml \
  packages/data_contracts/tests --cov=quantops_contracts --cov-branch -q
# exit 0; 43 passed; 94% combined branch coverage

.venv\Scripts\ruff.exe check packages/data_contracts
.venv\Scripts\ruff.exe format --check packages/data_contracts
# both exit 0; 12 files formatted

.venv\Scripts\mypy.exe --config-file packages/data_contracts/pyproject.toml \
  packages/data_contracts/src/quantops_contracts packages/data_contracts/tests
# exit 0; 12 source files, no issues

.venv\Scripts\uv.exe build packages/data_contracts --offline
# exit 0; sdist and wheel built
```

The six v1 contracts enforce type/version pairing, UTC/non-nil identifiers, bounded payloads,
finite Decimal values, canonical JSON, stable idempotency keys, and explicit synthetic labels.
They intentionally have no broker dependency.

Verified broker-neutral worker gates:

```text
.venv\Scripts\pytest.exe -c apps/stream_worker/pyproject.toml apps/stream_worker/tests \
  --cov=quantops_stream_worker --cov-branch -q
# exit 0; 29 passed; 89% combined branch-aware coverage

.venv\Scripts\ruff.exe check apps/stream_worker
.venv\Scripts\ruff.exe format --check apps/stream_worker
# both exit 0; 18 files formatted

.venv\Scripts\mypy.exe --config-file apps/stream_worker/pyproject.toml \
  apps/stream_worker/src apps/stream_worker/tests
# exit 0; 17 source files, no issues

.venv\Scripts\uv.exe build apps/stream_worker --offline
# exit 0; sdist and wheel built
```

The process-local adapters demonstrate exact redelivery, idempotency conflicts, bounded lateness,
metadata-only DLQ records, planned retry delays without sleeping, broker outage behavior, and
acknowledged publication ordering. They do not prove consumer-group rebalancing, topic/ACL setup,
or durable Redpanda behavior. Milestone 6 remains incomplete until the live adapter, isolated broker
tests, and replay-driven persisted risk update pass.

## Milestone 7 — Airflow and adapters

- [x] Add four typed, offline-first job wrappers over the existing data, ML, and AI CLIs.
- [x] Derive deterministic configuration hashes and UUIDv5 run identities.
- [x] Enforce process-local duplicate suppression, bounded execution, dry-run, timeout,
  cancellation, sanitized failures, and observable run counts/statuses.
- [x] Add guarded optional Airflow DAG discovery that degrades to `scheduler_unavailable`.
- [ ] Exercise the DAGs against a real Airflow scheduler and durable metadata/run store.
- [ ] Add database ingestion/upsert scheduling after the PostgreSQL critical path exists.

Verified scheduler gates:

```text
.venv\Scripts\pytest.exe -c apps/scheduler/pyproject.toml apps/scheduler/tests -q
# exit 0; 37 passed

.venv\Scripts\ruff.exe check apps/scheduler
.venv\Scripts\mypy.exe --config-file apps/scheduler/pyproject.toml apps/scheduler/src apps/scheduler/tests
# both exit 0; mypy checked 18 source files

.venv\Scripts\uv.exe --cache-dir .uv-cache build --package quantops-scheduler --offline
# exit 0; sdist and wheel built
```

The tests execute the real existing pipeline, ML, and AI CLI boundaries without network access.
No active Airflow service, cross-host idempotency, or database ingestion is claimed.

## Milestone 8 — ML lifecycle

- [x] Build ten point-in-time risk-regime features with explicit provenance and leakage tests.
- [x] Implement a documented deterministic rule baseline and pure-Python K-Means candidate.
- [x] Use chronological partitions and report every fixed seed under a median-validation policy.
- [x] Evaluate macro F1, adjusted Rand index, stress false-negative rate, and calibration error.
- [x] Enforce automated promotion gates, retain the baseline on rejection, and generate a model card.
- [x] Produce deterministic, content-addressed lifecycle artifacts with dataset and code revisions.
- [x] Monitor PSI, missingness change, and Jensen-Shannon regime drift.
- [ ] Exercise the optional MLflow adapter against a real tracking service.
- [ ] Expose the lifecycle catalog and active model through the application API.

Verified ML gates:

```text
.venv\Scripts\pytest.exe -c ml/pyproject.toml ml/tests --cov=quantops_ml --cov-branch -q
# exit 0; 42 passed; 93% combined branch coverage

.venv\Scripts\ruff.exe check ml
.venv\Scripts\ruff.exe format --check ml
# both exit 0; 25 files formatted

.venv\Scripts\mypy.exe --config-file ml/pyproject.toml -p quantops_ml -p ml.tests
# exit 0; 24 source files, no issues

.venv\Scripts\uv.exe build ml --offline
# exit 0; sdist and wheel built
```

The lifecycle produced 462 feature rows from the canonical synthetic dataset. Seed `7` was selected
by the declared median-validation policy, not by test performance. The candidate failed relative
macro-F1 and calibration gates, so `rule-baseline-v1` remains active. Operational drift was
detected and MLflow was truthfully reported as disabled. Two consecutive runs at code revision
`72cfa241760ffb02e682ef58caab176bedab41d1` produced artifact hash
`0b0738757fbade763be9688c60592c33c9b2978114c2f79daf7e7a3f8081cb52`; the second changed zero of
ten files. Milestone 8 remains incomplete until the real MLflow profile and API catalog are proven.

## Milestone 9 — grounded AI

- [x] Define frozen, portfolio-scoped evidence, request, brief, refusal, and trace schemas.
- [x] Implement a fixed ten-tool read-only protocol with call, time, and response-size budgets.
- [x] Provide a useful no-key deterministic provider and an isolated optional OpenAI-compatible port.
- [x] Add bounded workflow, one repair, deterministic fallback, and safe refusal behavior.
- [x] Add approved-scope keyword retrieval with prompt-injection isolation and relevance thresholds.
- [x] Validate schemas, citations, evidence scope, canonical numbers/rounding, and prohibited content.
- [x] Version 44 labeled evaluation cases covering every one of the 20 required categories.
- [x] Store a machine-readable evaluation report and document the system boundary.
- [ ] Exercise pgvector retrieval and the optional provider against configured external services.
- [x] Expose deterministic briefs, structured refusal, and evaluations through the application API.
- [ ] Connect the generated/live UI client to the API brief endpoints.

Verified grounded-AI gates:

```text
.venv\Scripts\pytest.exe -c packages/ai_engine/pyproject.toml packages/ai_engine/tests \
  --cov=quantops_ai --cov-branch -q
# exit 0; 110 passed; 97% combined branch-aware coverage
# citation and numerical validator modules: 100% statements and branches

.venv\Scripts\ruff.exe check packages/ai_engine
.venv\Scripts\ruff.exe format --check packages/ai_engine
# both exit 0; 25 files formatted

.venv\Scripts\mypy.exe --config-file packages/ai_engine/pyproject.toml \
  -p quantops_ai -p packages.ai_engine.tests
# exit 0; 24 source files, no issues

.venv\Scripts\uv.exe build packages/ai_engine --offline
# exit 0; sdist and wheel built; wheel contains evals/v1/cases.jsonl

.venv\Scripts\python.exe -m quantops_ai evaluate \
  --cases packages/ai_engine/evals/v1/cases.jsonl \
  --output $env:TEMP\quantops-ai-evaluation-root.json
# exit 0; 44 passed, 0 failed across 20 categories
```

All deterministic schema, citation, numerical, refusal, tool-selection, and groundedness rates were
`1.0`; 23 tool calls were made. Seven deliberately invalid-provider cases used the safe fallback.
External cost/token fields are null because no provider call occurred. Evaluation latency is a
local observation and is not a portable benchmark. API integration additionally verifies auth,
idempotency/conflict, rate limiting, unknown scope, deterministic refusals with zero tool/provider
calls, and synchronous evaluation. Milestone 9 remains incomplete until live UI client integration
and configured pgvector/external-provider profiles are separately proven.

## Milestone 10 — read-only MCP

- [x] Use the official Python MCP SDK `1.28.1`, capped below its future v2 boundary.
- [x] Expose exactly three read-only tools over the existing application-service read methods.
- [x] Expose one fixed, bounded risk-methodology resource through local stdio transport.
- [x] Validate UUID and literal demo scope and cap reads at one second and responses at 32 KiB.
- [x] Return structured synthetic/no-advice outputs with evidence identity where applicable.
- [x] Prove the exact tool/resource surface, read-only annotations, no audit mutation, invalid-scope
  rejection, injection-as-data behavior, timeout/size failure, and stdio client/server operation.
- [x] Document package-level threats, explicitly absent capabilities, and remote-transport gaps.

Verified MCP gates:

```text
.venv\Scripts\pytest.exe -c apps/mcp_server/pyproject.toml apps/mcp_server/tests -q
# exit 0; 10 passed, including an actual stdio client/server exchange on protocol 2025-11-25

.venv\Scripts\ruff.exe check apps/mcp_server
.venv\Scripts\ruff.exe format --check apps/mcp_server
# both exit 0; 10 files formatted

.venv\Scripts\mypy.exe --config-file apps/mcp_server/pyproject.toml \
  -p quantops_mcp -p apps.mcp_server.tests
# exit 0; 9 source files, no issues

.venv\Scripts\uv.exe build apps/mcp_server --offline
# exit 0; sdist and wheel built
```

The allowlist contains `get_latest_portfolio_risk`, `get_snapshot_evidence`, and
`list_system_scenarios`; no write, recompute, scenario-run, shell, filesystem, arbitrary URL,
environment, raw database, prompt, sampling, or arbitrary-resource capability exists. Milestone 10
is complete for the required local stdio boundary. Authenticated multi-tenant remote transport is a
future design and is not claimed.

## Milestone 11 — operations and infrastructure

- [x] Document system, batch, streaming, risk/evidence, AI, and ML architecture flows.
- [x] Add eight incident runbooks with detection, impact, diagnosis, safe mitigation, recovery, and
  verification.
- [x] Add explicit backup/restore guidance, migration policy, a blameless sanitized postmortem
  template, and an observability contract for the deferred telemetry profile.
- [x] Keep API image multi-stage/non-root and build the grounded-AI wheel before the dependent API.
- [ ] Add structured telemetry, bounded metrics, traces, and a verified optional observability profile.
- [ ] Run core/optional Docker profiles and verify health, readiness, and graceful shutdown.

Static Dockerfile tests cover the builder/runtime split, all five required workspace wheels,
grounded-AI evaluation-data inclusion, and non-root runtime identity. Docker remains unavailable in
this environment, so image build/start evidence is intentionally unchecked. Kubernetes/Terraform
remain P2 and no resource or paid service has been created.

## Milestone 12 — CI, security, and full testing

- [x] Add a deterministic high-confidence secret, sensitive-filename, and oversized-file scanner.
- [x] Test scanner behavior without rendering matched secret values.
- [x] Add a STRIDE-style threat model covering the required data, event, AI/MCP, supply-chain,
  container, denial-of-service, and financial-misinterpretation threats.
- [x] Record the minimum ADR set plus the local demo-auth boundary.
- [x] Map major engineering claims to inspectable files/tests/commands.
- [x] Add a statically validated, least-privilege ten-job CI workflow, dependency updates,
  evidence artifacts, isolated PostgreSQL migration job, dependency/SBOM gates, and container smoke
  definitions.
- [x] Observe the first GitHub-hosted CI run, network vulnerability audits, PostgreSQL service job,
  and Docker image smoke jobs after publication.
- [x] Complete automated browser accessibility and critical-path e2e tests on desktop/mobile Chromium.
- [ ] Complete live PostgreSQL/Redpanda and clean-room service tests.

Verified no-service repository gates after AI/stream/MCP integration:

```text
.venv\Scripts\pytest.exe -m "not integration and not e2e" -q
# exit 0; 428 passed, 1 integration test deselected, 20 subtests passed

.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# both exit 0; 187 files formatted

.venv\Scripts\python.exe scripts/docs_check.py
# exit 0; 45 Markdown files checked at the time of the gate

.venv\Scripts\python.exe scripts/security_scan.py
# exit 0; no high-confidence secret or hygiene findings
```

The scanner explicitly permits the committed 1.16 MiB canonical synthetic JSON fixture while its
manifest/hash checks remain authoritative; other repository files over 1 MiB fail the gate.

Final local service-free integration gate after scheduler, CI tooling, and portfolio images:

```text
.venv\Scripts\python.exe -m pytest -m "not integration and not e2e" -q
# exit 0; 468 passed, 1 integration test deselected, 20 subtests passed

.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# both exit 0; 210 Python files formatted

.venv\Scripts\python.exe scripts/typecheck.py
# exit 0; 11 isolated strict mypy groups passed

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# all exit 0; 14 Vitest tests; production build completed

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# both exit 0; 48 Markdown files; no high-confidence secret or hygiene findings
```

## Milestone 13 — portfolio polish

- [x] Replace the scaffold README with a product-oriented quickstart, demo story, architecture,
  feature evidence, methods/safety summary, observed status, and visible limitations.
- [x] Capture seven actual running-product images for the landing page, dashboard, scenario/stress,
  grounded brief, model/drift, and data-quality views.
- [x] Keep architecture diagrams, methodology, model/AI cards, engineering evidence, runbooks,
  threat model, and all ten required decision topics linked and factual, including MLflow
  reproducibility and safely optional infrastructure profiles.
- [x] Add the interview guide with pitch, walkthrough, demo, domain explanations, 30 technical
  questions, ten trade-off questions, concepts, and personal owner exercises.
- [x] Add a truthful AI-assisted-development record with observed verification, concrete corrected
  errors, review limits, and separate owner-review actions.
- [x] Complete automated browser accessibility and Playwright critical-path coverage.

## Milestone 14 — clean-room verification and publication

- [x] Run the strongest clean local service-free gate available in this environment.
- [x] Inspect repository images, lockfile, documentation, status, and high-confidence secret/hygiene
  results.
- [ ] Run the Docker/PostgreSQL/Redpanda/clean-checkout gates on a Docker-capable host.
- [x] Publish public `braundm/quantops-risk-platform`, configure `origin`, description, and ten concise
  repository topics, and push `main`; hosted CI passed at verified commit `4f7627b`.
- [x] Observe the initial hosted CI run to completion; do not create a release tag while the full
  Definition of Done remains open.

## Current blockers

- Docker is unavailable, so PostgreSQL/Redpanda integration gates cannot yet be claimed.
- GitHub Actions run `29694259171` passed on `main`, including the PostgreSQL migration and
  unprivileged API/frontend container smoke jobs.
- Local Docker remains unavailable, so the same service and container behavior cannot yet be
  reproduced on this workstation.

Scoped verification for the frontend container permission fix:

```text
pnpm --filter @quantops/web build
# exit 0; Vite 8.1.5 production build completed

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# both exit 0; 48 Markdown files; no high-confidence secret or hygiene findings
```

## Next work

Connect the generated TypeScript client to the live API boundary, then implement and verify the
PostgreSQL-backed critical application path and Redpanda adapter. On a Docker-capable clean host,
repeat migrations, persistence/Redpanda integration, image, and Compose smoke tests. Keep the
release tag and remaining service-dependent evidence unchecked until those gates pass.
# Additive Treasury and liquidity lab — 2026-10-10

Scope: preserve the current stock/investor work and add a bounded banking-risk demonstration,
without replacing the architecture or implementing every item in the imported LLM backlog.
The pre-implementation gap assessment and intentional deferrals are in `treasury-lab.md`.

Implemented: pure Decimal regular-bond pricing, Macaulay/modified duration, convexity and DV01;
signed/gross book aggregation; -100/-50/+50/+100/+200bp full repricing and position contributions;
absolute net DV01 limits; separate constant-ADV equity liquidation, participation choices,
dated-history validation, stale/insufficient states, coverage and liquidation limits; editable
`/treasury` UI, synthetic cases, read-only calculation endpoints and escaped HTML export with
complete reproduction inputs. No new dependency, migration or provider integration.

Observed verification:

```text
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -m "not integration and not e2e" -q
# exit 0: 598 passed, 1 deselected, 20 subtests passed (25.35 seconds)
# Includes 34 new Treasury/liquidity/API tests; no external provider calls required.

.venv\Scripts\python.exe scripts/typecheck.py
# exit 0: all 11 isolated strict groups passed

.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# exit 0: all lint checks passed; 238 Python files formatted

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web build
pnpm --filter @quantops/web test
# exit 0: ESLint, TypeScript/Vite production build, 3 Vitest files / 20 tests

pnpm --filter @quantops/web exec playwright test e2e/treasury.spec.ts --workers=2
# exit 0: 4 desktop/mobile tests, including automated accessibility checks and HTML download

pnpm --filter @quantops/web exec playwright test --workers=2
# exit 0: all 44 desktop/mobile regressions passed (1.8 minutes)

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# exit 0: 56 Markdown files; deterministic repository hygiene/secret-pattern gate passed

git diff --check
# exit 0: no whitespace errors
```

Initial failures were corrected: strict TypeScript flagged unchecked array access; report export
exposed a missing postponed type annotation import; Ruff found long strings/import ordering.
The first sandboxed Python test run stalled at the web client, and sandboxed pnpm could not resolve
the workspace path. Replacement checks ran outside that restriction. A subsequent pytest-cache
Windows permission failure was avoided with `-p no:cacheprovider`; test selection was unchanged.
The initial two report-download browser failures were resolved by the same report import fix;
the complete new-browser suite then passed. No tests were weakened.

Artifacts: `docs/images/quantops-treasury-lab.png` was captured from actual API-backed application
results and visually inspected. `quantops-treasury-report.html` was exported to the chat's artifact
folder, with synthetic provenance and reproduction inputs. Screenshot capture is opt-in through
`QUANTOPS_CAPTURE_TREASURY=1`; optional report retention uses `QUANTOPS_TREASURY_REPORT_PATH`.

`git status`, branch and diff were inspected. The current branch remains `agent/portfolio-polish`.
`gh pr view 11 --json title,body,headRefName,state,isDraft` failed to connect to `api.github.com`;
no remote verification, PR update, publication, merge or commit is claimed. Existing owner edits
remain in the working tree. Full release and external-service gates remain open.
# GitHub publication verification — 2026-10-12

The owner explicitly requested all current changes be published to the existing GitHub
repository. Publication uses `agent/portfolio-polish` and draft PR #11. Full release
Definition of Done and service-dependent gates remain open.

Observed commands and outcomes:

```text
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -m "not integration and not e2e" -q
# exit 0: 626 passed, 1 deselected, 20 subtests passed in 32.57 seconds
.venv\Scripts\python.exe scripts/typecheck.py
# exit 0: all 11 isolated strict groups passed
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# exit 0: ESLint, 23 tests in 4 files, TypeScript/Vite production build
pnpm --filter @quantops/web exec playwright test --workers=2
# exit 0: all 54 desktop/mobile browser tests passed in 2.3 minutes
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_security_scan.py -q
# exit 0: 4 passed, including the new large-catalog secret detection regression
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# exit 0: all checks passed; 255 files formatted
.venv\Scripts\python.exe scripts/docs_check.py
# exit 0: 59 Markdown files
.venv\Scripts\python.exe scripts/security_scan.py
# exit 0: no high-confidence secret or hygiene findings
```

Initial environment failures: sandbox blocked Git index writes and pnpm path resolution,
stalled Python web-client tests and prevented pytest temporary-directory creation.
Authorized elevated reruns succeeded. The initial tracked-file scan omitted untracked
files; after staging all files it correctly rejected the 6,864,239-byte public catalog.
Its documented reproducible source snapshot now has an explicit size exception, with
secret detection retained and regression-tested. One extra blank line in the stock
catalog was removed to satisfy Ruff format. No assertions or test selections were weakened.

## Imported portfolio risk analysis — 2026-10-12

Existing code/documentation were inspected before implementation: XTB parser/merger and
native valuation, public stock/FX adapters, investor-book accounting/TWR, fixed-unit history,
covariance, signed contributions, VaR/ES, scenarios, drawdown and report exports. The new
workflow extends the existing account UI and XTB API boundary; core calculations remain
framework independent. Methods, supported scope and explicit limitations are in
`imported-portfolio-risk.md`.

Observed verification:

```text
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -m "not integration and not e2e" -q
# exit 0: 654 passed, 1 deselected, 20 subtests passed in 66.12 seconds
# Earlier complete gate: 653 passed before the additional calendar-gap invariant.
.venv\Scripts\python.exe scripts/typecheck.py
# exit 0: all 11 isolated strict groups passed
.venv\Scripts\python.exe -m mypy --strict --config-file pyproject.toml --cache-dir .mypy_cache/typecheck/api apps/api
# exit 0: 64 source files, including final Decimal monetary outputs
.venv\Scripts\python.exe -m mypy --strict --config-file pyproject.toml --cache-dir .mypy_cache/typecheck/risk packages/risk_engine/src/quantops_risk packages/risk_engine/tests
# exit 0: 41 source files
.venv\Scripts\python.exe -m pytest -p no:cacheprovider apps/api/tests/test_health.py apps/api/tests/test_portfolio_risk.py apps/api/tests/test_portfolio_history_provider.py packages/risk_engine/tests/test_portfolio_history.py packages/risk_engine/tests/test_investor_book.py -q
# exit 0: 41 passed in 5.66 seconds after final amount/schema changes
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# exit 0: all checks passed; 261 files formatted
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# exit 0: ESLint, 23 Vitest tests in 4 files, TypeScript/Vite production build
# Vite reports an advisory main-chunk size warning above 500 kB; build succeeds.
$env:QUANTOPS_E2E_API_PORT='8002'; $env:QUANTOPS_E2E_WEB_PORT='4174'
pnpm --filter @quantops/web exec playwright test --workers=2
# exit 0: all 60 desktop/mobile browser tests passed in 3.6 minutes
pnpm --filter @quantops/web exec playwright test e2e/portfolio-risk.spec.ts --workers=2
# exit 0: final 6 desktop/mobile risk tests passed in 28.5 seconds with Decimal API amounts
.venv\Scripts\python.exe scripts/docs_check.py
# exit 0: final check covered 60 Markdown files
.venv\Scripts\python.exe scripts/security_scan.py
# exit 0; additional scan_paths over git ls-files --cached --others --exclude-standard:
# zero findings, including all new untracked source files
git diff --check
# exit 0: no whitespace errors
```

New hand-checkable invariants cover identical assets/singular covariance, a negative hedging
contribution, cash, exact simultaneous price/FX loss, shock precedence, unbalanced weights,
variant/book isolation, missing histories, inconsistent FX, cash date/completeness, split
reconciliation, adjusted dividends, unknown/supplied ETF composition, missing benchmarks,
current valuation versus historical windows, unrecovered drawdown and multi-month gaps.
New browser checks exercise actual report import through analysis/scenario, independent
weight changes, report retention, source/partial states, API failure, accessibility,
mobile overflow, chart interaction and report download.

Initial findings were corrected without weakening assertions: Python typing/import/format
issues, an unused test-loop index and an exact-label selector that could not select the
account-currency dropdown. The first complete browser run had those two selector failures
and one existing mobile context-teardown timeout (57 passed, 3 failed); the corrected six
new tests and then all 60 regressions passed. A formatter-diff header was briefly introduced
as a stray source line, caught at collection/lint, removed and followed by the successful
654-test rerun above. UI screenshots were visually inspected on desktop and mobile.

One read-only actual provider call fetched AAPL.US plus USD/PLN for 2025-10-01 through
2026-10-09: 229 aligned observations, latest shared date 2026-10-08, no source failures.
The provider result was not packaged as a synthetic fixture or claimed to satisfy the
252-observation risk requirement. The running API was restarted; through localhost:5173,
health, risk-example and risk analysis returned HTTP 200, complete status and 339 synthetic
return observations. No live source is required by unit/browser tests.

The repository secret/hygiene gate passed, including a separate scan of tracked and new
untracked files (zero findings). No private reports or credentials were introduced. The
working changes remain local on `agent/portfolio-polish`; no commit, push, merge or release
tag is claimed for this scope. Remaining release/service-dependent gates remain open.

## Beginner-oriented risk interface — 2026-10-12

Replaced the up-front technical form with a short data/cash step and four question-based action
cards. Clicking an action calculates through the existing API and opens the corresponding
result. Added hypothetical 10%/20%/35% equity/ETF decline presets, signed scenario and position
bars, allocation/comparison charts and deterministic metric-grounded conclusions. Advanced JSON,
source metadata, VaR/ES definitions and attribution tables are expandable. Data coverage gates,
Decimal financial calculations, exact weight totals and report isolation are preserved.

Verification for this UI-only follow-up:

```text
pnpm --filter @quantops/web test
# exit 0: 23 tests in 4 files, 10.62 seconds
pnpm --filter @quantops/web lint
# exit 0: zero warnings
pnpm --filter @quantops/web build
# exit 0: TypeScript and production build; existing >500 kB chunk advisory remains
$env:QUANTOPS_E2E_API_PORT='8002'; $env:QUANTOPS_E2E_WEB_PORT='4174'
$env:QUANTOPS_CAPTURE_RISK='1'
pnpm --filter @quantops/web exec playwright test e2e/portfolio-risk.spec.ts --workers=2
# exit 0: 6 desktop/mobile tests, 40.1 seconds
```

Browser evidence includes all four action paths, hidden advanced controls, charts and grounded
conclusions, a hand-checkable 400 PLN preset loss with unchanged cash, exact terminal value,
stale result removal after edits, invalid weights, insufficient data, API errors, accessibility,
saved-report isolation and mobile overflow. Desktop/mobile screenshots were visually inspected.
The earlier six-test pass took 38.7 seconds before the final preset assertion was added. No
engine or API change was made in this follow-up, so backend suites were not repeated.

Final build and ESLint passed after the last wording adjustment. Documentation validation
passed for 60 Markdown files; `python scripts/security_scan.py` and a separate `scan_paths`
over tracked plus untracked files found zero issues. `git diff --check` passed (only the
existing OpenAPI CRLF normalization advisory). Local HTTP checks returned 200 for `/`, the
updated frontend component and `/api/v1/health`; the served component contains the new stress
action. The first sandboxed socket check was denied by OS permissions; the authorized
unsandboxed read-only loopback check above succeeded. No publication was performed.

## Saved-account analysis without cash entry — 2026-10-12

Removed the manual cash form from the risk screen. The selected saved account is now the
explicit default data source, with its identity and position date displayed. An analysis
action obtains actual current holdings from the book analyzer and fetches required price/FX
histories automatically. Closed-only instruments are excluded from fetching. Cached histories
are reused within the account; a new import/account selection clears histories and results.
The optional synthetic example is behind a disclosure and never silently substitutes the book.

Added explicit `securities_only` API scope, echoed in results and labeled in coverage. It excludes
unknown account cash rather than assuming zero or using cash movements as a balance. The API
default `full_account` mode retains confirmed cash requirements. Securities scope rejects
account cash payloads and retains history, supported-position and quantity-date gates.

Initial verification: 25 scoped API/OpenAPI tests passed in 3.53 seconds; strict API mypy passed
for 64 files; Ruff lint and format check passed for both changed Python files. Frontend build,
ESLint and 23 unit tests passed (5.23 seconds for Vitest). Six desktop/mobile browser checks
passed in 32.1 seconds, then 37.4/37.1 seconds after account-switch/cache assertions and the
book-change reset. Final verification below also covers the explicit stale-price explanation.

Restarted only the matching local QuantOps API process. A read-only check through the running
frontend fetched all nine public histories for the saved synthetic account. No provider symbol
failed; the latest common date was 2026-10-08, before its 2026-10-09 position snapshot. The API
correctly returned `securities_only`, `partial_or_insufficient` and no portfolio metrics. The
screen now explains that exact date mismatch rather than asking for cash or inventing prices.

Final verification after the explanatory date message: all six desktop/mobile risk browser
checks passed in 39.8 seconds, including actual import, no cash fields, one automatic history
fetch, reuse on a second action, exact selected account in the request, account switching,
history cache reset and blocked metrics when prices precede the position snapshot. Production
build and ESLint passed; the existing >500 kB main-chunk advisory remains. Documentation check
passed for 60 Markdown files. Repository security scanning plus tracked/untracked `scan_paths`
found zero issues; `git diff --check` passed. No commit or publication was performed.
