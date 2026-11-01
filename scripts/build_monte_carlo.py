"""Build and verify the optional C++17 Monte Carlo engine without downloads."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    cmake = shutil.which("cmake")
    if cmake is None:
        candidates = list(
            Path("C:/Program Files/Microsoft Visual Studio/2022").glob(
                "*/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
            )
        )
        if candidates:
            cmake = str(candidates[0])
    if cmake is None:
        raise SystemExit("Install CMake 3.20+ and a C++17 compiler, then run this command again.")
    source = ROOT / "native" / "monte_carlo"
    build = source / "build"
    subprocess.run(  # noqa: S603
        [cmake, "-S", str(source), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"], check=True
    )
    subprocess.run([cmake, "--build", str(build), "--config", "Release"], check=True)  # noqa: S603
    if args.test:
        ctest = str(Path(cmake).with_name("ctest.exe" if Path(cmake).suffix == ".exe" else "ctest"))
        subprocess.run(  # noqa: S603
            [ctest, "--test-dir", str(build), "-C", "Release", "--output-on-failure"],
            check=True,
        )


if __name__ == "__main__":
    main()
