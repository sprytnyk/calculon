"""Engine tests, mostly examples from Soulver's documentation."""

import time
from datetime import datetime
from decimal import Decimal

import pytest

from calculon.engine import Config, FormatOptions, RateTable, evaluate_sheet

RATES = RateTable(
    base="USD",
    rates={
        "EUR": Decimal("0.9"),
        "GBP": Decimal("0.8"),
        "UAH": Decimal("41"),
        "AUD": Decimal("1.5"),
        "JPY": Decimal("150"),
    },
)
NOW = datetime(2026, 11, 10, 18, 30)
CONFIG = Config(now=lambda: NOW)


def calc(text: str, **opts) -> list[str]:
    res = evaluate_sheet(text, RATES, CONFIG, FormatOptions(**opts))
    return [line.text for line in res.lines]


def one(text: str, **opts) -> str:
    return calc(text, **opts)[-1]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # operators
        ("3 × 3", "9"),
        ("2 + 3 * 4", "14"),
        ("(2 + 3) * 4", "20"),
        ("2(3 + 4)", "14"),
        ("-2^2", "-4"),
        ("2^3^2", "512"),
        ("30 plus 20", "50"),
        ("3,000 minus 12", "2,988"),
        ("3 multiplied by 4", "12"),
        ("1,000 divided by 200", "5"),
        ("3 to the power of 2", "9"),
        ("remainder of 21 divided by 5", "1"),
        ("21 mod 5", "1"),
        ("20 % 3", "2"),
        ("10 / 4", "2.5"),
        ("1 / 3", "0.333333"),
        ("10!", "3,628,800"),
        ("5 squared", "25"),
        # percentages
        ("120 + 30%", "156"),
        ("30% of 700", "210"),
        ("10% + 20%", "30%"),
        ("50% × 30", "15"),
        ("30 × 50%", "15"),
        ("100% + 2 + 30%", "330%"),
        ("90% − 40%", "50%"),
        ("30% + 0.4", "70%"),
        ("200 - 10%", "180"),
        ("10% on 200", "220"),
        ("10% off 200", "180"),
        ("20 is 10% of what", "200"),
        ("180 is 10% off what", "200"),
        ("220 is 10% on what", "200"),
        ("50 to 75 is what %", "50%"),
        ("40 to 90 as %", "125%"),
        ("180 is what % off 200", "10%"),
        ("180 is what % on 150", "20%"),
        ("20 is what % of 200", "10%"),
        ("20 as a % of 200", "10%"),
        ("20/200 as %", "10%"),
        ("0.35 as %", "35%"),
        ("2/5 as percent", "40%"),
        ("3/20 is what %", "15%"),
        ("3 in 20 is what %", "15%"),
        ("20% is 500, what is 750", "30%"),
        ("if 20 is 30%, what is 60%", "40"),
        ("2/10 as fraction", "1/5"),
        ("50% as fraction", "1/2"),
        ("5% is 1 in what", "1/20"),
        ("40% is 1 in what", "1/2.5"),
        ("2/3 of 600", "400"),
        ("50 is 1/5 of what", "250"),
        ("20/5 as multiplier", "4x"),
        ("50 as x of 5", "10x"),
        ("2 as multiplier on 1", "1x"),
        ("1 as x off 2", "0.5x"),
        ("50 to 75 is what x", "1.5x"),
        ("20 to 40 as x", "2x"),
        # currencies
        ("$19 for breakfast + $22 for the uber", "$41.00"),
        ("10 USD in EUR", "€9.00"),
        ("10 usd in eur", "€9.00"),
        ("20 GBP as AUD", "37.50 AUD"),
        ("50 EUR in USD at 1.05 USD/EUR", "$52.50"),
        ("$200 + €200", "€380.00"),
        ("$20 + 30", "$50.00"),
        ("1000 UAH in USD", "$24.39"),
        ("₴1000 in $", "$24.39"),
        ("¥1500", "¥1,500"),
        ("100 euros in dollars", "$111.11"),
        ("$3k", "$3,000.00"),
        ("$5m", "$5,000,000.00"),
        ("$7bn", "$7,000,000,000.00"),
        ("$3 million", "$3,000,000.00"),
        ("-$5 + $2", "-$3.00"),
        # units
        ("10 km in m", "10,000 m"),
        ("5 hours 30 minutes to seconds", "19,800 seconds"),
        ("100 pounds in kg", "45.359237 kg"),
        ("meters in 10 km", "10,000 m"),
        ("days in 3 weeks", "21 days"),
        ("seconds in a day", "86,400 seconds"),
        ("km m", "1,000 m"),
        ("5 km cast miles", "5 mi"),
        ("300 + 20 km", "320 km"),
        ("1km + 1,000m", "2 km"),
        ("10m × 10m", "100 m²"),
        ("10m", "10 m"),
        ("20 sq m * 3", "60 m²"),
        ("100 °C in °F", "212 °F"),
        ("1 GB in MB", "1,000 MB"),
        ("1 GiB in MiB", "1,024 MiB"),
        ("60 mph in km/h", "96.56064 km/h"),
        ("2 cups of flour", "2 cups"),
        # rates
        ("$30 × 4 days", "$120.00"),
        ("3 hours / day", "3 hours/day"),
        ("$99 per week", "$99.00/week"),
        ("$20/day + $300/week", "$440.00/week"),
        ("90 km / 3 day", "30 km/day"),
        ("$50/week × 12 weeks", "$600.00"),
        ("30 hours at $30/hour", "$900.00"),
        ("$500 at $20/hour", "25 hours"),
        ("3 hours / 3 days", "0.041667"),
        ("€30/day in €/month", "€913.13/month"),
        ("$24 a day for a year", "$8,766.00"),
        # numbers
        ("2.5k", "2,500"),
        ("5M", "5,000,000"),
        ("1_000_000 + 2_000", "1,002,000"),
        ("0b_1100_0001 to decimal", "193"),
        ("0xff + 1", "0x100"),
        ("255 as hex", "0xFF"),
        ("5 as binary", "0b101"),
        ("3 million + 10%", "3,300,000"),
        ("1.5e3", "1,500"),
        ("123456789 as sci", "1.234568e8"),
        # functions
        ("sqrt 16", "4"),
        ("sqrt(2)", "1.414214"),
        ("square root of 81", "9"),
        ("round(3.14159, 2)", "3.14"),
        ("floor(2.7)", "2"),
        ("ceil(2.1)", "3"),
        ("sin(90°)", "1"),
        ("cos(0)", "1"),
        ("log 1000", "3"),
        ("abs(-4)", "4"),
        ("pi * 2", "6.283185"),
        # statistics
        ("total of 3, 4, 7 and 9", "23"),
        ("average of 36, 42, 19 and 81", "44.5"),
        ("count of 1, 2, 3, 4, 5", "5"),
        ("median of 10, 20 and 30", "20"),
        ("standard deviation of 20, 30 and 40", "10"),
        # comments, labels, quotes
        ("Cost of 128 GB iPhone 16: $999", "$999.00"),
        ("I spent $128 + $45 on clothes // on 10-02-2019", "$173.00"),
        ("$999 (for iPhone 16)", "$999.00"),
        ('Boing "747" is $386.8M', "$386,800,000.00"),
        ("// 1 + 2", ""),
        ("# Heading 2024", ""),
        ("just some words", ""),
        ("Room 101 costs $45", "$45.00"),
        ("4 people × $20", "$80.00"),
        # dates (today is 10 Nov 2026, 18:30)
        ("10 June + 3 weeks", "1 July"),
        ("April 1, 2019 − 3 months 5 days", "27 December 2018"),
        ("12/02/1988 + 32 years", "12 February 2020"),
        ("01.05.2005 + 3 years 2 months 3 weeks", "22 July 2008"),
        ("2024-03-15 + 1 day", "16 March 2024"),
        ("3 weeks after March 14, 2019", "4 April 2019"),
        ("28 days before March 12", "12 February"),
        ("today + 3 weeks", "1 December"),
        ("4 days from now", "14 November"),
        ("3 days ago", "7 November"),
        ("January 10 - February 5", "3 weeks 5 days"),
        ("3 March to 30 May", "2 months 3 weeks 6 days"),
        ("days since July 15", "118 days"),
        ("days till December 25", "45 days"),
        ("days between 3 March and 30 May", "88 days"),
        ("April 1 through April 30 in days", "30 days"),
        ("midpoint between March 12 and April 5", "24 March"),
        ("Feb 28 + 1 month", "28 March"),
        ("January 31 2020 + 1 month", "29 February 2020"),
        ("7:45am - 4:20pm", "8 hours 35 minutes"),
        ("9:00 + 90 minutes", "10:30"),
        ("next friday", "13 November"),
        ("March 1st + 1 week", "8 March"),
    ],
)
def test_line(line: str, expected: str) -> None:
    assert one(line) == expected


