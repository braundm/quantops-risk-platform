# QuantOps deterministic synthetic dataset

This dataset is entirely fictional and synthetic. It is intended only for software testing,
demonstrations, and transparent risk-methodology examples. It is not current market data and
must not be used for investment decisions.

- Dataset: `quantops_synthetic_market_v1` version `1.0.0`
- Seed: `20250317`
- Window: `2023-01-02` through `2024-12-31`
- Calendar: `SYNTHETIC_WEEKDAY` (Monday-Friday; exchange holidays are intentionally not modeled)
- Instruments: QTECH, QGOLD, QWTI, QCASH
- Canonical accepted bars: 2088

## Regimes

1. `normal`: low-volatility baseline with ordinary diversification.
2. `risk_on`: positive trend with falling cross-asset factor dependence.
3. `volatility_shock`: an abrupt deterministic selloff followed by high volatility.
4. `correlation_breakdown`: normally diversifying risky assets share a common factor.
5. `partial_recovery`: volatility moderates and prices recover only partially.

Canonical accepted CSV/JSON files are under `canonical/`. Intentional missing, late, duplicate,
and malformed inputs are isolated under `cases/`; they never contaminate canonical bars. Their
safe-reference quarantine records and deterministic pipeline counts are under `quarantine/` and
`runs/`.

`manifest.json` records the normalized configuration, seed, artifact byte sizes, SHA-256 hashes,
and aggregate dataset hash. Re-running the generator with the same code and configuration is
byte-identical and leaves unchanged files untouched.
