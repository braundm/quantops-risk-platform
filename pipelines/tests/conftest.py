"""Make the src-layout package importable in repository-level test runs."""

from __future__ import annotations

import sys
from pathlib import Path

PIPELINE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))
