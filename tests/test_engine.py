"""Engine tests, mostly examples from Soulver's documentation."""

import time
from datetime import datetime
from decimal import Decimal

import pytest

from calculon.engine import Config, FormatOptions, RateTable, evaluate_sheet, format_value
from calculon.engine.interpreter import Parser
from calculon.engine.values import DateVal

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


@pytest.mark.parametrize(
    "text", ["sqrt(-1)", "100 + sqrt(-1)", "2 * (3 +)", "2 + (3 +", "1 + 2) + 4"]
)
def test_invalid_math_never_becomes_a_partial_answer(text: str) -> None:
    line = evaluate_sheet(text, RATES, CONFIG).lines[0]
    assert line.value is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sqrt(1e-400)", "1e-200"),
        ("square root of 1e400", "1e200"),
        ("sqrt(4e-400 m²)", "2e-200 m"),
    ],
)
def test_square_root_handles_decimal_exponents(text: str, expected: str) -> None:
    assert one(text) == expected


def test_square_root_rejects_even_tiny_negative_numbers() -> None:
    line = evaluate_sheet("sqrt(-1e-400)", RATES, CONFIG).lines[0]
    assert line.value is None
    assert line.error == "invalid function argument"


@pytest.mark.parametrize("operator", ["*", "/", "^"])
def test_malformed_formula_does_not_return_its_last_number(operator: str) -> None:
    line = evaluate_sheet(f"2 + {operator} 3", RATES, CONFIG).lines[0]
    assert line.value is None
    assert line.error


def test_long_malformed_formula_is_not_reparsed_at_every_operator(monkeypatch) -> None:
    original = Parser.statement
    attempts = 0

    def count_attempt(parser):
        nonlocal attempts
        attempts += 1
        return original(parser)

    monkeypatch.setattr(Parser, "statement", count_attempt)
    text = " + ".join(["1"] * 80) + " + * 3"
    evaluate_sheet(text, RATES, CONFIG)
    assert attempts <= 3


@pytest.mark.parametrize("rate", ["0", "-1"])
def test_custom_exchange_rate_must_be_positive(rate: str) -> None:
    line = evaluate_sheet(f"50 EUR in USD at {rate} USD/EUR", RATES, CONFIG).lines[0]
    assert line.value is None


def test_failed_assignment_does_not_reuse_old_value() -> None:
    lines = evaluate_sheet(
        "rent = 1900\nrent = 1/0\nrent / 2\nrent += 10\nrent = 2000\nrent / 2",
        RATES,
        CONFIG,
    ).lines
    assert lines[2].value is None
    assert lines[2].hints == []
    assert lines[3].value is None
    assert lines[-1].value.mag == 1000
    assert lines[-1].hints == [(0, 4, "2,000")]


@pytest.mark.parametrize(
    ("input_text", "error"),
    [
        ("1e9999999999999999999", "invalid number"),
        ("Aprıl 5", "no such date"),
        ("Aprıl 2026", "no such date"),
    ],
)
def test_invalid_lexed_assignment_clears_old_value(input_text: str, error: str) -> None:
    lines = evaluate_sheet(
        f"budget = 100\nbudget = {input_text}\nbudget * 2\n2 + 2", RATES, CONFIG
    ).lines
    assert lines[1].value is None
    assert lines[1].error == error
    assert lines[2].value is None
    assert lines[2].error == "budget has no value"
    assert lines[3].text == "4"


@pytest.mark.parametrize("reference", ["line999", "line 999", "line2"])
def test_missing_line_reference_cannot_overwrite_variable(reference: str) -> None:
    lines = evaluate_sheet(
        f"balance = 100\nbalance = {reference} + 1\nbalance * 2", RATES, CONFIG
    ).lines
    assert lines[1].error == "no such line"
    assert lines[1].value is None
    assert lines[2].error == "balance has no value"
    assert lines[2].value is None


@pytest.mark.parametrize(
    "text",
    ["10 + unknown_variable", "10 + unknown fee + 5", "unknown_variable + 10", "(8 + unknown)"],
)
def test_unknown_operand_gives_an_error_instead_of_a_partial_answer(text) -> None:
    line = evaluate_sheet(text, RATES, CONFIG).lines[0]
    assert line.value is None
    assert "is not defined" in line.error


