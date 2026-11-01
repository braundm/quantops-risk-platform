"""Bounded ctypes adapter to the optional, versioned C++ Monte Carlo library."""

from __future__ import annotations

import ctypes
import math
import sys
from pathlib import Path


class NativeUnavailable(RuntimeError):
    """The optional native component has not been built for this host."""


def simulate(
    exposures: list[float],
    covariance: list[list[float]],
    drifts: list[float],
    days: int,
    simulations: int,
    seed: int,
    confidence: float,
) -> tuple[list[float], list[list[float]], list[list[float]], list[float]]:
    """Return summary, marginal bands, sampled paths and sorted terminal NAVs."""
    n = len(exposures)
    if not 1 <= n <= 20 or len(drifts) != n or len(covariance) != n:
        raise ValueError("One to twenty matching asset inputs are required")
    if any(len(row) != n for row in covariance):
        raise ValueError("Covariance dimensions differ")
    if not 1 <= days <= 1260 or not 1000 <= simulations <= 50000:
        raise ValueError("Unsupported simulation dimensions")
    if not 0 <= seed <= 2**64 - 1:
        raise ValueError("Seed outside uint64 range")
    root = Path(__file__).resolve().parents[4] / "native" / "monte_carlo" / "build"
    filename = (
        "quantops_mc.dll"
        if sys.platform == "win32"
        else ("libquantops_mc.dylib" if sys.platform == "darwin" else "libquantops_mc.so")
    )
    library_path = next(
        (p for p in (root / "Release" / filename, root / filename) if p.is_file()), None
    )
    if library_path is None:
        raise NativeUnavailable(
            "Build the native engine: python scripts/build_monte_carlo.py --test"
        )
    try:
        library = ctypes.CDLL(str(library_path))
        version = library.qmc_abi_version
        call = library.qmc_simulate
    except (OSError, AttributeError) as load_error:
        raise NativeUnavailable(
            "The native engine cannot load on this host; rebuild it"
        ) from load_error
    version.restype = ctypes.c_int
    if version() != 1:
        raise NativeUnavailable("Native ABI mismatch; rebuild the Monte Carlo engine")
    pointer = ctypes.POINTER(ctypes.c_double)
    call.argtypes = [
        ctypes.c_int,
        pointer,
        pointer,
        pointer,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_double,
        ctypes.c_int,
        pointer,
        ctypes.c_uint64,
        ctypes.POINTER(ctypes.c_char),
        ctypes.c_int,
    ]
    call.restype = ctypes.c_int
    points = min(53, days + 1)
    size = 5 + 15 * points + simulations
    output = (ctypes.c_double * size)()
    error = ctypes.create_string_buffer(256)
    status = call(
        n,
        (ctypes.c_double * n)(*exposures),
        (ctypes.c_double * n)(*drifts),
        (ctypes.c_double * (n * n))(*(v for row in covariance for v in row)),
        days,
        simulations,
        seed,
        confidence,
        points,
        output,
        size,
        error,
        len(error),
    )
    if status:
        message = error.value.decode("utf-8", errors="replace") or "Native simulation failed"
        raise ValueError(message)
    result = list(output)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("Native engine returned non-finite output")
    bands = [result[5 + 3 * k : 5 + 3 * k + 3] for k in range(points)]
    start = 5 + 3 * points
    paths = [result[start + p * points : start + (p + 1) * points] for p in range(12)]
    return result[:5], bands, paths, result[5 + 15 * points :]
