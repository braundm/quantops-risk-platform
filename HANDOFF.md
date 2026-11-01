# QuantOps handoff

Last updated: 2026-11-01
## C++ Monte Carlo portfolio simulation — 2026-11-01

The owner requested implementation of the illustrated portfolio Monte Carlo module
in C++. Added an optional C++17 shared library in native/monte_carlo, a no-download
CMake build helper, a bounded ctypes adapter and POST /api/v1/xtb/monte-carlo.
The existing imported-allocation checks remain authoritative. Calibration uses
aligned adjusted base-currency log returns; native simulation uses correlated GBM,
an explicit assumed drift, fixed holdings, repeatable seeds, pointwise bands,
sample paths and signed VaR/fractional-tail ES. No silent Python fallback exists.

In Analiza ryzyka → Możliwe spadki, calculate a complete allocation first and run
Monte Carlo. The panel includes horizon/path/drift/allocation controls, path and
histogram views, keyboard checkpoint readings, synthetic labels and JSON export.
Changing simulation controls clears only its own result, not the portfolio analysis.
Existing account storage and the owner's earlier uncommitted work are preserved.
See docs/monte-carlo.md for build instructions, assumptions and limits.

Verified locally on Windows/MSVC: Release build and CTest, 18 new API/adapter tests,
241 focused risk/API tests plus 14 subtests before the final loader-only regression
was added, strict typing, frontend build/lint, 23 frontend unit tests, and 10
desktop/mobile Monte Carlo and existing risk browser tests including accessibility.
Final missing-export loader handling is covered by the passing 18-test module suite.
Exact commands and caveats are in docs/progress.md. Native binaries are ignored;
other deployment hosts must build their own library. The owner authorized committing
and publishing this module on 2026-11-01 as Dominik Braun, using the configured
GitHub noreply address. Earlier overview/benchmark edits remain outside this commit.


## Owner-authorized review and GitHub update — 2026-10-31

The owner explicitly requested a final review, commit and GitHub publication of the
current work. This authorizes updating the existing `agent/portfolio-polish` branch and
draft PR #11 despite the earlier general publication gate; it does not mark the original
release Definition of Done complete or authorize a release tag/merge.

The review corrected an erroneous empty-holdings message on Overview and separated the
latest quantity-changing event date from the original split-review anchor. Reconstructed
holdings and subsequent partial closures now block prices older than their latest state,
while an earlier split still requires reconciliation. The API exposes `quantity_date`.
Regression tests cover both the stale/current execution cases and later partial closures.

A dependency audit found 19 advisory entries affecting four locked packages. Updated
certifi to 2026.10.23, filelock to 4.2.5, msgpack to 1.2.4 and the MCP SDK to 1.30.0;
minimum-version constraints prevent selecting the vulnerable versions again. After the
upgrade, 674 Python tests plus 20 subtests and all 11 strict typecheck groups passed;
the full hashed Python audit and production frontend audit both reported no known
vulnerabilities. Frontend unit/build/lint and all 62 browser regressions passed in this
publication review. Exact commands are maintained in `docs/progress.md`.

## Tabbed equity risk dashboard — 2026-10-31

The owner requested a polished, interactive risk workspace for fully funded equities.
The risk tab now starts with Overview and a descriptive 0–100 risk index, followed by
Concentration, Diversification, Possible declines, History, Allocation comparison and
Data/methodology. Interactive company selection, exposure bars, a correlation heatmap,
capital/risk contribution comparisons, selectable scenarios and a drawdown chart share
the same returned analysis. Keyboard navigation and mobile layouts are covered.

The UI explicitly analyzes the equity slice (`securities_only` / `equities_only`).
Omitted ETFs/other instruments are enumerated; unknown cash is excluded. The API keeps
its original default mixed scope. The new synthetic demonstration has five equities,
invented histories and explicitly synthetic issuer metadata, without changing reports.

`equity-diagnostics@1.0.0` computes HHI, effective holdings, documented issuer aggregation,
weighted correlation, diversification ratio, single-company -50% stresses and a bounded
four-component research score in the pure risk engine. Thresholds and 25% weights are
visible and versioned. The score is not a probability or guarantee and omits fundamentals,
liquidity and full sector/economic risk. Short samples, stale real valuations and non-equity
allocations receive null scores with typed statuses. Read `docs/equity-risk-dashboard.md`.