@pytest.mark.parametrize("clock", ["24:30", "12:60", "15:00pm", "0am", "08:15:60"])
def test_invalid_time_is_not_reduced_to_a_number_or_date(clock) -> None:
    text = f"Meeting: 2026-11-18 {clock}"
    line = evaluate_sheet(text, RATES, CONFIG).lines[0]
    assert line.value is None
    assert line.error == "no such time"
    assert (20, len(text), "invalid_time") in line.spans


def calc(text: str, **opts) -> list[str]:
    res = evaluate_sheet(text, RATES, CONFIG, FormatOptions(**opts))
    return [line.text for line in res.lines]


def one(text: str, **opts) -> str:
    return calc(text, **opts)[-1]


@pytest.mark.parametrize(
    ("text", "expected"), [("11 Dec", "11 December"), ("11 Oct", "11 October")]
)
def test_abbreviated_month_after_day(text: str, expected: str) -> None:
    assert one(text) == expected


@pytest.mark.parametrize(
    ("text", "style", "expected"),
    [
        ("$1000.1", "comma_dot", "$1,000.10"),
        ("100\u00a0500", "space_dot", "100\u202f500"),
        ("100\u2007500", "space_dot", "100\u202f500"),
        ("1) 100\u202f500 500", "space_comma", "100\u202f500\u202f500"),
        ("1. 100 500 500", "space_dot", "100\u202f500\u202f500"),
        ("• 100\u2009500,5", "space_comma", "100\u202f500,5"),
        ("$75.000,00", "dot_comma", "$75.000,00"),
        ("100.111,1", "dot_comma", "100.111,1"),
    ],
)
def test_pasted_number_formats(text: str, style: str, expected: str) -> None:
    result = evaluate_sheet(text, RATES, CONFIG, FormatOptions(number_style=style)).lines[0]
    assert result.text == expected
    start = text.index("100") if "100" in text else text.index("75")
    assert (start, len(text), "number") in result.spans


@pytest.mark.parametrize(
    ("style", "text"),
    [
        ("comma_dot", "100 100 1000"),
        ("space_comma", "100 100 1000"),
        ("comma_dot", "100.111,1"),
        ("space_dot", "100.111,1"),
        ("space_comma", "100.111,1"),
        ("dot_comma", "1.234.5678"),
        ("comma_dot", "10 10 10 10 10"),
        ("comma_dot", "10 100 10 100 1000"),
        ("comma_dot", "100 100 1"),
        ("comma_dot", "100 100 100 1"),
        ("comma_dot", "1_000_000"),
        ("comma_dot", "1’234.5"),
        ("space_comma", "١٬٢٣٤٫٥"),
    ],
)
def test_invalid_number_does_not_return_a_partial_answer(style: str, text: str) -> None:
    result = evaluate_sheet(text, RATES, CONFIG, FormatOptions(number_style=style)).lines[0]
    assert result.value is None
    assert result.spans == [(0, len(text), "invalid_number")]


@pytest.mark.parametrize(
    ("style", "group", "point"),
    [
        ("comma_dot", ",", "."),
        ("dot_comma", ".", ","),
        ("space_dot", " ", "."),
        ("space_comma", " ", ","),
    ],
)
def test_invalid_number_does_not_return_a_partial_answer_during_editing(style, group, point):
    opts = FormatOptions(number_style=style)
    texts = [f"1{group}2", f"1{group}23", f"1{group}234{point}"]
    result = evaluate_sheet("\n".join(texts), RATES, CONFIG, opts)
    assert all(line.value is None and not line.error and not line.spans for line in result.lines)
    texts = [f"2 + 1{group}234{point}5", f"round({point}55; 1)", f"total of {point}5; 2"]
    result = evaluate_sheet("\n".join(texts), RATES, CONFIG, opts)
    assert [line.value.mag for line in result.lines] == [
        Decimal("1236.5"),
        Decimal("0.6"),
        Decimal("2.5"),
    ]
    assert result.total.mag == Decimal("1239.6")


@pytest.mark.parametrize(
    ("style", "bad"),
    [
        ("comma_dot", "12,345.67.8"),
        ("dot_comma", "12.345,67,8"),
        ("space_comma", "12 345,67,8"),
        ("space_dot", "12 345.67.8"),
    ],
)
def test_bad_numbers_cannot_change_sheet_state(style, bad) -> None:
    start = "budget += $"
    text = f"budget = $200\n{start}{bad} + $999\n1. Fuel $50\n4 Car $200\nbudget + $1"
    res = evaluate_sheet(text, RATES, CONFIG, FormatOptions(number_style=style))
    assert [line.value.mag if line.value else None for line in res.lines] == [
        200,
        None,
        50,
        200,
        None,
    ]
    assert (len(start), len(start) + len(bad), "invalid_number") in res.lines[1].spans
    assert (0, 3, "comment") in res.lines[2].spans
    assert (0, 1, "comment") in res.lines[3].spans
    assert res.total.mag == 450


