from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url


@pytest.mark.integration
def test_clean_test_database_migrates_to_head(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.environ.get("QUANTOPS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("set QUANTOPS_TEST_DATABASE_URL to an isolated PostgreSQL test database")

    parsed = make_url(database_url)
    if parsed.database is None or "test" not in parsed.database.casefold():
        pytest.fail("QUANTOPS_TEST_DATABASE_URL database name must contain 'test'")

    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    monkeypatch.setenv("QUANTOPS_DATABASE_URL", database_url)

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