Verified: 671 service-free Python tests plus 20 subtests, 23 frontend unit tests, all 62
desktop/mobile browser checks, strict risk/API typing (43/65 files), frontend lint and
production build. OpenAPI was regenerated and its contract gate passed. Browser checks
include axe, keyboard tabs, exact scenario loss, stale-result removal, unknown metadata,
account isolation and report export. The existing main-bundle size advisory remains.
The actual localhost:5173 API proxy returned a complete five-equity synthetic analysis
and score 44 after restarting only the verified workspace API process. Final desktop/mobile
visual captures were inspected; the additional two focused browser checks passed in 11.6s.
Documentation (61 files), tracked/untracked secret/hygiene scanning and whitespace checks
passed. Exact commands and preview paths are recorded in `docs/progress.md`.

Existing owner changes remain in place. No commit, GitHub publication or release tag
was performed in this update; the original release Definition of Done remains open.

## Saved-account analysis without cash entry — 2026-10-12

The default risk screen uses the selected saved account directly. It displays account identity
and the position snapshot, removes cash amount/date/confirmation fields, and fetches price/FX
histories automatically on the first analysis action. Histories come from current holdings
returned by the existing book analyzer, excluding closed-only instruments. Changing accounts
or importing a new book clears results, histories and example state. The separate synthetic
example is behind an explicit optional disclosure.

The API adds an explicit `securities_only` scope, returned in reports and visibly labeled.
Account cash is excluded rather than inferred from movements or set to a fictitious zero.
`full_account` remains the default API scope and retains confirmed, dated cash gates.
Securities-only requests reject account cash inputs and still require complete supported
positions, reconciled quantities and adequate source dates. Variant cash reallocates analyzed
capital hypothetically; it is not the account's unknown cash balance.

Verified: 25 scoped API/OpenAPI tests, 23 frontend unit tests, strict API typing (64 files),
frontend lint/build and desktop/mobile browser checks. The local API was restarted. An actual
public-source check fetched all nine saved demo histories, but the latest shared valuation
was 2026-10-08 before the 2026-10-09 quantity snapshot. The insufficient state is correct and
is now explained directly with both dates. No complete result for that snapshot is claimed.
See progress for final verification evidence. Changes remain local.

## Beginner-oriented risk interface — 2026-10-12

The risk workspace now starts with cash/data preparation and four question-based actions:
stress testing, diversification, historical losses and an independent allocation comparison.
Each action runs the existing API calculations and selects its result. Hypothetical equity/ETF
decline presets of 10%, 20% and 35% keep FX unchanged; custom combined scenarios remain available.
Results include signed loss/position bars, allocation and comparison charts, and deterministic
plain-language explanations grounded in returned metrics. JSON, VaR/ES, correlation matrices,
provenance and statistical details remain expandable. Missing coverage still blocks full results.

Verified for this presentation-only follow-up: 23 frontend unit tests, six desktop/mobile risk
browser checks, TypeScript production build and ESLint. The browser checks validate an exact
400 PLN preset loss on 4,000 PLN equity plus 100 PLN cash, chart/conclusion visibility, hidden
advanced controls, stale-result removal, account isolation and accessibility. Desktop/mobile
screenshots were inspected. See `docs/progress.md` for commands and final hygiene checks.
The financial engine and API contracts are unchanged by this follow-up. Changes remain local.

## Imported portfolio risk workflow — 2026-10-12

The owner requested a connected import-to-risk-to-scenario-to-variant workflow. The existing
XTB workspace now includes **Analiza ryzyka**, using confirmed report holdings, adjusted
price history, dated FX and explicitly confirmed cash. The stateless service composes the
existing covariance, correlation, signed Euler contribution, VaR/ES and drawdown functions.
It adds source-aware exposure metadata/ETF overlap, common-period benchmark comparison,
historical/combined/user shocks, loss tolerances and independent weight variants at equal
capital. Actual transaction-based TWR remains at `/investor` and gains episode/calendar
performance summaries; it is never inferred from imported snapshots.