@pytest.mark.parametrize("style", ["comma_dot", "dot_comma", "space_comma", "space_dot"])
def test_commas_do_not_separate_function_arguments_or_list_items(style) -> None:
    assert calc("round(1, 9)\ntotal of 1, 9", number_style=style) == ["", ""]


def test_switch_to_dot_comma_with_mixed_sheet() -> None:
    text = """# Testing
ohx travelling
yes - we do
salary = $100k
tax = $5k
net = salary - tax
sadffsaf
sadffsaf
// $1000.1
$1000,1
1000,1
100 500

1000.123
1000.100

1) 100 500 500
1. 100 500 500
• 100 500 500
1, 1234 1000

10.1111
11 december 2027
01/02/2026
01.02.2026
01-02-2026
11 November

1 CAD in USD
1 USD in CAD
1.43 CAD in USD"""
    result = evaluate_sheet(text, RATES, CONFIG, FormatOptions(number_style="dot_comma"))
    assert len(result.lines) == len(text.splitlines())
    assert result.lines[9].text == "$1.000,10"


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
        ("1 / 3", "0.333"),
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
        ("50 USD in EUR at 1.05 USD/EUR", "€47.62"),
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
        ("5 hours 30 minutes to seconds", "19,800 s"),
        ("100 pounds in kg", "45.359 kg"),
        ("meters in 10 km", "10,000 m"),
        ("days in 3 weeks", "21 days"),
        ("seconds in a day", "86,400 s"),
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
        ("60 mph in km/h", "96.561 km/h"),
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
        ("3 hours / 3 days", "0.042"),
        ("€30/day in €/month", "€913.11/month"),
        ("$24 a day for a year", "$8,765.82"),
        # numbers
        ("2.5k", "2,500"),
        ("5M", "5,000,000"),
        ("1000000 + 2000", "1,002,000"),
        ("0b_1100_0001 to decimal", "193"),
        ("0xff + 1", "0x100"),
        ("255 as hex", "0xFF"),
        ("5 as binary", "0b101"),
        ("3 million + 10%", "3,300,000"),
        ("1.5e3", "1,500"),
        ("123456789 as sci", "1.235e8"),
        # functions
        ("sqrt 16", "4"),
        ("sqrt(2)", "1.414"),
        ("square root of 81", "9"),
        ("round(3.14159; 2)", "3.14"),
        ("floor(2.7)", "2"),
        ("ceil(2.1)", "3"),
        ("sin(90°)", "1"),
        ("cos(0)", "1"),
        ("log 1000", "3"),
        ("abs(-4)", "4"),
        ("pi * 2", "6.283"),
        # statistics
        ("total of 3; 4; 7; 9", "23"),
        ("average of 36; 42; 19; 81", "44.5"),
        ("count of 1; 2; 3; 4; 5", "5"),
        ("median of 10; 20; 30", "20"),
        ("standard deviation of 20; 30; 40", "10"),
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
        ("1988-02-12 + 32 years", "12 February 2020"),
        ("2005-05-01 + 3 years 2 months 3 weeks", "22 July 2008"),
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
        ("7:45am - 4:20pm", "8 hours 35 min"),
        ("9:00 + 90 minutes", "10:30"),
        # a night is one day
        ("2 nights", "2 nights"),
        ("2 nights in hours", "48 hours"),
        ("€95/night * 2 nights", "€190.00"),
        ("€95/night * 3 days", "€285.00"),
        ("2 nights × $95/night", "$190.00"),
        ("2 days × $95/day", "$190.00"),
        ("2 nights × $95 per night", "$190.00"),
        ("2 days × $95 per day", "$190.00"),
        ("3 × $95/day", "$285.00/day"),
        ("Meeting March 5, 10:00 - 11:30", "1 hour 30 min"),
        ("March 5 10:00 to 12:30", "2 hours 30 min"),
        ("10 June + 2 nights", "12 June"),
        # nights with a time end at 12:00 check-out; before 06:00 is still the night before
        ("2026-11-11 14:00 + 2 nights", "13 November, 12:00"),
        ("2026-11-11 23:30 + 1 night", "12 November, 12:00"),
        ("2026-11-12 01:00 + 1 night", "12 November, 12:00"),
        ("2026-11-11 14:00 + 1 night 2 hours", "12 November, 14:00"),
        ("2026-11-11 14:00 + 2 days", "13 November, 14:00"),
        # a date followed by a time
        ("2026-11-11 15:00", "11 November, 15:00"),
        ("2026-11-11 at 15:00 + 1 day", "12 November, 15:00"),
        ("Nov 11, 2026 3pm + 26 hours", "12 November, 17:00"),
        ("11 Nov 2026 15:00", "11 November, 15:00"),
        ("12 November, 17:00", "12 November, 17:00"),  # an answer pasted back
        ("Nov 11, 2026, 3pm", "11 November, 15:00"),
        ("Nov 2026 15:00", "1 November, 15:00"),
        ("12 June 2027 @ 9:00", "12 June 2027, 09:00"),
        ("tomorrow 9am", "11 November, 09:00"),
        ("2026-11-13 15:00 - 2026-11-12 15:00", "1 day"),
        ("2026-11-11 15:00 to 2026-11-12 17:30", "1 day 2 hours 30 min"),
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


