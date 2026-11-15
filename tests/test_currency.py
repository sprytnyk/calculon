"""Exchange rate parsing."""

from decimal import Decimal

import pytest

from calculon.engine.currency import RatesError, RateTable


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