Read `docs/imported-portfolio-risk.md` for methods, contracts, limits and a reproducible
synthetic walkthrough. Missing data or unsupported instruments block whole-account claims.
ETF composition/economic exposure remain unknown unless sourced inputs are supplied. CFD,
direct-bond and derivative risk, automatic corporate-action ledger reconciliation, secure
durable storage, automatic verified ETF feeds and account aggregation remain separate work.
The analysis UI supports one cash currency per selected account; the API supports multiple
explicit balances. Histories/drafts are held in component memory and exported explicitly.

Verified: 654 service-free Python tests and 20 subtests; 23 frontend unit tests; 60 complete
desktop/mobile browser regressions; all 11 strict typecheck groups. Final API/risk typing,
OpenAPI and 41 scoped Python checks passed after Decimal monetary outputs were added.
Exact commands, initial corrected failures and final UI checks are in `docs/progress.md`.
One actual public AAPL/USD-PLN fetch succeeded with 229 aligned observations through 2026-10-08;
this is not enough to enable the default 252-observation VaR gate. Synthetic examples remain
explicitly marked and never overwrite stored reports. The local API was restarted and the
frontend proxy's example/analysis returned HTTP 200. No commit or publication was performed
for this new work, and the original release Definition of Done remains open.

## Owner-authorized GitHub publication — 2026-10-12

The owner explicitly requested publication of all current repository changes, overriding
the earlier publication restriction for this update. Use the existing
`agent/portfolio-polish` branch and draft PR #11; the original release Definition of Done
remains open. The snapshot includes the local stock workspace, report imports, public
instrument catalog, Treasury lab and visibly synthetic local demo accounts.

Pre-publication checks passed: 626 service-free Python tests and 20 subtests, 23 frontend
unit tests, all 11 strict Python typecheck groups, frontend lint and production build.
The security scan now recognizes the reproducible 6.9 MB public broker catalog as a
reviewed data artifact while retaining secret-pattern scanning; four scanner tests passed,
including a regression proving that the size exception still detects secrets.
Ruff lint/format and documentation checks passed; all 54 desktop/mobile browser tests
passed in 2.3 minutes. See `docs/progress.md` for exact evidence.
No release tag or production-readiness claim is authorized.

## Default synthetic local accounts — 2026-10-11

Owner requested `admin`/`admin` empty and `admin1`/`admin1` populated from the attached
`quantum_ops_portfolio_test.xlsx`. Development initialization is loopback-only, idempotent,
preserves existing login/UUID owners and report edits, and never enables server admin privileges.
Normal registration still requires ten-character passwords. Two demo slots supplement ten custom
profiles. Login screen and active demo profiles visibly identify the synthetic data.

The workbook was read as data, retaining 20 open lots / 9 instruments, 26 closed positions and
76 cash operations, account PLN, snapshot 2026-10-09T20:00:00Z. Its explicitly synthetic financial
sections permit a normalized source fixture; prices are not seeded as verified provider marks.
Parser now handles its known Sources provenance sheet and Open positions total footer.
`scripts/build_local_demo.py` rebuilds the seed through the existing import pipeline and refuses
unmarked sections. See `docs/local-workspace.md` for credentials, provenance and regeneration.

Verified: 21 parser/API tests; 23 frontend unit tests; 10 desktop/mobile browser tests covering
default logins, separation, retained edits, onboarding and existing XTB import; ESLint, TypeScript,
production build, Ruff and mypy passed. Mobile portfolio screenshot was visually inspected.
The running API was restarted and the actual workbook was previewed through localhost:5173's proxy.
Security/documentation gates and exact command evidence are recorded in `docs/progress.md`.
No publication or commit was made; pre-existing owner changes remain in the working tree.

## Local login, optional onboarding and workspace layout — 2026-10-11

The owner requested login/password registration, skippable questionnaire, broker setup
and a more coherent layout. `/` and `/stocks` now provide that flow and six distinct
views: Overview, Portfolio, Brokers/accounts, Import, History and Settings. Questionnaire
skip is explicit and reversible from Settings; calculations and imports do not depend on it.
Broker selection supports XTB and Bossa together; only the XTB importer is enabled.
Adding an account opens Import; confirmed imports open Portfolio. Existing event and
valuation behavior is retained. Legacy unprotected profiles can gain credentials while
preserving their UUID and report storage. Profile exports omit credential verifiers.

