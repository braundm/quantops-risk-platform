"""Read bounded XTB CSV/XLSX/ZIP reports as data, never execute workbook formulas."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from quantops_api.application.xtb_models import XtbBook, XtbPreview, XtbRecord, record_id

MAX_BYTES = 8 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024


def normalized(text: str) -> str:
    text = text.lower().replace("ł", "l")
    return re.sub(
        r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    )


ALIASES = {
    "instrument": "name",
    "instrumentname": "name",
    "nazwa": "name",
    "category": "category",
    "kategoria": "category",
    "ticker": "symbol",
    "symbol": "symbol",
    "type": "side",
    "typ": "side",
    "volume": "quantity",
    "wolumen": "quantity",
    "quantity": "quantity",
    "ilosc": "quantity",
    "openprice": "price",
    "cenaotwarcia": "price",
    "price": "price",
    "cena": "price",
    "opentimeutc": "at",
    "opentime": "at",
    "czasotwarcia": "at",
    "czasotwarciautc": "at",
    "time": "at",
    "timeutc": "at",
    "czas": "at",
    "czasutc": "at",
    "closetimeutc": "closed",
    "closetime": "closed",
    "czaszamkniecia": "closed",
    "czaszamknieciautc": "closed",
    "closeprice": "close_price",
    "cenazamkniecia": "close_price",
    "profitloss": "pnl",
    "zyskstrata": "pnl",
    "positionid": "position_id",
    "idpozycji": "position_id",
    "id": "id",
    "amount": "amount",
    "kwota": "amount",
}


def bounded_zip(data: bytes) -> ZipFile:
    archive = ZipFile(io.BytesIO(data))
    members = archive.infolist()
    if len(members) > 512 or sum(member.file_size for member in members) > MAX_EXPANDED:
        archive.close()
        raise ValueError("Archive exceeds the expanded size or entry limit")
    if len({member.filename for member in members}) != len(members):
        archive.close()
        raise ValueError("Duplicate archive paths are not supported")
    for member in members:
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if (
            path.is_absolute()
            or ".." in path.parts
            or re.match(r"^[A-Za-z]:", member.filename)
            or member.flag_bits & 1
        ):
            archive.close()
            raise ValueError("Unsafe or encrypted archive member")
    return archive


def xml(data: bytes) -> ET.Element:
    if (
        len(data) > MAX_BYTES
        or b"\x00" in data
        or any(token in data.upper() for token in (b"<!DOCTYPE", b"<!ENTITY"))
    ):
        raise ValueError("Unsupported or oversized workbook XML")
    # Entity declarations and non-UTF8 XML are rejected before parsing.
    data.decode("utf-8-sig")
    return ET.fromstring(data)  # noqa: S314 - guarded XML, no DTD or entities


def workbook_tables(data: bytes) -> dict[str, list[list[str]]]:
    with bounded_zip(data) as archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names:
            raise ValueError("Not an XLSX workbook")
        book = xml(archive.read("xl/workbook.xml"))
        if book.find(".//{*}workbookPr") is not None:
            props = book.find(".//{*}workbookPr")
            if props is not None and props.get("date1904") in ("1", "true"):
                raise ValueError("The 1904 Excel date system is not supported")
        relationships = xml(archive.read("xl/_rels/workbook.xml.rels"))
        paths = {rel.attrib["Id"]: rel.attrib.get("Target", "") for rel in relationships}
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared = [
                "".join(item.itertext()) for item in xml(archive.read("xl/sharedStrings.xml"))
            ]
        tables: dict[str, list[list[str]]] = {}
        cells = 0
        for sheet in book.findall(".//{*}sheet"):
            rel_id = next(v for k, v in sheet.attrib.items() if k.endswith("}id"))
            target = paths[rel_id]
            path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            if path not in names or ".." in PurePosixPath(path).parts:
                raise ValueError("Unsupported worksheet relationship")
            rows: list[list[str]] = []
            for node in xml(archive.read(path)).findall(".//{*}sheetData/{*}row"):
                values: list[str] = []
                for cell in node:
                    cells += 1
                    if cells > 250000 or cell.find("{*}f") is not None:
                        raise ValueError("Workbook formulas or excessive cells are not supported")
                    reference = cell.get("r", "")
                    letters = re.match(r"[A-Z]+", reference)
                    if letters is None:
                        raise ValueError("Missing workbook cell reference")
                    column = 0
                    for letter in letters[0]:
                        column = column * 26 + ord(letter) - ord("A") + 1
                    if column > 64:
                        raise ValueError("Report exceeds the column limit")
                    while len(values) < column:
                        values.append("")
                    value = cell.findtext("{*}v", "")
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.itertext())
                    values[column - 1] = value
                rows.append(values)
                if len(rows) > 20010:
                    raise ValueError("Report exceeds the row limit")
            tables[sheet.attrib["name"]] = rows
        return tables


def csv_table(data: bytes) -> list[list[str]]:
    text = ""
    for encoding in ("utf-8-sig", "utf-16", "cp1250"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeError:
            continue
    if not text or "\x00" in text:
        raise ValueError("Unsupported CSV encoding")
    try:
        # Export metadata and footers have fewer columns than the actual table.
        candidates = text.splitlines()[:30]
        header = max(candidates, key=lambda line: max(line.count(d) for d in ",;\t"))
        dialect = csv.Sniffer().sniff(header, delimiters=",;\t")
    except csv.Error as error:
        raise ValueError("CSV requires comma, semicolon or tab-separated columns") from error
    rows = list(csv.reader(io.StringIO(text), dialect, strict=True))
    if len(rows) > 20010 or any(len(row) > 64 for row in rows):
        raise ValueError("CSV exceeds row or column limits")
    return rows


def tables_from_file(filename: str, data: bytes) -> dict[str, list[list[str]]]:
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds 8 MiB")
    extension = PurePosixPath(filename).suffix.lower()
    if extension == ".csv":
        return {"CSV": csv_table(data)}
    if extension == ".xlsx":
        return workbook_tables(data)
    if extension == ".zip":
        result: dict[str, list[list[str]]] = {}
        with bounded_zip(data) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                if PurePosixPath(member.filename).suffix.lower() not in (".csv", ".xlsx"):
                    raise ValueError("ZIP may contain only CSV or XLSX reports")
                for name, rows in tables_from_file(member.filename, archive.read(member)).items():
                    key = f"{member.filename}:{name}"
                    result[key] = rows
                    if (
                        sum(len(table) for table in result.values()) > 20010
                        or sum(len(row) for table in result.values() for row in table) > 250000
                    ):
                        raise ValueError("Combined reports exceed row or cell limits")
        if not result:
            raise ValueError("ZIP contains no reports")
        return result
    raise ValueError("Choose an XTB CSV, XLSX or ZIP report")


def number(text: str) -> Decimal:
    try:
        value = Decimal(text.replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except InvalidOperation as error:
        raise ValueError("Invalid report number") from error
    if not value.is_finite():
        raise ValueError("Non-finite report number")
    try:
        return value.quantize(Decimal("0.0000000001"))
    except InvalidOperation as error:
        raise ValueError("Report number exceeds supported precision") from error


def time_value(text: str) -> datetime:
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
        value = Decimal(text)
        if not Decimal(32874) <= value <= Decimal(100000):
            raise ValueError("Invalid Excel date")
        return datetime(1899, 12, 30, tzinfo=UTC) + timedelta(microseconds=int(value * 86400000000))
    text = text.strip().replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(text)
    except ValueError:
        result = None
        for fmt in ("%d.%m.%Y %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                result = datetime.strptime(text, fmt)  # noqa: DTZ007 - source column is UTC
                break
            except ValueError:
                continue
        if result is None:
            raise ValueError("Invalid report timestamp; use UTC ISO dates") from None
    if result is None:
        raise ValueError("Invalid report timestamp")
    return result.replace(tzinfo=UTC) if result.utcoffset() is None else result.astimezone(UTC)


def asset_type(category: str) -> str:
    return {
        "cfd": "cfd",
        "stocks": "equity",
        "stock": "equity",
        "cashstocks": "equity",
        "stc": "equity",
        "stk": "equity",
        "akcje": "equity",
        "etf": "etf",
        "etfs": "etf",
    }.get(normalized(category), "unknown")


def parse_report(
    filename: str, data: bytes, account: str, currency: str, observed: datetime
) -> XtbPreview:
    try:
        tables = tables_from_file(filename, data)
        for report_name in (filename, *tables):
            identity = re.search(r"(?:^|[/\\])([A-Z]{3})_([0-9]+)_", report_name)
            if identity and identity[1] != currency:
                raise ValueError("Report currency differs from the selected account")
            if identity and identity[2] != account:
                raise ValueError("Report account differs from the selected XTB account")
        records: list[XtbRecord] = []
        has_open = False
        snapshot_times: set[datetime] = set()
        for sheet, rows in tables.items():
            if normalized(sheet.rsplit(":", 1)[-1]) == "sources":
                if not rows or rows[0] != [
                    "Source Type",
                    "Ticker",
                    "Instrument / Dataset",
                    "Market",
                    "Data Used",
                    "URL",
                    "Notes",
                ]:
                    raise ValueError("Unsupported source-provenance worksheet")
                continue  # Provenance cells are data, never executable instructions.
            header_at = None
            headers: list[str] = []
            sheet_observed = observed
            for index, metadata in enumerate(rows[:30]):
                if (
                    metadata
                    and normalized(metadata[0]) in ("account", "accountnumber", "numerrachunku")
                    and (len(metadata) < 2 or metadata[1].strip() != account)
                ):
                    raise ValueError("Report account differs from the selected XTB account")
                if (
                    metadata
                    and normalized(metadata[0]) in ("currency", "waluta")
                    and (len(metadata) < 2 or metadata[1].strip() != currency)
                ):
                    raise ValueError("Report currency differs from the selected account")
                if (
                    metadata
                    and normalized(metadata[0]) in ("datetoutc", "dateto", "datado")
                    and len(metadata) > 1
                ):
                    sheet_observed = min(observed, time_value(metadata[1]))
                mapped = [ALIASES.get(normalized(cell), "") for cell in metadata]
                if "symbol" in mapped and ("quantity" in mapped or "amount" in mapped):
                    header_at, headers = index, mapped
                    break
            if header_at is None:
                raise ValueError(f"Unsupported XTB table: {sheet.rsplit(':', 1)[-1]}")
            recognized = [h for h in headers if h]
            if len(set(recognized)) != len(recognized):
                raise ValueError("Duplicate recognized CSV columns")
            is_cash = "amount" in headers and "quantity" not in headers
            is_fill = not is_cash and "position_id" not in headers and "id" in headers
            declared_closed = any(
                word in normalized(sheet) for word in ("closedpositions", "zamkniete")
            )
            declared_open = any(word in normalized(sheet) for word in ("openpositions", "otwarte"))
            has_open = has_open or declared_open
            if declared_open:
                snapshot_times.add(sheet_observed)
            for row_number, values in enumerate(rows[header_at + 1 :], header_at + 2):
                if not any(value.strip() for value in values):
                    continue
                if normalized(values[0]) in (
                    "profitloss",
                    "total",
                    "suma",
                    "zyskstrata",
                    "openpositionstotal",
                ):
                    continue
                row = {
                    key: values[i].strip() if i < len(values) else ""
                    for i, key in enumerate(headers)
                    if key
                }
                try:
                    source_id = row.get("position_id") or row.get("id") or ""
                    if not source_id:
                        raise ValueError("Stable Position ID or transaction ID is required")
                    if re.fullmatch(r"\d+\.0+", source_id):
                        source_id = source_id.split(".")[0]
                    at = time_value(row.get("at", ""))
                    closed = time_value(row["closed"]) if row.get("closed") else None
                    kind = (
                        "cash" if is_cash else "fill" if is_fill else "closed" if closed else "open"
                    )
                    if declared_closed and not is_cash and closed is None:
                        raise ValueError("A closed-position report row is missing its close time")
                    if declared_open and closed is not None:
                        raise ValueError("An open-position report contains a closed row")
                    has_open = has_open or kind == "open"
                    if kind == "open":
                        snapshot_times.add(sheet_observed)
                    common: dict[str, Any] = {
                        "id": record_id(account, kind, source_id, closed),
                        "account_number": account,
                        "kind": kind,
                        "source_id": source_id,
                        "symbol": row.get("symbol", ""),
                        "name": row.get("name", ""),
                        "event_at": at,
                        "observed_at": sheet_observed,
                    }
                    if is_cash:
                        common.update(
                            cash_amount=number(row["amount"]), operation=row.get("side", "")
                        )
                    else:
                        common.update(
                            side=row.get("side", "").upper(),
                            quantity=number(row.get("quantity", "")),
                            price=number(row.get("price", "")),
                            asset_type=asset_type(row.get("category", "")),
                            close_at=closed,
                            close_price=number(row["close_price"])
                            if row.get("close_price")
                            else None,
                            reported_pnl=number(row["pnl"]) if row.get("pnl") else None,
                        )
                    records.append(XtbRecord.model_validate(common))
                except (ValueError, KeyError, OverflowError) as error:
                    raise ValueError(
                        f"Invalid XTB row {row_number}: {str(error).splitlines()[0]}"
                    ) from error
        unique: dict[object, XtbRecord] = {}
        for record in records:
            if record.id in unique and record != unique[record.id]:
                raise ValueError("Conflicting duplicate broker event")
            unique[record.id] = record
        records = list(unique.values())
        if len(snapshot_times) > 1:
            raise ValueError("Import open-position snapshots with different dates separately")
        book = XtbBook(account_number=account, currency=currency, records=records)
        warnings = [
            "Reports cover only their selected period; cash movements are not account balances.",
            "Closed-position P/L and matching cash entries must not be added together.",
        ]
        if not has_open and not any(r.kind == "fill" for r in records):
            warnings.append(
                "No open positions or purchase ledger supplied; current holdings are unknown."
            )
        if any(r.asset_type in ("unknown", "cfd") and r.kind != "cash" for r in records):
            warnings.append(
                "CFD or unclassified instruments are retained; spot valuation is disabled for them."
            )
        return XtbPreview(
            book=book,
            report_hash=hashlib.sha256(data).hexdigest(),
            sheets=list(tables),
            has_open_section=has_open,
            snapshot_at=next(iter(snapshot_times), None),
            warnings=warnings,
            closed_count=sum(r.kind == "closed" for r in records),
            open_count=sum(r.kind == "open" for r in records),
            fill_count=sum(r.kind == "fill" for r in records),
            cash_count=sum(r.kind == "cash" for r in records),
        )
    except (
        BadZipFile,
        ET.ParseError,
        UnicodeError,
        IndexError,
        KeyError,
        StopIteration,
        csv.Error,
    ) as error:
        raise ValueError("Invalid or unsupported report file") from error
