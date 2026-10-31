"""Synthetic PDF extraction examples exercise market inheritance and layout failures."""

import pytest

from scripts.extract_bossa_pdf import page_rows


def test_missing_market_cell_inherits_page_section_and_preserves_units() -> None:
    text = (
        "NASDAQ | Akcje i inne instrumenty udziałowe\n"
        "NSQ US0000000002 SYN1 Synthetic fixture GBX Akcje\n"
        "US0000000010 SYN2 Synthetic receipt USD ADS"
    )
    assert page_rows(text) == [
        ["NSQ", "US0000000002", "SYN1", "Synthetic fixture", "GBX", "Akcje"],
        ["NSQ", "US0000000010", "SYN2", "Synthetic receipt", "USD", "ADS"],
    ]


def test_changed_pdf_layout_cannot_silently_drop_rows() -> None:
    with pytest.raises(ValueError, match="Unparsed instrument"):
        page_rows("Xetra | Akcje\nUS0000000002 SYN1 Synthetic row with missing columns")