Local passwords use Web Crypto PBKDF2/SHA-256 with 600,000 iterations and random 128-bit
salts. Plaintext passwords are not stored or sent to the API. A sessionStorage identifier
provides a local UI gate, with logout and password verification. This is deliberately
documented as a local prototype: client state is editable, reports remain unencrypted,
there is no server authentication, ownership enforcement, email reset or synchronization.
Do not deploy this as secure account access. See `docs/local-workspace.md`.

Verified: TypeScript/production build and ESLint passed; all 20 existing frontend unit
tests passed. Eight desktop/mobile onboarding and XTB browser tests passed, followed by
four focused browser tests after the final questionnaire presentation adjustment.
Axe scans, overflow checks, secret/hygiene, docs and whitespace gates passed. Synthetic
screenshots were inspected. Existing local web/API servers still answer HTTP 200 at
`http://localhost:5173/` and its API proxy. No commit or publication was performed.

## XTB report-based accounts — 2026-10-11

The default workspace now replaces manual/search-based additions with XTB report import.
It supports multiple isolated local accounts, official broker logos, CSV paste/upload,
XLSX and ZIP, preview/confirmation, deduplication and atomic conflict rejection.
Bossa is selectable but clearly marked as awaiting an importer. Earlier manual holdings
remain downloadable and are not automatically combined. No broker connection was added.

Open-position snapshots and complete execution ledgers retain unsold stocks/ETFs and
reconcile partial sales. Closed-only reports leave current holdings unknown. The supplied
private ZIP was checked directly: it contains one XLSX with closed positions and cash
operations and no open positions. No private source file or account data was checked in.
CFD records remain separate from physical positions and have no fabricated spot valuation.

Imported physical quotes reuse the public daily-close adapter, with catalog/listing and
currency validation, explicit refresh and optional 15-minute visible-page refresh.
Outages retain prior prices; native-currency totals and split review are implemented.
Limits include 20 instruments per refresh, no GBX scaling, no imported-portfolio VaR/ES
integration, no CFD contract risk, no durable authenticated storage or backup restore.
See `docs/xtb-report-import.md` for supported formats and recommended next work.

Verified final state: 623 service-free Python tests passed (1 deselected, 20 subtests),
strict API/risk typing for 67 files, Ruff, frontend lint/production build and 4 browser
tests across desktop/mobile with axe passed. Security, documentation and whitespace
checks passed. Exact outcomes and corrected initial failures are in `docs/progress.md`.
Existing unrelated owner work is preserved; nothing was committed or published.

## Public Bossa / XTB instrument catalog — 2026-10-11

The owner requested every Bossa and XTB instrument, including equities and derivatives.
The new `/instruments` page and two `/api/v1/broker-catalog` GET routes provide 18,409
validated public reference entries: 12,599 XTB Poland, 5,632 dated Bossa foreign entries
and 178 BOSSAFX CFD specifications. Search, type/broker/market filters, pagination,
source dates, counts, hashes and distinct equity/CFD identities are implemented.
The packaged data requires no live provider for application startup or tests.

The complete request is **not fulfilled**: eight public Bossa domestic groups returned
empty lists, including options and futures. These are marked unavailable, not complete.
An official export or recovered public feed is required for those entries. The existing
40-stock valuation flow is preserved; broad catalog membership does not implement
portfolio valuation, live quotes, option Greeks, margin or financing for these entries.
No broker account connectivity, publication or commit was added. See `docs/broker-catalog.md`.

Verified: 22 scoped Python tests, strict API/tooling typechecks, frontend lint/build,
four new desktop/mobile catalog tests with axe scans, and four existing stock browser
tests passed. Ruff, documentation and security gates passed; exact commands and corrected
initial failures are recorded in `docs/progress.md`. Other pre-existing owner edits remain.

## Additive Treasury and liquidity lab — 2026-10-10

