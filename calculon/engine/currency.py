"""Currency codes, symbols and the exchange rate table."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

# ISO 4217 codes recognised even before any rates are loaded.
_CODES = """
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN
BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD
FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY
KES KGS KHR KMF KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU
MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON
RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SYP SZL THB TJS TMT TND TOP
TRY TTD TWD TZS UAH UGX USD UYU UZS VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWL
"""
KNOWN_CODES = frozenset(_CODES.split())

# Symbols typed before a number. "$" is resolved from settings.
PREFIX_SYMBOLS: dict[str, str] = {
    "US$": "USD",
    "NZ$": "NZD",
    "C$": "CAD",
    "CA$": "CAD",
    "A$": "AUD",
    "AU$": "AUD",
    "S$": "SGD",
    "NT$": "TWD",
    "HK$": "HKD",
    "R$": "BRL",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₴": "UAH",
    "₹": "INR",
    "₽": "RUB",
    "₩": "KRW",
    "₺": "TRY",
    "₪": "ILS",
    "₫": "VND",
    "₱": "PHP",
    "฿": "THB",
    "₦": "NGN",
    "₸": "KZT",
    "₾": "GEL",
    "zł": "PLN",
}

# Currency names (case-insensitive). "pound" is left out: Soulver reads it as mass.
NAMES: dict[str, str] = {
    "dollar": "USD",
    "dollars": "USD",
    "euro": "EUR",
    "euros": "EUR",
    "yen": "JPY",
    "yuan": "CNY",
    "rupee": "INR",
    "rupees": "INR",
    "hryvnia": "UAH",
    "hryvnias": "UAH",
    "hryvnas": "UAH",
    "uah": "UAH",
    "zloty": "PLN",
    "zlotys": "PLN",
    "franc": "CHF",
    "francs": "CHF",
    "sterling": "GBP",
    "quid": "GBP",
    # Ukrainian ("фунт" stays a mass unit, like "pound")
    "грн": "UAH",
    "гривня": "UAH",
    "гривні": "UAH",
    "гривень": "UAH",
    "гривню": "UAH",
    "гривнях": "UAH",
    "долар": "USD",
    "долари": "USD",
    "доларів": "USD",
    "долара": "USD",
    "доларах": "USD",
    "дол": "USD",
    "євро": "EUR",
    "злотий": "PLN",
    "злоті": "PLN",
    "злотих": "PLN",
    "злотого": "PLN",
    "франк": "CHF",
    "франки": "CHF",
    "франків": "CHF",
    "єна": "JPY",
    "єни": "JPY",
    "єн": "JPY",
    "юань": "CNY",
    "юані": "CNY",
    "юанів": "CNY",
}

# Symbol used when showing a result; everything else is shown as "12.00 CHF".
DISPLAY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "UAH": "₴",
    "INR": "₹",
    "KRW": "₩",
    "ILS": "₪",
    "TRY": "₺",
    "RUB": "₽",
}

ZERO_DECIMALS = {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "PYG", "UGX", "XAF", "XOF"}


class RatesError(ValueError):
    pass


@dataclass
class RateTable:
    """Rates as 'units of CODE per 1 unit of base'."""

    base: str = "USD"
    rates: dict[str, Decimal] = field(default_factory=dict)
    updated: float = 0.0  # unix time of the source's last update
    source: str = ""

    def __post_init__(self) -> None:
        self.rates.setdefault(self.base, Decimal(1))

    def has(self, code: str) -> bool:
        return code in self.rates

    def rate(self, src: str, dst: str) -> Decimal:
        """How many dst for one src."""
        if src == dst:
            return Decimal(1)
        try:
            return self.rates[dst] / self.rates[src]
        except KeyError as exc:
            raise RatesError(f"no exchange rate for {exc.args[0]}") from exc

    # --- (de)serialisation -------------------------------------------------

    @classmethod
    def parse(cls, payload: bytes | str, source: str = "") -> RateTable:
        """Parse a rates JSON document.

        Accepted format (also matches open.er-api.com and Frankfurter):
            {"base": "USD", "rates": {"EUR": 0.92, "UAH": 41.3, ...}}
        "base_code" may be used instead of "base"; it defaults to USD. Each rate is
        how many units of that currency one unit of the base buys. An optional
        "time_last_update_unix" (or "updated", unix seconds, or "date", YYYY-MM-DD)
        is kept for display.
        """
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RatesError(f"not JSON: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("rates"), dict):
            raise RatesError('expected an object with a "rates" object')
        base = str(data.get("base") or data.get("base_code") or "USD").upper()
        rates: dict[str, Decimal] = {}
        for code, value in data["rates"].items():
            if not isinstance(code, str) or not isinstance(value, int | float | str):
                continue
            try:
                dec = Decimal(str(value))
            except ArithmeticError:
                continue
            if dec > 0 and len(code) == 3 and code.isalpha():
                rates[code.upper()] = dec
        if not rates:
            raise RatesError("no usable rates in the document")
        updated = data.get("time_last_update_unix") or data.get("updated")
        if updated is None and isinstance(data.get("date"), str):
            try:
                updated = datetime.fromisoformat(data["date"]).replace(tzinfo=UTC).timestamp()
            except ValueError:
                updated = None
        try:
            updated = float(updated) if updated is not None else time.time()
        except TypeError, ValueError:
            updated = time.time()
        return cls(base=base, rates=rates, updated=updated, source=source)

    def to_json(self) -> str:
        return json.dumps(
            {
                "base": self.base,
                "rates": {k: str(v) for k, v in sorted(self.rates.items())},
                "updated": self.updated,
                "source": self.source,
            },
            indent=1,
        )


def display(code: str) -> tuple[str, bool]:
    """Return (text, is_prefix) for a currency code."""
    sym = DISPLAY_SYMBOLS.get(code)
    if sym:
        return sym, True
    return code, False
