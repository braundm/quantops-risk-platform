# QuantOps risk-regime lifecycle

This package classifies **risk regimes** from deterministic synthetic market observations. It does
not predict price direction, optimize trading returns, recommend investments, or execute orders.
The default implementation uses only the Python standard library so unit tests never need a model
server, network, MLflow, NumPy, or scikit-learn.

The lifecycle contains:

- point-in-time rolling volatility, drawdown, correlation, dispersion, volume, and quality features;
- a documented rule baseline;
- deterministic standardization and pure-Python K-Means candidates across fixed seeds;
- an explicit centroid-to-regime mapping through the versioned rule baseline;
- chronological train/validation/test splits with no shuffling;
- macro F1, adjusted Rand index, stress false-negative rate, and calibration error;
- a median-validation-seed selection policy that does not cherry-pick the best run;
- automated promotion gates, deterministic model artifacts, a model card, and PSI/Jensen-Shannon
  drift reports;
- an optional MLflow adapter that is disabled by default and reports unavailability cleanly.

Run from the repository root after exposing `ml/src` on `PYTHONPATH`:

```text
python -m quantops_ml run \
  --prices data/synthetic/canonical/price_bars.csv \
  --manifest data/synthetic/manifest.json \
  --output ml/artifacts/demo
```

All persisted demo artifacts are deterministic. Host-dependent latency and wall-clock timestamps
are deliberately not written into the reproducibility report.
