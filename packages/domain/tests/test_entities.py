from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from quantops_domain import (
    AssetClass,
    Currency,
    CurrencyMismatchError,
    DomainValidationError,
    Instrument,
    Money,
    OptimisticConcurrencyError,
    Portfolio,
    Position,
)

NOW = datetime(2026, 1, 15, 12, 30, tzinfo=UTC)
INSTRUMENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PORTFOLIO_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
POSITION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def make_instrument(**overrides: object) -> Instrument:
    arguments: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "source": " Synthetic ",
        "symbol": " qspx ",
        "name": "QuantOps Equity Index",
        "asset_class": AssetClass.EQUITY_INDEX,
        "quote_currency": "usd",
        "price_scale": 4,
        "timezone": "UTC",
        "calendar": "WEEKDAY",
        "is_demo": True,
        "now": NOW,
        "metadata": {"sector": "broad_market", "aliases": ["QSPX-DEMO"]},
    }
    arguments.update(overrides)
    return Instrument.create(**arguments)  # type: ignore[arg-type]


def make_portfolio(**overrides: object) -> Portfolio:
    arguments: dict[str, object] = {
        "portfolio_id": PORTFOLIO_ID,
        "name": "Demo Portfolio",
        "base_currency": "USD",
        "description": "Synthetic multi-asset exposures",
        "is_demo": True,
        "now": NOW,
    }
    arguments.update(overrides)
    return Portfolio.create(**arguments)  # type: ignore[arg-type]


class InstrumentTests(unittest.TestCase):
    def test_factory_canonicalizes_identity_currency_and_utc(self) -> None:
        offset_now = datetime(2026, 1, 15, 13, 30, tzinfo=timezone(timedelta(hours=1)))
        instrument = make_instrument(now=offset_now)

        self.assertEqual(instrument.source, "synthetic")
        self.assertEqual(instrument.symbol.value, "QSPX")
        self.assertEqual(instrument.quote_currency.code, "USD")
        self.assertEqual(instrument.created_at, NOW)
        self.assertEqual(instrument.identity.source, "synthetic")

    def test_metadata_is_deeply_immutable(self) -> None:
        instrument = make_instrument()

        with self.assertRaises(TypeError):
            instrument.metadata["new"] = "value"  # type: ignore[index]
        aliases = instrument.metadata["aliases"]
        self.assertIsInstance(aliases, tuple)

    def test_metadata_rejects_arbitrary_executable_values(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "unsupported JSON value"):
            make_instrument(metadata={"callback": lambda: None})

    def test_naive_timestamps_and_nil_uuids_are_rejected(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "timezone-aware"):
            make_instrument(now=NOW.replace(tzinfo=None))
        with self.assertRaisesRegex(DomainValidationError, "nil UUID"):
            make_instrument(instrument_id=UUID(int=0))

    def test_entity_itself_is_immutable(self) -> None:
        instrument = make_instrument()

        with self.assertRaises(FrozenInstanceError):
            instrument.name = "changed"  # type: ignore[misc]


class PortfolioTests(unittest.TestCase):
    def test_create_starts_at_version_one(self) -> None:
        portfolio = make_portfolio()

        self.assertEqual(portfolio.version, 1)
        self.assertEqual(portfolio.base_currency.code, "USD")

    def test_revise_checks_expected_version_and_returns_new_aggregate(self) -> None:
        portfolio = make_portfolio()
        revised = portfolio.revise(
            expected_version=1,
            updated_at=NOW + timedelta(minutes=1),
            name="Renamed Portfolio",
        )

        self.assertEqual(portfolio.version, 1)
        self.assertEqual(revised.version, 2)
        self.assertEqual(revised.name, "Renamed Portfolio")
        self.assertEqual(revised.updated_at, NOW + timedelta(minutes=1))

    def test_stale_revision_fails_with_conflict_metadata(self) -> None:
        portfolio = make_portfolio().revise(
            expected_version=1,
            updated_at=NOW + timedelta(minutes=1),
            name="Version Two",
        )

        with self.assertRaises(OptimisticConcurrencyError) as raised:
            portfolio.revise(
                expected_version=1,
                updated_at=NOW + timedelta(minutes=2),
                name="Stale Write",
            )
        self.assertEqual(raised.exception.expected, 1)
        self.assertEqual(raised.exception.actual, 2)
        self.assertEqual(raised.exception.aggregate_id, PORTFOLIO_ID)

    def test_semantic_noop_does_not_churn_version(self) -> None:
        portfolio = make_portfolio()

        unchanged = portfolio.revise(
            expected_version=1,
            updated_at=NOW + timedelta(minutes=1),
            name="  Demo Portfolio  ",
        )

        self.assertIs(unchanged, portfolio)

    def test_update_time_cannot_move_backwards(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "move backwards"):
            make_portfolio().revise(
                expected_version=1,
                updated_at=NOW - timedelta(seconds=1),
                name="Invalid",
            )


class PositionTests(unittest.TestCase):
    def make_position(self, **overrides: object) -> Position:
        arguments: dict[str, object] = {
            "position_id": POSITION_ID,
            "portfolio_id": PORTFOLIO_ID,
            "instrument_id": INSTRUMENT_ID,
            "quantity": Decimal("-2.5"),
            "average_cost": Decimal("100.10"),
            "currency": "USD",
            "as_of": NOW,
            "tags": {"Book": "macro", "risk_bucket": "index"},
        }
        arguments.update(overrides)
        return Position.create(**arguments)  # type: ignore[arg-type]

    def test_signed_quantity_and_exact_cost_basis_are_supported(self) -> None:
        position = self.make_position()

        self.assertEqual(position.quantity, Decimal("-2.5"))
        self.assertEqual(position.cost_basis.amount, Decimal("-250.250"))
        self.assertEqual(position.tags["book"], "macro")

    def test_market_value_requires_position_currency(self) -> None:
        position = self.make_position(quantity=Decimal("3"))

        self.assertEqual(
            position.market_value(Money(Decimal("12.50"), position.currency)).amount,
            Decimal("37.50"),
        )
        with self.assertRaises(CurrencyMismatchError):
            position.market_value(Money(Decimal("12.50"), Currency("EUR")))

    def test_quantity_rejects_float_and_average_cost_rejects_negative(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "must be Decimal"):
            self.make_position(quantity=1.5)
        with self.assertRaisesRegex(DomainValidationError, "greater than or equal"):
            self.make_position(average_cost=Decimal("-0.01"))

    def test_tags_are_bounded_and_immutable(self) -> None:
        too_many = {f"tag{index}": "x" for index in range(21)}
        with self.assertRaisesRegex(DomainValidationError, "at most 20"):
            self.make_position(tags=too_many)

        position = self.make_position()
        with self.assertRaises(TypeError):
            position.tags["book"] = "changed"  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
