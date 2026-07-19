# QuantOps risk engine

`quantops-risk` is an independently installable, framework-free Python package for
deterministic market-risk calculations. Its public results are immutable dataclasses,
carry methodology version `1.0.0`, and use a positive-number-is-a-loss convention for
VaR and Expected Shortfall.

The engine contains no database, web-framework, or network imports. Decimal is used for
position valuation and scenario revaluation; floating point is used for statistical
calculations. See `docs/risk-methodology.md` for equations, assumptions, and limitations.

Development install:

```shell
python -m pip install -e ".[test]"
python -m pytest
```

The calculations are educational engineering components, not forecasts or investment
advice.
