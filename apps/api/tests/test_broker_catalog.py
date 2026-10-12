"""Offline public specification identity, provenance and search invariants."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from quantops_api.application.broker_catalog import (
    BrokerCatalog,
    CatalogInstrument,
    CatalogSource,
    instrument_id,
    load_catalog,
)
from quantops_api.main import create_app


def test_snapshot_coverage_counts_and_missing_domestic_feed_are_explicit() -> None:
    catalog = load_catalog()
    assert catalog.coverage == "partial"
    xtb = [source for source in catalog.sources if source.broker == "xtb"]
    assert len(xtb) == 10
    assert sum(source.count for source in xtb) == 12599
    assert all(source.count == source.expected_count for source in xtb)
    assert next(s for s in catalog.sources if s.id == "bossa-world").count == 5632
    assert next(s for s in catalog.sources if s.id == "bossa-opcje").status == "unavailable"
    assert all(row.valuation_status == "reference_only" for row in catalog.instruments)


def test_equity_and_cfd_identity_and_details_do_not_alias() -> None:
    with TestClient(create_app()) as client:
        result = client.get("/api/v1/broker-catalog", params={"q": "AAPL", "broker": "xtb"})
        assert result.status_code == 200
        rows = [row for row in result.json()["items"] if row["symbol"] == "AAPL.US"]
        assert {row["instrument_type"] for row in rows} == {"equity", "cfd"}
        assert len({row["id"] for row in rows}) == 2
        for row in rows:
            assert client.get(f"/api/v1/broker-catalog/{row['id']}").json() == row
        assert client.get(f"/api/v1/broker-catalog/{uuid4()}").status_code == 404


def test_search_filters_isin_pagination_and_empty_results() -> None:
    with TestClient(create_app()) as client:
        first = client.get("/api/v1/broker-catalog", params={"limit": 7}).json()
        second = client.get("/api/v1/broker-catalog", params={"limit": 7, "offset": 7}).json()
        assert first["total"] == second["total"] > 18000
        assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}
        filtered = client.get(
            "/api/v1/broker-catalog",
            params={
                "q": " apple ",
                "broker": "xtb",
                "instrument_type": "equity",
            },
        ).json()
        assert filtered["total"] > 0
        assert all(
            r["broker"] == "xtb" and r["instrument_type"] == "equity" for r in filtered["items"]
        )
        isin = client.get("/api/v1/broker-catalog", params={"q": "DE0005140008"}).json()
        assert any(r["symbol"] == "DBK" and r["market"] == "Xetra" for r in isin["items"])
        assert (
            client.get("/api/v1/broker-catalog", params={"instrument_type": "option"}).json()[
                "total"
            ]
            == 0
        )
        for params in ({"limit": 101}, {"offset": -1}, {"broker": "other"}, {"q": "x" * 121}):
            assert client.get("/api/v1/broker-catalog", params=params).status_code == 422


def test_source_provenance_and_currency_reject_false_precision() -> None:
    source = CatalogSource(
        id="synthetic-source",
        broker="bossa",
        url="https://bossa.pl/synthetic-test-only",
        fetched_at=datetime(2026, 10, 11, tzinfo=UTC),
        sha256="0" * 64,
        count=1,
        expected_count=1,
        status="source_complete",
        note="Synthetic specification test fixture",
    )
    for changes in (
        {"fetched_at": "2026-10-11T00:00:00"},
        {"url": "javascript:alert(1)"},
        {"expected_count": 2},
    ):
        with pytest.raises(ValidationError):
            CatalogSource.model_validate(source.model_dump() | changes)
    row = CatalogInstrument(
        id=instrument_id("bossa", "option", "Synthetic", "SYNTHETIC"),
        broker="bossa",
        symbol="SYNTHETIC",
        name="Synthetic option fixture",
        instrument_type="option",
        market="Synthetic",
        source_id=source.id,
        source_category="synthetic",
    )
    assert row.currency is None
    for row_changes in ({"currency": "GBX"}, {"id": uuid4()}):
        with pytest.raises(ValidationError):
            CatalogInstrument.model_validate(row.model_dump() | row_changes)
    with pytest.raises(ValidationError, match="Duplicate"):
        BrokerCatalog(sources=(source,), instruments=(row, row))
    with pytest.raises(ValidationError, match="Source count"):
        BrokerCatalog(sources=(source,), instruments=())


def test_pence_remain_source_units_without_silent_gbp_conversion() -> None:
    pence = [
        row
        for row in load_catalog().instruments
        if row.specifications.get("quotation_currency") == "GBX"
    ]
    assert pence
    assert all(row.currency is None for row in pence)
