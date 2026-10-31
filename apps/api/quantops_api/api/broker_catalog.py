"""Search public broker specification snapshots without requesting live provider data."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from quantops_api.application.broker_catalog import (
    Broker,
    CatalogContract,
    CatalogInstrument,
    CatalogSource,
    InstrumentType,
    load_catalog,
)

router = APIRouter(prefix="/api/v1/broker-catalog", tags=["Public instrument catalog"])


class CatalogPage(CatalogContract):
    schema_version: str = "broker-catalog@1.0.0"
    coverage: str = "partial"
    total: int
    offset: int
    limit: int
    items: list[CatalogInstrument]
    sources: tuple[CatalogSource, ...]
    markets: list[str]
    instrument_types: list[str]


@router.get("", response_model=CatalogPage)
def search_catalog(
    q: str = Query(default="", max_length=120),
    broker: Broker | None = None,
    instrument_type: InstrumentType | None = None,
    market: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=50, ge=1, le=100),
) -> CatalogPage:
    catalog = load_catalog()
    query = q.strip().casefold()
    rows = [
        row
        for row in catalog.instruments
        if (broker is None or row.broker == broker)
        and (instrument_type is None or row.instrument_type == instrument_type)
        and (market is None or row.market == market)
        and (not query or query in f"{row.symbol} {row.name} {row.isin or ''}".casefold())
    ]
    return CatalogPage(
        total=len(rows),
        offset=offset,
        limit=limit,
        items=rows[offset : offset + limit],
        sources=catalog.sources,
        markets=sorted({row.market for row in catalog.instruments}),
        instrument_types=sorted({row.instrument_type for row in catalog.instruments}),
    )


@router.get("/{instrument_id}", response_model=CatalogInstrument)
def catalog_detail(instrument_id: UUID) -> CatalogInstrument:
    for row in load_catalog().instruments:
        if row.id == instrument_id:
            return row
    raise HTTPException(404, "Instrument not found in the public catalog snapshot")
