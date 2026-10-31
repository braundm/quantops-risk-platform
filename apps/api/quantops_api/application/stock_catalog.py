"""Fixed US and Polish equity catalog; inclusion is not an investment recommendation."""

from pydantic import BaseModel, ConfigDict, field_validator
from quantops_domain.value_objects import ISO_4217_CODES


class Stock(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    name: str
    market: str
    currency: str

    @field_validator("currency")
    @classmethod
    def iso_currency(cls, value: str) -> str:
        if value not in ISO_4217_CODES:
            raise ValueError("Currency must be an ISO 4217 code")
        return value


US = [
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("NVDA", "NVIDIA"),
    ("AMZN", "Amazon"),
    ("GOOGL", "Alphabet"),
    ("META", "Meta Platforms"),
    ("TSLA", "Tesla"),
    ("BRK-B", "Berkshire Hathaway B"),
    ("JPM", "JPMorgan Chase"),
    ("V", "Visa"),
    ("MA", "Mastercard"),
    ("JNJ", "Johnson & Johnson"),
    ("PG", "Procter & Gamble"),
    ("KO", "Coca-Cola"),
    ("PEP", "PepsiCo"),
    ("WMT", "Walmart"),
    ("COST", "Costco"),
    ("XOM", "Exxon Mobil"),
    ("CVX", "Chevron"),
    ("DIS", "Walt Disney"),
]
# Large Warsaw-listed companies from the WIG20 universe, checked on 2026-10-05.
# This fixed catalog does not track future index rebalances.
PL = [
    ("PKO.WA", "PKO Bank Polski"),
    ("PKN.WA", "ORLEN"),
    ("KGH.WA", "KGHM"),
    ("PEO.WA", "Bank Pekao"),
    ("ALE.WA", "Allegro"),
    ("PZU.WA", "PZU"),
    ("EBP.WA", "Erste Bank Polska"),
    ("LPP.WA", "LPP"),
    ("MBK.WA", "mBank"),
    ("DNP.WA", "Dino Polska"),
    ("CDR.WA", "CD Projekt"),
    ("ZAB.WA", "Żabka Group"),
    ("PGE.WA", "PGE"),
    ("ALR.WA", "Alior Bank"),
    ("KTY.WA", "Grupa Kęty"),
    ("TPE.WA", "Tauron"),
    ("BDX.WA", "Budimex"),
    ("PCO.WA", "Pepco Group"),
    ("KRU.WA", "Kruk"),
    ("MDV.WA", "Modivo"),
]
STOCKS = tuple(
    [Stock(symbol=s, name=n, market="US", currency="USD") for s, n in US]
    + [Stock(symbol=s, name=n, market="PL", currency="PLN") for s, n in PL]
)
BY_SYMBOL = {stock.symbol: stock for stock in STOCKS}
