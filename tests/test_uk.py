"""Ukrainian sheets: 1 234,56 numbers, metric units in Cyrillic, Ukrainian results."""

import time
from dataclasses import replace

import pytest

from calculon.engine import FormatOptions, evaluate_sheet
from tests.test_engine import CONFIG, RATES

NB = " "  # thousands separator in the 1 234,56 style
UK = FormatOptions(number_style="space_comma", lang="uk")
UK_CONFIG = replace(CONFIG, number_style="space_comma")


def uk(text: str) -> str:
    return evaluate_sheet(text, RATES, UK_CONFIG, UK).lines[-1].text


@pytest.fixture
def kyiv_time(monkeypatch: pytest.MonkeyPatch):
    """Answers in other cities depend on the machine's own time zone; pin it."""
    monkeypatch.setenv("TZ", "Europe/Kyiv")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_time_in_another_city(kyiv_time) -> None:
    assert uk("15:00 у Лондоні") == "13:00 Лондон"  # Kyiv is 2 hours ahead in November


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # numbers
        ("1 234,56 + 10", f"1{NB}244,56"),
        ("2,5 + 2,5", "5"),
        ("10,5% від 200", "21"),
        ("round(2,345; 2)", "2,35"),
        ("1,5e3", f"1{NB}500"),
        ("5 тис. + 500", f"5{NB}500"),
        ("5к - 55", f"4{NB}945"),
        ("2,5К + 1", f"2{NB}501"),
        ("5к грн", f"5{NB}000,00 ₴"),
        ("5 км", "5 км"),
        ("2,5 млн", f"2{NB}500{NB}000"),
        ("1 млрд / 1 млн", f"1{NB}000"),
        # money: symbol after the number, Ukrainian names
        ("₴1 234,5 + ₴10", f"1{NB}244,50 ₴"),
        ("1 000 грн у USD", "24,39 $"),
        ("41 гривня у доларах", "1,00 $"),
        ("100 € у грн", f"4{NB}555,56 ₴"),
        ("5 тис. грн", f"5{NB}000,00 ₴"),
        ("$10 у євро", "9,00 €"),
        # metric units
        ("5 кг у г", f"5{NB}000 г"),
        ("5 кг + 300 г", "5,3 кг"),
        ("1,5 л + 500 мл", "2 л"),
        ("2,5 км у м", f"2{NB}500 м"),
        ("20 °С у °F", "68 °F"),  # Cyrillic С
        ("1 т у кг", f"1{NB}000 кг"),
        ("2 ГБ у МБ", f"2{NB}000 МБ"),
        ("20 м² × 3", "60 м²"),
        ("60 км/год × 2 год", "120 км"),
        ("100 км/год", "100 км/год"),
        ("10 км у милі", "6,213712 милі"),
        ("5 миль у кілометрах", "8,04672 км"),
        # Ukrainian plurals
        ("1 година", "1 година"),
        ("3 години", "3 години"),
        ("5 годин", "5 годин"),
        ("11 днів", "11 днів"),
        ("21 день", "21 день"),
        ("90 хв у годинах", "1,5 години"),
        ("1 год 30 хв", "1 година 30 хвилин"),
        ("120 км / 60 км/год", "2 години"),
        # dates
        ("10 листопада + 5 днів", "15 листопада"),
        ("2 ночі", "2 ночі"),
        ("10 листопада + 2 ночі", "12 листопада"),
        ("сьогодні + 3 тижні", "1 грудня"),
        ("3 дні тому", "7 листопада"),
        ("днів до 25 грудня", "45 днів"),
        ("днів між 3 березня і 30 травня", "88 днів"),
        ("днів від 10 листопада", "0 днів"),
        ("з 3 березня до 30 травня", "2 місяці 3 тижні 6 днів"),
        ("3 тижні після 14 березня 2027", "4 квітня 2027"),
        # words for operations
        ("30 плюс 20 мінус 5", "45"),
        ("1 000 поділити на 8", "125"),
        ("3 помножити на 4", "12"),
        ("остача від ділення 21 на 5", "1"),
        ("21 за модулем 5", "1"),
        ("2 у степені 10", f"1{NB}024"),
        ("5 у квадраті", "25"),
        ("квадратний корінь з 81", "9"),
        ("пі × 2", "6,283185"),
        ("255 у шістнадцятковій", "0xFF"),
        # percentages, the same forms as in English
        ("10% знижки від 200", "180"),
        ("10% націнки до 200", "220"),
        ("200 зі знижкою 10%", "180"),
        ("200 з націнкою 10%", "220"),
        ("20 це 10% від чого", "200"),
        ("180 це 10% знижки від чого", "200"),
        ("220 це 10% націнки до чого", "200"),
        ("з 50 до 75 це скільки %", "50%"),
        ("20 це скільки % від 200", "10%"),
        ("20 як % від 200", "10%"),
        ("0,35 як %", "35%"),
        ("2/10 як дріб", "1/5"),
        ("20/5 як множник", "4x"),
        # rates
        ("₴500 за годину × 40 годин", f"20{NB}000,00 ₴"),
        ("₴99 на тиждень як / місяць", "430,47 ₴/місяць"),
        ("30 годин по ₴300 за годину", f"9{NB}000,00 ₴"),
        ("₴5 000 по ₴250 за годину", "20 годин"),
        ("30 годин при ₴300 за годину", f"9{NB}000,00 ₴"),
        ("200 км при 80 км/год", "2,5 години"),
        ("1,5 ТБ при 25 МБ/с у годинах", "16,666667 години"),
        ("₴240 на день протягом року", f"87{NB}660,00 ₴"),
        ("50 € у USD за курсом 1,05 USD/EUR", "52,50 $"),
        ("5 км без перерахунку у милі", "5 миль"),
        ("₴190 на сніданок + ₴220 на таксі", "410,00 ₴"),
    ],
)
def test_ukrainian(line: str, expected: str) -> None:
    assert uk(line) == expected


def test_ukrainian_timeline() -> None:
    sheet = "@від 11.11.2026 15:00\nЛондон: 2 ночі\n@до 14.11.2026 15:00\n@до 12.11.2026"
    res = evaluate_sheet(sheet, RATES, UK_CONFIG, UK)
    assert [(line.text, line.error) for line in res.lines] == [
        ("11 листопада, 15:00", ""),
        ("13 листопада, 12:00", ""),
        ("залишилось: 1 день 3 години", ""),
        ("", "no @від above"),
    ]


def test_ukrainian_totals_and_variables() -> None:
    sheet = "оренда = 12 000 грн\nоренда / 3\n₴200 обід #їжа\n₴350 вечеря #їжа\nразом від #їжа"
    res = evaluate_sheet(sheet, RATES, UK_CONFIG, UK)
    assert [line.text for line in res.lines] == [
        f"12{NB}000,00 ₴",
        f"4{NB}000,00 ₴",
        "200,00 ₴",
        "350,00 ₴",
        "550,00 ₴",
    ]


def test_english_results_stay_english() -> None:
    res = evaluate_sheet("5 кг у г\n90 хв у годинах\n₴10", RATES, CONFIG)
    assert [line.text for line in res.lines] == ["5,000 g", "1.5 hours", "₴10.00"]


def test_ukrainian_line_references() -> None:
    res = evaluate_sheet("100\nрядок1 * 2\nпопередній + 1", RATES, UK_CONFIG, UK)
    assert [line.text for line in res.lines] == ["100", "200", "201"]