def test_variables() -> None:
    out = calc(
        "discount = 10%\ncost = $550\ncost - discount\n"
        "monthly rent = $1,900 // 2018\nmonthly rent = $2,150 // 2019\nmonthly rent / 4 people"
    )
    assert out == ["10%", "$550.00", "$495.00", "$1,900.00", "$2,150.00", "$537.50"]


def test_compound_assignment() -> None:
    assert calc("x = 5\nx += 2\nx -= 1\nx * 2") == ["5", "7", "6", "12"]


def test_divider_resets_variables() -> None:
    assert calc("a = 5\na\n---\na") == ["5", "5", "", ""]


def test_line_references_and_continuation() -> None:
    assert calc("10\n20\nline1 + line2\n+ 5\n* 2\nprev / 7") == [
        "10",
        "20",
        "30",
        "35",
        "70",
        "10",
    ]


def test_totals_stop_at_heading_and_previous_total() -> None:
    text = "# Food\n$20 lunch\n$30 dinner\ntotal\n$5 tip\nsubtotal\n# Rent\n$900\ntotal"
    assert calc(text) == [
        "",
        "$20.00",
        "$30.00",
        "$50.00",
        "$5.00",
        "$5.00",
        "",
        "$900.00",
        "$900.00",
    ]


def test_total_assigned_to_variable() -> None:
    assert calc("$10\n$15\nfood = total\nfood * 2") == ["$10.00", "$15.00", "$25.00", "$50.00"]


