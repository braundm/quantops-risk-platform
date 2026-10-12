# Local account onboarding and workspace navigation

The default `/` and `/stocks` routes now provide a local login/register screen followed by
an optional questionnaire, multi-select broker setup and report-based account management.
This is a browser-local prototype, not server authentication or a hosted account service.

## Flow

1. Register a display name, unique login and matching password. Login identifiers are normalized
   to lowercase and accept 3–40 ASCII letters, digits, dots, underscores and hyphens.
   Passwords accept 10–128 characters and preserve whitespace and case.
2. Skip the questionnaire immediately, or expand and complete it. A skipped questionnaire is
   recorded explicitly and does not block broker selection, imports, quotes or calculations.
   It can be completed or edited later from Settings. Answers are not a financial risk model.
3. Select one or both brokers. XTB supports import; Bossa selection is retained with an explicit
   unavailable-import status. The chosen brokers can be changed later without deleting reports.
4. Add each XTB account and import its report. Adding an account opens Import; confirming a
   report opens Portfolio. Preview, snapshot confirmation and event validation are unchanged.

The application has six distinct views: Overview, Portfolio, Brokers and accounts, Report import,
Import history and Settings. The active navigation item and page heading identify the current
view. Overview shows counts and a next action; native-currency valuation belongs to the selected
account. History shows original import names, dates and record counts, with account backups.
Settings contains the optional questionnaire, profile export and local-storage limitations.
Switching views preserves the in-progress import form and current account. Reload opens Overview.

## Local credential boundary

Credentials extend the existing `quantops.stock-users.v1` registry. Web Crypto derives a
256-bit PBKDF2/SHA-256 verifier using 600,000 iterations and a separately generated 128-bit salt.
Only the verifier and salt are persisted; plaintext passwords are cleared from form state after
successful login/registration and are never sent to the API or a broker. There is no email reset.
The session identifier lives in sessionStorage, survives reload in that tab and is removed on
logout. A previous `active_id` alone never signs a user in. A missing session requires login.

This is a UI access gate. The session identifier and profile registry are client controlled;
report storage remains unencrypted and accessible to someone with access to the browser or
developer tools. It does not protect against local-storage modification, XSS, brute-force
tools, malicious extensions or another person using the same OS/browser profile. Do not present
it as secure tenancy or expose private financial data based on this gate. Server-side identity,
HttpOnly sessions, CSRF controls, authenticated ownership and protected durable storage remain
necessary before any network account service is introduced.

Legacy profiles without credentials are not automatically logged in. Registration offers an
explicit choice to attach credentials to a prior unprotected profile, preserving its UUID,
questionnaire, manual holdings and XTB storage key. This is a local claim of previously
unprotected data, not proof of prior identity. New profiles remain separate. Profile exports
omit credential verifiers; account backups retain report data. Concurrent profile changes
block further writes until reload to avoid silently overwriting another tab.

## Default local test accounts

The loopback development server creates two profiles when their login/UUID is absent:

| Login | Password | Initial portfolio |
| --- | --- | --- |
| `admin` | `admin` | Empty; no report accounts |
| `admin1` | `admin1` | The owner's `quantum_ops_portfolio_test.xlsx` synthetic fixture |

These are public test credentials, not administrator permissions. Initialization is disabled
in production builds and outside localhost/127.0.0.1/IPv6 loopback. Normal registration retains
its ten-character minimum. Verifiers use the same salted PBKDF2 format as other local profiles.
Existing logins and UUIDs are preserved; initialization never resets report accounts or edits.
The registry permits ten custom profiles plus two defaults. Signing out returns to the login form.

The uploaded workbook explicitly marks its three report sections DEMO / SYNTHETIC and its Sources
sheet states that it is not an XTB-issued statement. The packaged seed retains 20 open lots across
9 instruments, 26 closed positions and 76 cash operations, with snapshot time
2026-10-09T20:00:00Z. The account currency is inferred as PLN from this fixture's cash and converted
totals. Workbook prices are not certified as provider quotes: initial marks are empty and existing
dated reference-price refresh remains available. Source cells are data, never executable instructions.
The Sources worksheet is skipped only when its known seven-column provenance header matches.

`scripts/build_local_demo.py SOURCE TARGET` regenerates `apps/web/src/data/localDemo.json` through
the normal parser/merger. It refuses financial sections without the explicit synthetic marker,
records the source SHA-256 and generates fresh credential salts. It does not package the original
workbook. Only use the generator for explicitly authorized synthetic fixtures.

## Verification

Synthetic desktop/mobile browser tests cover registration, mismatched confirmation, rejected
passwords, logout/login, session removal, reload, questionnaire skip and later completion,
multi-broker selection, legacy migration, retained XTB accounts and report import/valuation.
WCAG A/AA axe checks and horizontal overflow checks run on the tested screens. No real password
or broker credential is used in fixtures. Exact results are recorded in `docs/progress.md`.
