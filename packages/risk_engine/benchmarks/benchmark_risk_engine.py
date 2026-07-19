"""Dependency-free benchmark for a realistic deterministic demo window.

Run from the package root with:
    python benchmarks/benchmark_risk_engine.py

This reports the local environment and measurements only; it asserts no universal SLA.
"""

from __future__ import annotations

import math
import platform
import sys
from pathlib import Path
from time import perf_counter

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PACKAGE_SRC))

from quantops_risk import (  # noqa: E402
    correlation_matrix,
    historical_expected_shortfall,
    historical_var,
    parametric_var_from_returns,
)


def _rows(observations: int = 756, instruments: int = 25) -> tuple[tuple[float, ...], ...]:
    return tuple(
        tuple(
            0.0002
            + math.sin(day * 0.071 + instrument * 0.41) * (0.006 + instrument * 0.0001)
            + math.cos(day * 0.019) * 0.002
            for instrument in range(instruments)
        )
        for day in range(observations)
    )


def main() -> None:
    rows = _rows()
    exposures = tuple(100_000.0 + index * 10_000.0 for index in range(len(rows[0])))
    series = {f"Q{index:02d}": tuple(row[index] for row in rows) for index in range(len(rows[0]))}

    started = perf_counter()
    historical_var(tuple(sum(row) / len(row) for row in rows), portfolio_value=sum(exposures))
    historical_expected_shortfall(
        tuple(sum(row) / len(row) for row in rows), portfolio_value=sum(exposures)
    )
    parametric_var_from_returns(rows, exposures)
    correlation_matrix(series)
    elapsed = perf_counter() - started

    print(f"python={platform.python_version()} platform={platform.platform()}")
    print(f"observations={len(rows)} instruments={len(rows[0])} elapsed_seconds={elapsed:.6f}")


if __name__ == "__main__":
    main()