The owner requested small, useful additions from an external LLM proposal, with a banking
internship demonstration in mind. Existing uncommitted stock-workspace changes were preserved.
The new `/treasury` route adds editable regular fixed-coupon bonds, Macaulay/modified duration,
convexity, signed/gross DV01, five full-repricing rate shocks, net DV01 limits, a separate
supplied-volume equity liquidity book, data-quality gates and a self-contained HTML export.
The stock page and research sidebar link to the lab. No migrations or new dependencies were added.

All examples are synthetic; user inputs remain unverified. No live yield, historical crisis replay,
durable account storage, regulatory IRRBB compliance or bank-wide NII/EVE is claimed. The requested
feature gap matrix, methods, three reproducible illustrations and interview walkthrough are in
`docs/treasury-lab.md`. New endpoints are `POST /api/v1/treasury/analyze` and
`POST /api/v1/treasury/report`; OpenAPI and route-contract tests include both.

Verified: 598 Python tests plus 20 subtests passed, one service integration test deselected;
all 11 strict typecheck groups passed; Ruff lint and formatting passed. Frontend lint/build and
20 Vitest tests passed; all 44 desktop/mobile browser regressions passed, including the four new
Treasury tests and axe checks. Documentation (56 Markdown files), security scan and diff whitespace
checks passed. Exact commands and initial corrected failures are in `docs/progress.md`.
The actual application screenshot is
`docs/images/quantops-treasury-lab.png`; a sample HTML report was exported to the chat artifact folder.

Work remains local and uncommitted on `agent/portfolio-polish`. Reading PR #11 through the local
GitHub CLI failed due to network connectivity; its body and remote branch were not modified.
The original release Definition of Done remains open.

## Stock-only personal start — 2026-10-05

The latest local changes make `/` and `/stocks` a portfolio-tracking start: create a browser-local
user, complete risk and instrument-knowledge questions, then manually add existing stock holdings
to an empty portfolio. The fixed catalog contains 20 US and 20 Polish equities. The previous
ledger remains at `/investor`, with its tests following that route. See `docs/stocks-start.md`.

The questionnaire tailors educational detail and flags willingness/capacity or liquidity issues;
it does not recommend assets. Current quantities, actual/estimated/unknown cost basis, dated
historical closes and per-position refresh are supported. Native USD/PLN totals remain separate.
CSV and broker imports, other instrument types and hosted accounts remain deferred in this flow.

Verification: 564 Python tests plus 20 subtests passed (one external-service test deselected),
strict API/risk typechecks passed, and frontend lint/build plus 20 Vitest tests passed. All 36 prior browser tests
passed; all four new desktop/mobile start tests passed after correcting test selectors, including
axe checks for the start, questionnaire and portfolio. Live Yahoo lookups returned valid closes
and currencies for all 40 catalog symbols; historical Apple and PKO reference dates were checked.
The full hosted Definition of Done remains open. These changes have not yet been committed.

## Investor workspace publication — 2026-10-05

The default `/` and `/investor` routes now provide a browser-local transaction ledger,
flow-adjusted performance, historical risk, diversification, named scenarios and JSON backup/restore.
Bundled sourced historical closes are identified separately from fictional example ownership.
The previous workshop remains at `/personal`; local onboarding, cash envelopes and the synthetic
forecast calibration quiz are included. See `docs/investor-workspace.md` for accounting conventions,
derivative assumptions, supported instruments and storage limitations.

Pre-publication verification passed: 549 Python tests and 20 subtests (one integration test
deselected), 11 strict typecheck groups, Ruff lint/format, frontend lint, 20 Vitest tests,
production build and all 36 desktop/mobile Playwright tests with two workers. Documentation
checks passed for 53 Markdown files on the final rerun; the deterministic security scan passed. Exact commands and
initial environment failures are recorded in `docs/progress.md`.

The owner authorized committing and publishing these local changes to the existing PR #11 branch
on 2026-10-05. Hosted CI for the new commit must be checked separately. Hosted tenant persistence,
broker adapters, full retail MVP completion and the original Definition of Done remain open.
Browser-local transaction/scenario persistence does not establish production readiness.

## Synthetic forecast quiz

