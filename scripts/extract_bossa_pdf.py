"""Extract every reference row from the dated Bossa PDF using optional pdfplumber.

PDF tooling belongs to this explicit maintenance task, never the application runtime.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from pathlib import Path

ROW = re.compile(
    r"^(?:(\S+) )?([A-Z]{2}[A-Z0-9]{9}[0-9]) (\S+) (.+?) ([A-Z]{3}) "
    r"(Akcje|ADR|ADS|GDR|REIT|ETF|ETC|ETN|ETP)$"
)
ISIN = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")
PDF = Path("data/generated/bossa-world-pdf.pdf")
TABLES = Path("data/generated/bossa-world-tables.json")


def page_rows(text: str) -> list[list[str]]:
    section = next(line for line in text.splitlines() if " | " in line).split(" | ")[0]
    market = {"NASDAQ": "NSQ"}.get(section, section)
    rows = []
    for line in text.splitlines():
        match = ROW.fullmatch(line)
        if match:
            values = list(match.groups())
            values[0] = values[0] or market
            rows.append(values)
        elif ISIN.search(line):
            raise ValueError("Unparsed instrument row; review PDF layout before publishing")
    if len(ISIN.findall(text)) != len(rows):
        raise ValueError("Extracted row count differs from page ISIN count")
    return rows


def extract() -> None:
    pdfplumber = importlib.import_module("pdfplumber")
    rows: list[list[str]] = []
    counts = []
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages[3:]:
            data = page_rows(page.extract_text())
            counts.append(len(data))
            rows.extend(data)
    TABLES.write_text(
        json.dumps(
            {
                "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
                "page_counts": counts,
                "rows": rows,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Extracted and counted {len(rows)} rows across {len(counts)} table pages")


if __name__ == "__main__":
    extract()
