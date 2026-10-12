"""Stock valuation suppresses unknown or unreconciled costs and rejects nonfinite inputs."""

from decimal import Decimal

import pytest

from quantops_risk.exceptions import InvalidInputError
from quantops_risk.stock_holdings import StockMark, value_stock


def test_decimal_stock_value_and_cost_statuses() -> None:
    result = value_stock(StockMark("PLN", Decimal("0.5"), Decimal("123.45"), Decimal("100")))
    assert result.value == Decimal("61.725")
    assert result.unrealized_change == Decimal("11.725")
    assert value_stock(StockMark("USD", Decimal(2), Decimal(50), None)).status == "unknown_cost"
    assert value_stock(StockMark("USD", Decimal(2), Decimal(50), Decimal(30), False)).cost is None


@pytest.mark.parametrize("number", ["NaN", "Infinity", "0", "-1"])
def test_invalid_prices_are_never_trustworthy(number: str) -> None:
    with pytest.raises(InvalidInputError):
        value_stock(StockMark("USD", Decimal(1), Decimal(number), None))