def test_empty_assignment_names_the_subtotal() -> None:
    """As in Soulver: "food =" with nothing after it is a subtotal line named food."""
    text = "$10\n$15\nfood =\n$5\nfuel = // car\nfood + fuel"
    assert calc(text) == ["$10.00", "$15.00", "$25.00", "$5.00", "$5.00", "$30.00"]


def test_list_markers_are_skipped() -> None:
    text = (
        "1. Rent $1000\n2) Food $300\n3 housing = subtotal\n"
        "• Car $200\n5. Fuel $50\n6 transport =\n7. housing + transport"
    )
    assert calc(text) == [
        "$1,000.00",
        "$300.00",
        "$1,300.00",
        "$200.00",
        "$50.00",
        "$250.00",
        "$1,550.00",
    ]


def test_a_leading_number_left_out_of_the_maths_looks_like_a_list_number() -> None:
    def look(line: str) -> str:
        res = evaluate_sheet(line, RATES, CONFIG)
        return next(cls for a, _, cls in res.lines[0].spans if a == 0)

    assert look("1. Rent $1000") == "comment"
    assert look("4 Car $200") == "comment"
    assert look("3 apples") == "number"
    assert look("4 people × $20") == "number"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("$5 * $5", "$25.00"),
        ("€5 * $5", "$25.00"),
        ("$5 * €5", "€25.00"),
        ("$5^2", "$25.00"),
        ("$30/hour * $2", "$60.00"),
        ("(1/$5)^2", "0.04/USD"),
    ],
)
def test_money_times_money_keeps_the_right_hand_currency(line: str, expected: str) -> None:
    """As in Soulver: no "25 USD²"."""
    assert one(line) == expected


def test_an_operator_at_the_start_continues_the_line_just_above() -> None:
    """As typing does in Soulver, "-" included, so a list of costs is a running balance."""
    assert calc("$1000\n-200\n- 50\n+ 25\n× 2\n/ 5\n^ 2") == [
        "$1,000.00",
        "$800.00",
        "$750.00",
        "$775.00",
        "$1,550.00",
        "$310.00",
        "$96,100.00",
    ]
    assert calc("$1000\n- 200\n- 50\nsubtotal") == ["$1,000.00", "$800.00", "$750.00", "$2,550.00"]


def test_nothing_continues_across_a_gap_or_after_text_in_front() -> None:
    text = (
        "$1000\n\n- 200\n$1000\n# Next\n- 200\n$1000\n// note\n+ 5\n"
        "$1000\nRefund: -200\nx = -5\n1. -5"
    )
    assert [t for t in calc(text) if t] == [
        "$1,000.00",
        "-200",
        "$1,000.00",
        "-200",
        "$1,000.00",
        "5",
        "$1,000.00",
        "-200",
        "-5",
        "-5",
    ]


def test_a_note_starting_with_an_operator_does_not_repeat_the_answer_above() -> None:
    text = "$10 lunch\n- milk\n* remember the receipt\n-> next\ntotal"
    assert calc(text) == ["$10.00", "", "", "", "$10.00"]


