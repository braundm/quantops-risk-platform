"""Build the explicitly synthetic local demo seed from the owner's test workbook."""

import argparse
import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from quantops_api.application.xtb_book import analyze_book, merge_book
from quantops_api.application.xtb_models import XtbBook
from quantops_api.application.xtb_reports import parse_report, workbook_tables


def build(source: Path, target: Path) -> None:
    """Refuse private/unmarked workbooks and preserve import semantics in the demo."""
    data = source.read_bytes()
    tables = workbook_tables(data)
    for name in ("Closed Positions", "Open Positions", "Cash Operations"):
        if not any("DEMO / SYNTHETIC" in cell for row in tables[name][:4] for cell in row):
            raise ValueError("Only explicitly marked synthetic report sections may be packaged")
    metadata = tables["Open Positions"][0]
    account = metadata[1]
    # PLN is the account currency of this fixture: cash entries and converted report totals.
    preview = parse_report(source.name, data, account, "PLN", datetime.now(UTC))
    book, _ = merge_book(
        XtbBook(account_number=account, currency="PLN"),
        preview,
        complete_snapshot=True,
        complete_ledger=False,
    )
    analysis = analyze_book(book)
    profiles = []
    for login, origin in (("admin", "empty"), ("admin1", "uploaded_workbook")):
        salt = secrets.token_bytes(16)
        profiles.append(
            {
                "id": str(uuid5(NAMESPACE_URL, f"quantops:local-demo:{login}")),
                "name": login,
                "demo_origin": origin,
                "credentials": {
                    "login": login,
                    "salt": salt.hex(),
                    "digest": hashlib.pbkdf2_hmac("sha256", login.encode(), salt, 600000).hex(),
                    "iterations": 600000,
                },
            }
        )
    seed = {
        "synthetic": True,
        "source_filename": source.name,
        "source_sha256": preview.report_hash,
        "counts": {
            "open": preview.open_count,
            "closed": preview.closed_count,
            "cash": preview.cash_count,
            "unique_symbols": len({r.symbol for r in analysis.holdings}),
        },
        "profiles": profiles,
        "accounts": {
            "version": 1,
            "selected": str(uuid5(NAMESPACE_URL, "quantops:local-demo:xtb")),
            "accounts": [
                {
                    "id": str(uuid5(NAMESPACE_URL, "quantops:local-demo:xtb")),
                    "label": "XTB testowe PLN — SYNTHETIC",
                    "broker": "xtb",
                    "book": book.model_dump(mode="json"),
                    "marks": [],
                    "imports": [
                        {
                            "hash": preview.report_hash,
                            "filename": source.name,
                            "at": book.open_snapshot_at.isoformat()
                            if book.open_snapshot_at
                            else "",
                            "records": len(book.records),
                        }
                    ],
                }
            ],
        },
    }
    target.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(seed["counts"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    arguments = parser.parse_args()
    build(arguments.source, arguments.target)