The personal workspace includes a market-direction calibration quiz inspired by workshop-style
forecast drills: 12 synthetic charts ending at NOW, up/down + confidence, periodic future reveal,
and a closing calibration summary. Futures stay server-side until reveal (HMAC cursor). Distinct
from the ten-step education lab; both are synthetic and non-advisory.

## YNAB-style cash envelopes

The personal workspace now includes a local zero-based cash budget (YNAB-style envelopes): monthly
income, Ready-to-Assign, category groups, assigned/spent/available, “assign the rest”, and optional
import of portfolio cash. State is browser-local per user id and clears with logout/delete. It is a
liquidity planning aid, not investment advice or a transaction ledger. Retail e2e helpers enter
through the local login and default-settings gate.

## Retail history, education and visual refinement

The personal workspace now includes aligned historical price/FX CSV preview, VaR/ES, volatility,
drawdown, correlation and a keyboard-accessible chart. It reprices current fixed quantities, not
investor transaction performance. Insufficient/inconsistent history suppresses precise metrics.
An optional survey checks loss willingness/capacity and applies a personal concentration threshold.
A separate cost budget excludes fees already embedded in prices. The ten-step synthetic education
exercise reveals future observations only after a decision and reports costs and Brier calibration.
The UI has a refined green/cream palette, clearer cards, responsive chart panels and a scrollable
sidebar. Delete clears the portfolio and all added session panels. Method details and exclusions
are maintained in `docs/retail-first-flow.md`.

Python verification: 531 tests plus 20 subtests passed, one PostgreSQL integration test skipped;
strict typechecks passed across 11 groups. Frontend lint, 14 Vitest tests and build passed.
Desktop/mobile Playwright coverage passed all 28 tests, including automated accessibility checks.
Documentation checks passed for 49 Markdown files; repository-wide Ruff checks passed.
Updated Python and production Node audits found no known vulnerabilities. The browser CI job now installs
the locked Python API required by its tests. The local Python environment was restored to 3.12
after a locked-process interruption; the temporary repair environment was removed.

Hosted application, PostgreSQL, frontend and security gates passed at `6fd665f`. The container job
found duplicate independently resolved Pydantic wheels. The follow-up Dockerfile uses one locked,
non-editable API dependency environment and retains the unprivileged runtime. Hosted run
`37212261658` passed all ten jobs at `2cb2515`, including API/frontend container builds and smoke
tests. Docker remains unavailable locally; the container evidence is from GitHub Actions.

Remaining work includes transaction/flow history, persisted named scenarios, authenticated durable
storage and any separately scoped read-only data adapters. The education cursor is intentionally
single-process and replayable; synthetic trials are not evidence of strategy performance. No full
retail MVP completion, external-service verification or production readiness is claimed.

## Retail flow added on 2026-10-04

The default `/` route now serves a Polish personal portfolio workspace connected to FastAPI.
The former landing page is preserved at `/research`; existing research routes and risk calculations
remain available. See `docs/retail-first-flow.md` for launch commands, the full CSV mapping, model
assumptions, local data handling and the actual/synthetic/deferred capability split.

Implemented and verified: manual current positions, atomic CSV preview/confirm, signed spot
valuation and exposures, concentration, combined asset/FX shocks, no/partial/full signed forward
comparisons with entry/holding estimates, before/after valuation, explicit local save/restore/delete,
readable report export and stale-result invalidation. Synthetic origin is retained in the example
CSV and modified fictional holdings. New portfolios require user FX; changing base currency clears
foreign rates instead of silently reusing rates with different units. The API is stateless and
rate-limited; it adds no hosted user accounts or PostgreSQL persistence.

Scoped gates: 190 API/risk Python tests and 14 subtests passed; one PostgreSQL test skipped because
no isolated database was configured. API/risk strict typechecks passed. Frontend lint, typecheck,
14 Vitest tests, production build and 22 desktop/mobile Playwright tests passed, including report
contents, CSV rejection, local data deletion and axe checks. Exact commands are in `docs/progress.md`.