def test_big_answers_are_short_in_the_answers_column_only() -> None:
    res = evaluate_sheet("$386.8M\n999999\n999999999\n100000000 km\n2^64", RATES, CONFIG)
    assert [line.short for line in res.lines] == ["$386.8M", "", "1B", "100M km", "1.845e19"]
    assert res.lines[0].text == "$386,800,000.00"  # hover and copy give it in full
    uk = evaluate_sheet("₴5000000", RATES, CONFIG, FormatOptions(lang="uk"))
    assert uk.lines[0].short == "5 млн ₴"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("5 ft 3 in in cm", "160.02 cm"),
        ("3 in to cm", "7.62 cm"),
        ("10 GB at 100 Mbps in minutes", "13.333 min"),
        ("0B in bytes", "0 B"),
        ("1 year in days", "365.242 days"),
        ("1 decade in years", "10 years"),
        ("2 centuries in decades", "20 decades"),
    ],
)
def test_inches_and_years(line: str, expected: str) -> None:
    assert one(line) == expected


def test_soulver_references_in_exported_text() -> None:
    text = "$1000\n[$1 000,00](line1) − 200\n[$800,00](line2) × fuel $50"
    assert calc(text) == ["$1,000.00", "$800.00", "$40,000.00"]


def test_empty_add_assignment_stays_empty() -> None:
    assert calc("x = 5\nx +=\nx") == ["5", "", ""]


def test_average_of_lines() -> None:
    assert calc("10\n20\n30\naverage") == ["10", "20", "30", "20"]


def test_total_mixed_currencies_uses_last() -> None:
    assert calc("$90\n€90\ntotal") == ["$90.00", "€90.00", "€171.00"]


def test_total_with_missing_rate_rejects_partial_answer() -> None:
    source = "100 CHF\n50 USD\ntotal"
    res = evaluate_sheet(source, RATES, CONFIG)
    assert [line.text for line in res.lines] == ["100.00 CHF", "$50.00", ""]
    assert res.lines[-1].error == "no exchange rate for CHF"
    assert res.total is None


def test_tags() -> None:
    text = "$20 lunch #food\n$15 taxi #travel\n$30 dinner #food\ntotal of #food\naverage of #food"
    assert calc(text)[-2:] == ["$50.00", "$25.00"]


def test_sheet_total() -> None:
    res = evaluate_sheet("$10\n$20\ntotal\n$5", RATES, CONFIG)
    assert res.total is not None
    assert res.total.mag == Decimal(35)


def sheet_total(text: str) -> str:
    total = evaluate_sheet(text, RATES, CONFIG).total
    return format_value(total, FormatOptions()) if total is not None else ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # - 5k carries on from the total, so it takes the place of the lines it adds up
        ("rent = 12k UAH\nfood = 8k UAH\ntotal\n- 2k", "₴18,000.00"),
        ("$100\n* 2", "$200.00"),
        ("$100\n* 2\n+ $1", "$201.00"),
        # an average isn't in the sheet total, so neither is what carries on from it
        ("$10\n$20\naverage\n* 12", "$30.00"),
        # rent += $100 takes the place of the line that last set rent
        ("rent = $900\nrent += $100", "$1,000.00"),
        ("rent = $900\n$50\nrent -= $100\nrent += $10", "$860.00"),
        ("$900\n$100\nhousing =\nhousing += $50", "$1,050.00"),
        # the tagged lines are in already, so a total of a tag isn't
        ("$20 lunch #food\n$15 taxi\n$30 dinner #food\ntotal of #food", "$65.00"),
        ("$20 lunch #food\n$15 taxi\naverage of #food", "$35.00"),
        ("$20 lunch #food\n$15 taxi\ntotal of #food\n* 2", "$55.00"),
        # a list of its own numbers is a new answer
        ("$20\ntotal of $3; $4", "$27.00"),
        # a line takes the place of the answers it uses
        ("rent = 12k UAH\nfood = 8k UAH\nhousing = rent + food", "₴20,000.00"),
        ("rent = 12k UAH\ntax = rent * 20%\nnet = rent - tax", "₴9,600.00"),
        # a new amount worked out from an answer counts as well as that answer
        ("rent = $1,000\ndeposit = rent × 2", "$3,000.00"),
        ("rent = 12k UAH\ntax = rent * 20%", "₴14,400.00"),
        ("$10\nline 1 * 2", "$30.00"),
        ("rent = $1,000\nfood = $500\nrent × 2 + food", "$3,500.00"),
        ("rent = $1,000\nfood = $500\ntotal of rent; food", "$1,500.00"),
        ("rent = $1,000\nrent in EUR", "€900.00"),
        ("$10\n$20\nx = average\nx * 2", "$30.00"),
        # two lines can use one answer, and both count
        ("x = $5\na = x + $1\nb = x + $2", "$13.00"),
        ("$20 lunch #food\n$15 taxi\ntotal of #food\ntotal", "$35.00"),
    ],
)
def test_the_sheet_total_counts_each_answer_once(text: str, expected: str) -> None:
    assert sheet_total(text) == expected