def test_average_of_lines() -> None:
    assert calc("10\n20\n30\naverage") == ["10", "20", "30", "20"]


def test_total_mixed_currencies_uses_last() -> None:
    assert calc("$90\n€90\ntotal") == ["$90.00", "€90.00", "€171.00"]


def test_tags() -> None:
    text = "$20 lunch #food\n$15 taxi #travel\n$30 dinner #food\ntotal of #food\naverage of #food"
    assert calc(text)[-2:] == ["$50.00", "$25.00"]


def test_sheet_total() -> None:
    res = evaluate_sheet("$10\n$20\ntotal\n$5", RATES, CONFIG)
    assert res.total is not None
    assert res.total.mag == Decimal(35)


def test_number_styles() -> None:
    assert one("1.234,5 + 1", number_style="dot_comma") == "1.235,5"
    assert one("1 234,5 + 1", number_style="space_comma") == "1 235,5"
    assert one("1234.5", number_style="space_comma") == "1 234,5"
    assert one("total of 1,5 and 2", number_style="dot_comma") == "3,5"


def test_decimal_settings() -> None:
    assert one("1/3", max_decimals=2) == "0.33"
    assert one("$10/3", money_decimals=3) == "$3.333"


def test_date_order_setting() -> None:
    cfg = Config(now=lambda: NOW, date_order="MDY")
    res = evaluate_sheet("02/12/2020", RATES, cfg)
    assert res.lines[0].text == "12 February 2020"


def test_missing_rate_gives_no_answer() -> None:
    assert one("10 CHF in USD") == ""


def test_division_by_zero_gives_no_answer() -> None:
    assert one("5 / 0") == ""


def test_huge_power_is_refused() -> None:
    assert one("9^9^9") == ""


def test_highlight_spans() -> None:
    res = evaluate_sheet("rent = $900 // monthly", RATES, CONFIG)
    kinds = {cls for _, _, cls in res.lines[0].spans}
    assert {"variable", "unit", "number", "comment"} <= kinds


def test_custom_units_from_rates() -> None:
    assert calc("hotel = €95/night × 5 nights\n$12 per seat\n3 seats × $12/seat") == [
        "€475.00",
        "$12.00/seat",
        "$36.00",
    ]
    assert one("€95/night") == "€95.00/night"


