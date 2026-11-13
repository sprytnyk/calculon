"""Timelines: @from starts one, labelled durations move it, @to ends it.

@from 11.11.2026 15:00
London: 1 night          -> 12 November, 15:00
Driving: 2 hours         -> 12 November, 17:00
@to 13.11.2026 15:00     -> 22 hours left · 1 day 2 hours
"""

import re
from dataclasses import dataclass

from .currency import RateTable
from .values import CalcError, DateVal, Q, Value, add, date_diff

DIRECTIVE_RE = re.compile(r"^\s*@(?P<word>from|to|від|до)(?=\s|$)", re.IGNORECASE)
STARTS = {"from", "від"}

WORDS = {
    "en": {"left": "{} left", "over": "{} over"},
    "uk": {"left": "залишилось: {}", "over": "перевищено: {}"},
}


@dataclass
class Timeline:
    """One @from block. start is None when @from had no usable date."""

    start: DateVal | None
    cursor: DateVal | None

    def advance(self, value: Value, rates: RateTable) -> Value:
        """Move by a duration and return the date reached; other values pass through."""
        if self.cursor is None or not is_duration(value):
            return value
        moved = add(self.cursor, value, rates)
        assert isinstance(moved, DateVal)
        self.cursor = moved
        return moved

    def elapsed(self) -> Q | None:
        if self.start is None or self.cursor is None:
            return None
        return date_diff(self.start, self.cursor)


def is_duration(value: Value) -> bool:
    if not isinstance(value, Q) or value.pct:
        return False
    try:
        value.time_parts()
    except CalcError:
        return False
    return True


def is_start(word: str) -> bool:
    return word.lower() in STARTS


def time_left(cursor: DateVal, boundary: DateVal) -> tuple[Q, Q, bool]:
    """(signed value, amount to show, is over) for boundary minus cursor."""
    left = date_diff(cursor, boundary)
    if left.mag < 0:
        return left, date_diff(boundary, cursor), True
    return left, left, False


def left_text(amount: str, over: bool, lang: str) -> str:
    words = WORDS.get(lang, WORDS["en"])
    return words["over" if over else "left"].format(amount)