def test_a_total_below_a_tag_total_counts_each_line_once() -> None:
    res = evaluate_sheet("$20 lunch #food\n$15 taxi\ntotal of #food\ntotal", RATES, CONFIG)
    assert [line.text for line in res.lines][-2:] == ["$20.00", "$35.00"]
    assert not res.lines[2].is_total  # not bold, and the block goes on past it


def test_money_wins_the_sheet_total() -> None:
    speeds = "100 mbps to mbs\n300 mbps to mbs\n85 mbps to mbs\n82 mbps to mbs\n"
    assert sheet_total(speeds + "rent = 12k UAH\nfood = 8k UAH\ntotal") == "₴20,000.00"
    assert sheet_total(speeds + "2 km") == "70.875 MB/s"  # no money: the kind used most


def test_number_styles() -> None:
    assert one("1.234,5 + 1", number_style="dot_comma") == "1.235,5"
    assert one("1 234,5 + 1", number_style="space_comma") == "1 235,5"
    assert one("1234.5", number_style="space_comma") == ""
    assert one("total of 1,5 and 2", number_style="dot_comma") == "3,5"


def test_decimal_settings() -> None:
    assert one("1/3", max_decimals=2) == "0.33"
    assert one("$10/3", money_decimals=3) == "$3.333"


def test_timeline() -> None:
    sheet = """@from 2026-11-11 at 15:00
London: 1 night
Driving: 2 hours
Hotel: $100 * 2
2 hours * 3
stay = 2 nights
# Day 2
Time zone shift: -1 hour
@to"""
    assert calc(sheet) == [
        "11 November, 15:00",
        "12 November, 12:00",
        "12 November, 14:00",
        "$200.00",
        "6 hours",
        "2 nights",
        "",
        "12 November, 13:00",
        "12 November, 13:00",
    ]


def test_timeline_hotel_nights() -> None:
    sheet = "@from 11 Nov 2026 at 14:00\nHotel: 2 nights\n@to 2026-11-13 12:00"
    assert one(sheet) == "0 hours left"
    assert one(sheet.replace("nights", "days")) == "2 hours over"
    # @from without a time: 02:00 after a walk isn't a late arrival
    walk = "@from 2026-11-11\nWalk: 2 hours\nHotel: 1 night"
    assert one(walk) == "12 November, 12:00"
    # @to without a time compares whole days
    nye = "@from 2026-12-30 at 15:00\nNYE: 2 nights\n@to 2027-01-01"
    assert one(nye) == "0 days left"
    assert one(nye.replace("2 nights", "3 nights")) == "1 day over"
    assert one(nye.replace("2 nights", "1 night")) == "1 day left"
    # a label ending in a digit is still a label, so it moves the timeline
    two = "@from 2028-02-28 at 15:00\nHotel: 1 night\nHotel 2: 1 night\n@to 2028-03-01 12:00"
    assert calc(two)[2:] == ["1 March 2028, 12:00", "0 hours left"]


def test_timeline_boundary() -> None:
    start = "@from 2026-11-11 15:00\nLondon: 1 day\n"
    # days and hours keep it short; hovering over @to shows it exactly
    assert one(start + "@to 2026-11-14 18:40") == "2 days 3 hours left"
    assert one(start + "@to 2026-11-13 15:40") == "1 day left"
    assert one(start + "@to 2026-11-13 14:20") == "23 hours 20 min left"
    assert one(start + "@to 2026-11-12 15:20") == "20 min left"
    assert one(start + "@to 2026-11-12 12:00") == "3 hours over"
    assert one(start + "@to 2026-11-13") == "1 day left"  # no time: whole days
    # how long the timeline lasts shows when hovering over @to
    res = evaluate_sheet(start + "  @to 2026-11-13 15:00", RATES, CONFIG, FormatOptions())
    assert res.lines[-1].hints == [(2, 5, "1 day left\nlasts 1 day")]
    res = evaluate_sheet(start + "@to", RATES, CONFIG, FormatOptions())
    assert res.lines[-1].hints == [(0, 3, "lasts 1 day")]
    # an answer pasted back into a sheet gives the same answer
    assert one("1 day left") == "1 day"
    assert one("12 November, 15:00") == "12 November, 15:00"
    res = evaluate_sheet(
        start + "@to 2026-11-12 12:00\nprev in hours", RATES, CONFIG, FormatOptions()
    )
    assert res.lines[-1].text == "-3 hours"


