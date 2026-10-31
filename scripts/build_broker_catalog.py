"""Validate and package downloaded specifications; failed input never replaces a snapshot.

Input: fetch_xtb_catalog.py pages, Bossa PDF tables extracted with pdfplumber,
and the public BOSSAFX instrument page. See docs/broker-catalog.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from quantops_api.application.broker_catalog import (
    BrokerCatalog,
    CatalogInstrument,
    CatalogSource,
    InstrumentType,
    instrument_id,
)
from quantops_domain.value_objects import ISO_4217_CODES

GENERATED = Path("data/generated")
OUTPUT = Path("apps/api/quantops_api/data/broker_catalog.json")
XTB_URL = "https://www.xtb.com/web-api/v2/languages/pl/branches/pl/instruments"
BOSSA_PDF = (
    "https://bossa.pl/sites/b30/files/2026-07/document/"
    "Lista_wszystkich_instrumentow_zagranicznych_22-06-2026.pdf"
)
KINDS: dict[str, InstrumentType] = {
    "cashstocks": "equity",
    "etfs": "etf",
    "etcs": "etc",
    "etns": "etn",
    "commodities": "cfd",
    "crypto-cfd": "cfd",
    "indices": "cfd",
    "forex": "cfd",
    "shares": "cfd",
    "etfcfd": "cfd",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetched(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def currency(raw: str) -> str | None:
    # Pence are retained in specifications; no implicit price conversion is performed.
    return raw if raw in ISO_4217_CODES else None


def build() -> BrokerCatalog:
    rows: list[CatalogInstrument] = []
    sources: list[CatalogSource] = []
    cache = GENERATED / "xtb-pages"
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest["instrumentTypes"]) != set(KINDS):
        raise ValueError("XTB categories changed; review classification before import")
    for category, kind in KINDS.items():
        expected = manifest["instrumentCounts"][category]
        records: dict[str, Any] = {}
        digest = hashlib.sha256()
        paths = [cache / f"{category}-{n}.json" for n in range(1, (expected + 9) // 10 + 1)]
        for path in paths:
            digest.update(path.read_bytes())
            page = json.loads(path.read_text(encoding="utf-8"))
            for symbol, row in page["instrumentsCollectionLimited"][category].items():
                if symbol in records:
                    raise ValueError(f"XTB pagination overlaps: {category} {symbol}")
                records[symbol] = row
        if len(records) != expected:
            raise ValueError(f"XTB coverage mismatch: {category} {len(records)} / {expected}")
        source_id = f"xtb-{category}"
        for symbol, row in records.items():
            market = row.get("stock_market") or "OTC"
            specs = {
                key: str(row[key])
                for key in (
                    "currencyCode",
                    "nominal_value_one_lot",
                    "contract_size",
                    "leverage",
                    "trading_hours",
                    "trading_days",
                    "settlement_method",
                    "exercise_type",
                    "payoff_type",
                    "possible_trade_direction",
                )
                if row.get(key) not in (None, "")
            }
            rows.append(
                CatalogInstrument(
                    id=instrument_id("xtb", kind, market, symbol),
                    broker="xtb",
                    symbol=symbol,
                    name=row["display_name"] or row["description"] or symbol,
                    instrument_type=kind,
                    market=market,
                    currency=currency(row.get("currencyCode", "")),
                    source_id=source_id,
                    source_category=category,
                    close_only=row.get("close_only"),
                    specifications=specs,
                )
            )
        sources.append(
            CatalogSource(
                id=source_id,
                broker="xtb",
                url=XTB_URL,
                fetched_at=fetched(paths[-1]),
                sha256=digest.hexdigest(),
                count=len(records),
                expected_count=expected,
                status="source_complete",
                note="All advertised Polish specification pages; account eligibility unverified.",
            )
        )

    table_path = GENERATED / "bossa-world-tables.json"
    extracted = json.loads(table_path.read_text(encoding="utf-8"))
    pdf_path = GENERATED / "bossa-world-pdf.pdf"
    tables: list[list[str]] = extracted["rows"]
    if extracted["pdf_sha256"] != sha(pdf_path) or sum(extracted["page_counts"]) != len(tables):
        raise ValueError("PDF extraction provenance or row counts do not match")
    pdf_kinds: dict[str, InstrumentType] = {
        "Akcje": "equity",
        "ADR": "equity",
        "ADS": "equity",
        "GDR": "equity",
        "REIT": "equity",
        "ETF": "etf",
        "ETC": "etc",
        "ETN": "etn",
        "ETP": "etp",
    }
    for market, isin, symbol, name, raw_currency, category in tables:
        pdf_kind = pdf_kinds.get(category)
        if pdf_kind is None or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
            raise ValueError("Unexpected Bossa PDF row; review extraction")
        rows.append(
            CatalogInstrument(
                id=instrument_id("bossa", pdf_kind, market, symbol),
                broker="bossa",
                symbol=symbol,
                name=name,
                instrument_type=pdf_kind,
                market=market,
                currency=currency(raw_currency),
                isin=isin,
                source_id="bossa-world",
                source_category=category,
                specifications={"quotation_currency": raw_currency},
            )
        )
    sources.append(
        CatalogSource(
            id="bossa-world",
            broker="bossa",
            url=BOSSA_PDF,
            fetched_at=fetched(pdf_path),
            effective_date=date(2026, 6, 22),
            sha256=sha(pdf_path),
            count=len(tables),
            expected_count=len(tables),
            status="source_complete",
            note="All dated PDF rows; current eligibility and other ETP subtypes unverified.",
        )
    )
    fx_path = GENERATED / "bossafx.txt"
    html = fx_path.read_text(encoding="utf-8")
    settings = re.search(r'data-drupal-selector="drupal-settings-json">(.*?)</script>', html, re.S)
    if settings is None:
        raise ValueError("BOSSAFX settings missing")
    fx = json.loads(settings[1])["b30fx_instruments"]
    fx_count = 0
    for category, group in fx.items():
        if not isinstance(group, dict) or "instruments" not in group:
            continue
        for row in group["instruments"]:
            symbol = row["id"]
            market = row.get("exchange") or "OTC"
            rows.append(
                CatalogInstrument(
                    id=instrument_id("bossa", "cfd", market, symbol),
                    broker="bossa",
                    symbol=symbol,
                    name=row["product_description"],
                    instrument_type="cfd",
                    market=market,
                    source_id="bossafx",
                    source_category=category,
                    specifications={
                        key: str(row[key])
                        for key in ("value", "min_value", "leverage")
                        if row.get(key) is not None
                    },
                )
            )
            fx_count += 1
    sources.append(
        CatalogSource(
            id="bossafx",
            broker="bossa",
            url="https://bossafx.pl/oferta/instrumenty",
            fetched_at=fetched(fx_path),
            sha256=sha(fx_path),
            count=fx_count,
            expected_count=fx_count,
            status="source_complete",
            note="All public specification rows; settlement currency not parsed.",
        )
    )
    for category in (
        "akcje",
        "newconnect",
        "globalconnect",
        "opcje",
        "kontrakty",
        "etf",
        "obligacje",
        "certyfikaty",
    ):
        path = GENERATED / f"bossa-{category}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("components") or any(g["items"] for g in payload.get("groups", [])):
            raise ValueError("Bossa domestic feed recovered; implement and review its new schema")
        sources.append(
            CatalogSource(
                id=f"bossa-{category}",
                broker="bossa",
                url=f"https://bossa.pl/wats_api/API/market/group/{category}",
                fetched_at=fetched(path),
                sha256=sha(path),
                count=0,
                status="unavailable",
                note="Public endpoint returned no instruments; offer coverage is missing.",
            )
        )
    return BrokerCatalog(
        instruments=tuple(sorted(rows, key=lambda r: (r.broker, r.symbol, r.instrument_type))),
        sources=tuple(sources),
    )


if __name__ == "__main__":
    catalog = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(catalog.model_dump_json(exclude_none=True), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(f"Validated {len(catalog.instruments)} reference instruments; overall coverage partial")
