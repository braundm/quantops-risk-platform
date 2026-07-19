from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from quantops_domain import (
    Currency,
    CurrencyMismatchError,
    DomainValidationError,
    InstrumentIdentity,
    InstrumentSymbol,
    Money,
)


class CurrencyTests(unittest.TestCase):
    def test_currency_is_canonical_and_immutable(self) -> None:
        currency = Currency(" usd ")

        self.assertEqual(currency.code, "USD")
        self.assertEqual(str(currency), "USD")
        with self.assertRaises(FrozenInstanceError):
            currency.code = "EUR"  # type: ignore[misc]

    def test_currency_rejects_non_iso_code(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "ISO 4217"):
            Currency("ZZZ")

    def test_symbol_and_source_form_canonical_identity(self) -> None:
        identity = InstrumentIdentity(" Synthetic-Feed ", InstrumentSymbol(" qspx "))

        self.assertEqual(identity.source, "synthetic-feed")
        self.assertEqual(identity.symbol.value, "QSPX")

    def test_symbol_rejects_unsafe_characters(self) -> None:
        with self.assertRaises(DomainValidationError):
            InstrumentSymbol("SPX; DROP TABLE")


class MoneyTests(unittest.TestCase):
    def test_money_arithmetic_preserves_decimal_and_currency(self) -> None:
        left = Money(Decimal("10.10"), Currency("USD"))
        right = Money(Decimal("0.20"), Currency("USD"))

        self.assertEqual((left + right).amount, Decimal("10.30"))
        self.assertEqual((left - right).amount, Decimal("9.90"))
        self.assertEqual((Decimal("2.5") * right).amount, Decimal("0.500"))
        self.assertEqual((-right).amount, Decimal("-0.20"))

    def test_money_rejects_binary_float(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "must be Decimal"):
            Money(1.25, Currency("USD"))  # type: ignore[arg-type]

    def test_money_rejects_non_finite_decimal(self) -> None:
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with self.subTest(value=value), self.assertRaises(DomainValidationError):
                Money(value, Currency("USD"))

    def test_money_never_implicitly_converts_currency(self) -> None:
        usd = Money(Decimal("1"), Currency("USD"))
        eur = Money(Decimal("1"), Currency("EUR"))

        with self.assertRaises(CurrencyMismatchError):
            _ = usd + eur

    def test_money_rejects_float_multiplier(self) -> None:
        money = Money(Decimal("1"), Currency("USD"))

        with self.assertRaises(TypeError):
            _ = money * 2.0


if __name__ == "__main__":
    unittest.main()
