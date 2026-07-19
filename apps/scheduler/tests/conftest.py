"""Make the standalone src-layout package importable during root-level discovery."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).parents[1] / "src"
source_text = str(SOURCE_ROOT)
if source_text not in sys.path:
    sys.path.insert(0, source_text)


@pytest.fixture
def workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]