The follow-up above adds historical risk, the optional survey and synthetic education. Transaction/
flow contracts and broker-specific read-only adapters remain separate deferred work.
This is a working retail application slice, not completion of the entire
retail MVP or the original master-spec Definition of Done. The owner explicitly authorized a Git
commit and GitHub publication on 2026-10-04, overriding the earlier publication restriction for
this change. Publish on the existing `agent/portfolio-polish` branch and update draft PR #11;
do not merge or create a release tag as part of this request.

## Previous research baseline (2026-07-19)

## Current state

The authoritative 2,442-line master specification was read in full. The repository now contains the
framework-free domain and risk cores, deterministic data/quality pipelines, PostgreSQL mappings and
migrations, a 31-route FastAPI surface, a responsive typed-demo UI, versioned events, broker-neutral
streaming, offline scheduling wrappers, a leakage-safe ML lifecycle, bounded grounded AI, and an
official-SDK read-only MCP server. The final local service-free gate passes 468 Python tests plus 20
subtests, strict typechecks across 11 isolated groups, 14 Vitest tests, 14 desktop/mobile Playwright
tests with axe scans, the frontend production build, documentation checks, and the repository
security scan.

The public repository is https://github.com/braundm/quantops-risk-platform. Local work is on
`agent/portfolio-polish`, tracking the same branch on `origin`; draft PR #11 contains the current
portfolio/documentation improvements.

Focused commits through `4f7627b` on `main` preserve the published implementation history. Use
`git log -1` on the active branch for its latest immutable SHA.

## Architecture in force

Use a modular monolith for synchronous behavior, framework-free domain/risk packages, and separate
workers only for replay, scheduling, or isolation. PostgreSQL is the designed source of record;
Redpanda, Airflow, MLflow, external LLM providers, and observability remain optional boundaries. The
current UI and API run deterministic local adapters independently, so live integration must not be
claimed.

Milestone 13 now includes `docs/interview-guide.md` and
`docs/ai/ai-assisted-development.md`; both separate observed Codex verification from personal owner
review and keep unavailable integrations explicitly qualified.

## Last successful local gates

```text
.venv\Scripts\uv.exe --cache-dir .uv-cache sync --locked --all-packages --offline
# exit 0; quantops-scheduler installed from the workspace

.venv\Scripts\python.exe -m pytest -m "not integration and not e2e" -q
# exit 0; 468 passed, 1 deselected, 20 subtests passed

.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# exit 0; 210 Python files formatted

.venv\Scripts\python.exe scripts/typecheck.py
# exit 0; 11 strict isolated mypy groups

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web test:e2e
pnpm --filter @quantops/web build
# exit 0; 14 Vitest tests; 14 desktop/mobile Playwright tests; Vite production build

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# exit 0; 56 Markdown files; no high-confidence secret/hygiene findings

.venv\Scripts\pytest.exe -c apps/scheduler/pyproject.toml apps/scheduler/tests -q
.venv\Scripts\uv.exe --cache-dir .uv-cache build --package quantops-scheduler --offline
# exit 0; 37 tests; sdist and wheel built
```

The current workstation uses bundled Git/Node/pnpm and workspace `uv`. GitHub CLI 2.96.0 is installed
at `C:\Program Files\GitHub CLI\gh.exe` and authenticated as `braundm`, although the current shell
does not include it in `PATH`. Docker, GNU Make, and Terraform remain absent from `PATH`.

## Honest blockers and limitations

- Docker-backed clean PostgreSQL, pgvector, Redpanda, image, and Compose gates were not runnable.
- GitHub Actions run `29694259171` passed on `main` after the unprivileged nginx cache/PID permission
  correction in commit `4f7627b`.
- Live Airflow/MLflow/provider/observability profiles and generated UI client integration remain
  unverified.
- The full master-spec Definition of Done remains open; do not create the `v0.1.0` release tag yet.

## Exact next action

Connect the generated TypeScript client and PostgreSQL-backed critical application path. On a
Docker-capable clean host, run the remaining Redpanda/clean-room gates and exercise the documented
backup/migration/observability procedures before creating a release tag or calling the project
complete.

## Working tree expectation

The current work belongs to `agent/portfolio-polish` and draft PR #11. Preserve `origin`, keep
commits narrowly scoped, and inspect `git status --short --branch` before future edits.
