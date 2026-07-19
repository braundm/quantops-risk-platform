"""Immutable financial and identity value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from quantops_domain._validation import fail, require_decimal, require_text
from quantops_domain.errors import CurrencyMismatchError, DomainValidationError

# A deliberately version-controlled ISO 4217 allow-list. Historical codes remain
# accepted so persisted records do not become unreadable after a currency transition.
ISO_4217_CODES = frozenset(
    """
    AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL
    BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK
    DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL
    HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT
    LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR
    MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR
    SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY
    TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA
    XBB XBC XBD XCD XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWL
    """.split()  # noqa: SIM905 - this version-controlled ISO code table is easier to audit
)

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{0,31}$")


@dataclass(frozen=True, slots=True, order=True)
class Currency:
    """A canonical ISO 4217 alphabetic code."""

    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            fail("currency", "must be a string")
        canonical = self.code.strip().upper()
        if canonical not in ISO_4217_CODES:
            raise DomainValidationError(f"currency: {canonical!r} is not an ISO 4217 code")
        object.__setattr__(self, "code", canonical)

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True, order=True)
class InstrumentSymbol:
    """A canonical exchange/source symbol used in instrument identity."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            fail("symbol", "must be a string")
        canonical = self.value.strip().upper()
        if _SYMBOL_PATTERN.fullmatch(canonical) is None:
            fail("symbol", "must be 1-32 canonical market-symbol characters")
        object.__setattr__(self, "value", canonical)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class InstrumentIdentity:
    """Unique source/symbol identity independent from the database identifier."""

    source: str
    symbol: InstrumentSymbol

    def __post_init__(self) -> None:
        source = require_text(self.source, "source", maximum=64).casefold()
        if not isinstance(self.symbol, InstrumentSymbol):
            fail("symbol", "must be InstrumentSymbol")
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount tagged with currency; no implicit conversion is allowed."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        require_decimal(self.amount, "amount")
        if not isinstance(self.currency, Currency):
            fail("currency", "must be Currency")

    def _same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(str(self.currency), str(other.currency))

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __mul__(self, multiplier: object) -> Money:
        if not isinstance(multiplier, Decimal):
            return NotImplemented
        require_decimal(multiplier, "multiplier")
        return Money(self.amount * multiplier, self.currency)

    def __rmul__(self, multiplier: object) -> Money:
        return self.__mul__(multiplier)