def test_line_total_uses_main_unit_kind() -> None:
    text = "flights = $420 × 2\npeople = 3\n€240\n10 km in miles\ntotal"
    assert calc(text)[-1] == "€996.00"


def test_explicit_list_keeps_plain_numbers() -> None:
    assert one("total of $5, 3") == "$8.00"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("20²", "400"),
        ("2³ + 1", "9"),
        ("(1 + 2)²", "9"),
        ("3 m²", "3 m²"),
        ("٣ + 1", "4"),  # other scripts' digits are still digits
    ],
)
def test_superscript_powers(line: str, expected: str) -> None:
    assert one(line) == expected


def test_bad_input_gives_an_error_not_a_crash() -> None:
    """Found by fuzzing: each of these used to raise inside the engine or hang."""
    res = evaluate_sheet("1\nline 1e999999\n0^-1\n²", RATES, CONFIG, FormatOptions())
    assert [line.text for line in res.lines] == ["1", "1e999999", "", ""]
    assert res.lines[2].error == "division by zero"
    big = evaluate_sheet("1e25 км", RATES, CONFIG, FormatOptions(lang="uk"))
    assert big.lines[0].text == "1e25 км"
    assert calc("1e999999 as %") == [""]
    assert evaluate_sheet("9e999999\n9e999999", RATES, CONFIG).total is None
    # a maths error in one part of the line: the rest still gets a go
    line = evaluate_sheet("3 days 10% ago", RATES, CONFIG).lines[0]
    assert (line.text, line.error) == ("3 days", "")


@pytest.mark.parametrize("line", ["1e999999 in hex", "5 km^1e999999", "round(1.5; 1e999999)"])
def test_huge_numbers_answer_fast(line: str) -> None:
    """int(1e999999) takes about a minute, which froze the window."""
    start = time.perf_counter()
    one(line)
    assert time.perf_counter() - start < 1


def test_words_in_prose_are_not_coloured_as_keywords() -> None:
    def coloured(src: str) -> list[str]:
        res = evaluate_sheet(src, RateTable(), Config(), FormatOptions())
        return [src[a:b] for a, b, cls in res.lines[0].spans if cls == "keyword"]

    assert coloured("if I buy 3 apples") == []
    assert coloured("go to the shop 5") == []
    assert coloured("go to the shop") == []
    assert coloured("10 km to miles") == ["to"]
    assert coloured("if 20 is 30%, what is 60%") == ["if", "is", "what", "is"]


@pytest.mark.parametrize(
    ("line", "answer"),
    [
        ("100 Mbps in MB/s", "12.5 MB/s"),
        ("12.5 MB/s in Mbps", "100 Mbps"),
        ("100 MBps in Mbps", "800 Mbps"),
        ("1 GB/s in Gbps", "8 Gbps"),
        ("1 Tbps in Gbps", "1,000 Gbps"),
        ("100 bps in kbps", "0.1 kbps"),
        ("1 MiB/s in Mbps", "8.388608 Mbps"),
        ("100 Mbps + 10 MB/s", "180 Mbps"),
        ("10 GB / 100 Mbps", "800 seconds"),
        ("10 GB at 100 Mbps in minutes", "13.333333 minutes"),
        ("100 Mbps × 1 hour in GB", "45 GB"),
        ("10 km at 5 kph", "2 hours"),
        # lowercase, as people type it: mb is megabytes, mbps is megabits
        ("1 mbps in mb/s", "0.125 MB/s"),
        ("1 mbps in mbs", "0.125 MB/s"),
        ("1 MBs in Mbps", "8 Mbps"),
        ("500 mb in gb", "0.5 GB"),
        ("1 mbit in mb", "0.125 MB"),
        ("1 Mb in MB", "0.125 MB"),  # exact case stays SI
        ("10 gb at 100 mbps in minutes", "13.333333 minutes"),
    ],
)
def test_data_rates(line: str, answer: str) -> None:
    assert one(line) == answer


def test_data_rates_in_ukrainian() -> None:
    assert one("100 Мбіт/с у МБ/с", lang="uk") == "12.5 МБ/с"
    assert one("10 ГБ по 100 Мбіт/с у хвилинах", lang="uk") == "13.333333 хвилини"
    assert one("1 мбіт/с у мб/с", lang="uk") == "0.125 МБ/с"
