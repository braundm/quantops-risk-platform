# QuantOps data

The committed default dataset is deterministic, fictional, and explicitly synthetic. It is designed to exercise risk, lineage, data-quality, streaming, ML, and grounded-AI workflows without requiring live accounts or implying current market behavior.

- `synthetic/` contains the canonical two-year fixture, approved fictional documents, isolated quality cases, quarantine output, run metadata, and SHA-256 manifest.
- `generated/` is reserved for recoverable local outputs and is ignored except for its placeholder.
- `schemas/` and `licenses/` will hold versioned public contracts and source-specific usage notes as adapters are added.

Run the generator and verifier without network access:

```bash
PYTHONPATH=pipelines/src python -m quantops_pipelines generate --output data/synthetic
PYTHONPATH=pipelines/src python -m quantops_pipelines verify --dataset data/synthetic
```

The canonical dataset contains no real customer, portfolio, issuer, or market data. See [`synthetic/README.md`](synthetic/README.md) and the project [data-lineage document](../docs/data-lineage.md).
