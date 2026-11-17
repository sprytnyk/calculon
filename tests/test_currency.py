"""Exchange rate parsing."""

from decimal import Decimal

import pytest

from calculon.engine.currency import RatesError, RateTable


def test_parse_frankfurter_v2_rates() -> None:
    table = RateTable.parse(
        '[{"date":"2026-11-16","base":"USD","quote":"EUR","rate":0.9},'
        '{"date":"2026-11-16","base":"USD","quote":"GBP","rate":0.8}]'
    )
    assert table.base == "USD"
    assert table.rates == {"USD": Decimal(1), "EUR": Decimal("0.9"), "GBP": Decimal("0.8")}


@pytest.mark.parametrize(
    "value",
    [
        '"NaN"',
        '"sNaN"',
        '"-NaN"',
        '"NaN123"',
        "NaN",
        '"Infinity"',
        '"-Infinity"',
        "Infinity",
        "-Infinity",
        "1e9999",
        "-1e9999",
        "0",
        "-1",
        '"invalid"',
    ],
)
def test_parse_skips_unusable_rates(value: str) -> None:
    table = RateTable.parse('{"rates": {"EUR": ' + value + ', "GBP": 0.8}}')
    assert table.rates == {"USD": Decimal(1), "GBP": Decimal("0.8")}

    with pytest.raises(RatesError, match="no usable rates in the document"):
        RateTable.parse('{"rates": {"EUR": ' + value + "}}")
