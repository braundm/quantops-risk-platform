# Security policy

## Supported versions

QuantOps is pre-release software. Security fixes apply to the latest `main` revision until a versioned release exists.

## Reporting

Do not open a public issue containing an exploitable vulnerability, credentials, or private data. Before publication, contact the repository owner privately using the security-reporting channel that will be configured in the public GitHub repository. This contact remains an explicit owner-review item.

## Product boundaries

- The local demo token is not production identity.
- External adapters and LLM providers are optional and disabled by default.
- QuantOps never requires brokerage credentials and has no order-execution capability.
- Synthetic fixtures must not be confused with live or exchange-grade market data.

See `docs/security/threat-model.md` once the application attack surface is implemented and verified.