def test_timeline_edges() -> None:
    # a date alone starts at midnight; months and leap days come from date maths
    assert calc("@from 2028-02-28\nLeap: 1 day 2 hours\nNext: 1 month") == [
        "28 February 2028",
        "29 February 2028, 02:00",
        "29 March 2028, 02:00",
    ]
    # a bad @from shows the error; lines below just show durations
    res = evaluate_sheet("@from soon\nRome: 2 days\n@to", RATES, CONFIG, FormatOptions())
    assert [(r.text, r.error) for r in res.lines] == [
        ("", "@from needs a date"),
        ("2 days", ""),
        ("", ""),
    ]
    # a block ends at @to, at ---, and at the next @from
    assert calc("@from 2026-11-11\nA: 1 day\n@to\nB: 1 day") == [
        "11 November",
        "12 November",
        "12 November",
        "1 day",
    ]
    assert one("@from 2026-11-11\n---\nB: 1 day") == "1 day"
    assert one("@from 2026-11-11\nA: 1 day\n@from 2026-12-01\nB: 1 day\n@to") == ("2 December")
    res = evaluate_sheet("@to", RATES, CONFIG, FormatOptions())
    assert res.lines[0].error == "no @from above"
    # outside a block nothing moves, and @ still means "at"
    assert one("London: 2 nights") == "2 nights"
    assert one("$5 @ 3") == "3"


def test_timeline_answers_stay_out_of_totals() -> None:
    res = evaluate_sheet(
        "@from 2026-11-11\nHotel: $100\nTaxi: $20\nStay: 2 nights\n@to 2026-11-20",
        RATES,
        CONFIG,
        FormatOptions(),
    )
    assert res.lines[3].text == "13 November"
    assert res.total is not None and res.total.mag == 120


@pytest.mark.parametrize("style", ["comma_dot", "dot_comma", "space_comma", "space_dot"])
def test_dates_use_the_same_syntax_in_every_number_format(style) -> None:
    lines = [
        "2026-01-18",
        "18 January 2026",
        "January 18, 2026",
        "18 Jan 2026",
        "January 18 2026",
        "18 January",
        "January 18",
        "18 Jan. 2026",
        "Jan. 18, 2026",
        "18.01.2026",
        "11.12.26",
        "18/01/2026",
    ]
    result = evaluate_sheet("\n".join(lines), RATES, CONFIG, FormatOptions(number_style=style))
    assert [line.value.dt for line in result.lines[:-3]] == [datetime(2026, 1, 18)] * 9
    assert [line.value for line in result.lines[-3:]] == [None, None, None]


@pytest.mark.parametrize("style", ["comma_dot", "dot_comma", "space_comma", "space_dot"])
def test_day_first_dates_and_times(style: str) -> None:
    text = "18-11-2026\n18-11-2026 15:00\n2026-11-18 15:00\n31-11-2026\n18 - 11 - 2026"
    date, date_time, iso, invalid, subtraction = evaluate_sheet(
        text, RATES, CONFIG, FormatOptions(number_style=style)
    ).lines
    assert date.value is None
    assert date.spans == [(0, 10, "invalid_date")]
    assert date_time.value is None
    assert iso.value == DateVal(datetime(2026, 11, 18, 15), has_time=True)
    assert invalid.value is None
    assert invalid.spans == [(0, 10, "invalid_date")]
    assert subtraction.value.mag == -2019


def test_invalid_assigned_date_is_not_a_number() -> None:
    line = evaluate_sheet("salary = 18-19-2026", RATES, CONFIG).lines[0]
    assert line.value is None
    assert (9, 19, "invalid_date") in line.spans


