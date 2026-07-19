# QuantOps data pipelines

This package provides the deterministic, offline synthetic-data foundation for QuantOps. It
contains no live-provider or network integration. Its canonical output is visibly fictional and
is suitable only for product demonstrations, tests, and risk-methodology examples.

From the repository root, generate and verify the bundled dataset with an installed package:

```text
quantops-data generate --config data/synthetic/generator_config.json --output data/synthetic
quantops-data verify --dataset data/synthetic
```

Without installation, set `PYTHONPATH=pipelines/src` and invoke
`python -m quantops_pipelines` with the same arguments. Generation is content-addressed and
idempotent: unchanged files are not rewritten, and the manifest verifies every artifact except
itself using SHA-256.

The accepted OHLCV series is kept under `data/synthetic/canonical`. Deliberately missing, late,
duplicate, and malformed staging examples are isolated under `data/synthetic/cases`; their
quality records contain safe references and live under `data/synthetic/quarantine`.