@pytest.mark.parametrize("bad", ["18.11.2026", "18/11/2026", "18-11-2026"])
def test_unsupported_numeric_date_warns_but_keeps_valid_iso_date(bad: str) -> None:
    text = f"Going to London on {bad} and back on 2026-11-18"
    line = evaluate_sheet(text, RATES, CONFIG).lines[0]
    assert line.value == DateVal(datetime(2026, 11, 18))
    assert (19, 29, "invalid_date") in line.spans


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("Trip: 18/11/2026 to 2026-11-20", "18/11/2026"),
        ("2026-11-18 through 20.11.2026", "20.11.2026"),
        ("2026-11-18 10:30 - 20/11/2026", "20/11/2026"),
        ("days between 18/11/2026 and 2026-11-20", "18/11/2026"),
        ("з 18.11.2026 до 2026-11-20", "18.11.2026"),
        ("днів між 18.11.2026 і 2026-11-20", "18.11.2026"),
    ],
)
def test_date_range_rejects_an_unsupported_endpoint(text: str, bad: str) -> None:
    line = evaluate_sheet(text, RATES, CONFIG).lines[0]
    assert line.value is None
    assert line.error == "use YYYY-MM-DD for numeric dates"
    start = text.index(bad)
    assert (start, start + len(bad), "invalid_date") in line.spans


def test_prose_with_two_dates_does_not_pick_one_without_a_range() -> None:
    line = evaluate_sheet("Going to London on 2026-11-18 and back 2026-11-19", RATES, CONFIG).lines[
        0
    ]
    assert line.value is None
    assert line.error == "Use ‘to’ between the dates to calculate a date range."


def test_date_like_division_with_spaces_remains_arithmetic() -> None:
    line = evaluate_sheet("18 / 11 / 2026", RATES, CONFIG).lines[0]
    assert line.value.mag == Decimal(18) / Decimal(11) / Decimal(2026)


def test_short_day_and_month_are_also_marked_as_unsupported_dates() -> None:
    line = evaluate_sheet("1/2/2026", RATES, CONFIG).lines[0]
    assert line.value is None
    assert line.spans == [(0, 8, "invalid_date")]


def test_missing_rate_gives_no_answer() -> None:
    assert one("10 CHF in USD") == ""


def test_division_by_zero_gives_no_answer() -> None:
    assert one("5 / 0") == ""


@pytest.mark.parametrize("text", ["5 km mod 2 m", "5 km % 2 m", "remainder of 5 km divided by 2 m"])
def test_remainder_converts_compatible_units(text: str) -> None:
    assert one(text) == "0 km"


def test_remainder_rejects_incompatible_units() -> None:
    line = evaluate_sheet("5 km mod 2 seconds", RATES, CONFIG).lines[0]
    assert line.value is None
    assert line.error == "incompatible units"


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
    assert one("total of $5; 3") == "$8.00"


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
    assert [line.text for line in res.lines] == ["1", "", "", ""]
    assert res.lines[1].error == "no such line"
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
        ("1 MiB/s in Mbps", "8.389 Mbps"),
        ("100 Mbps + 10 MB/s", "180 Mbps"),
        ("10 GB / 100 Mbps", "800 s"),
        ("10 GB at 100 Mbps in minutes", "13.333 min"),
        ("100 Mbps × 1 hour in GB", "45 GB"),
        ("10 km at 5 kph", "2 hours"),
        # lowercase, as people type it: mb is megabytes, mbps is megabits
        ("1 mbps in mb/s", "0.125 MB/s"),
        ("1 mbps in mbs", "0.125 MB/s"),
        ("1 MBs in Mbps", "8 Mbps"),
        ("500 mb in gb", "0.5 GB"),
        ("1 mbit in mb", "0.125 MB"),
        ("1 Mb in MB", "0.125 MB"),  # exact case stays SI
        ("10 gb at 100 mbps in minutes", "13.333 min"),
    ],
)
def test_data_rates(line: str, answer: str) -> None:
    assert one(line) == answer


def test_data_rates_in_ukrainian() -> None:
    assert one("100 Мбіт/с у МБ/с", lang="uk") == "12.5 МБ/с"
    assert one("10 ГБ по 100 Мбіт/с у хвилинах", lang="uk") == "13.333 хв"
    assert one("1 мбіт/с у мб/с", lang="uk") == "0.125 МБ/с"


def test_variables_carry_their_values_for_hover() -> None:
    lines = evaluate_sheet("rent = $1000\nrent = rent + 50\nrent * 2 // rent", RATES, CONFIG).lines
    assert lines[0].hints == [(0, 4, "$1,000.00")]
    # the value the line used, then the new one on the name being assigned
    assert sorted(lines[1].hints) == [(0, 4, "$1,050.00"), (7, 11, "$1,000.00")]
    assert lines[2].hints == [(0, 4, "$1,050.00")]  # not the word in the comment
