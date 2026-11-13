"""Timelines: @from starts one, labelled durations move it, @to ends it.

@from 11.11.2026 15:00
London: 1 night          -> 12 November, 15:00
Driving: 2 hours         -> 12 November, 17:00
@to 14.11.2026 15:00     -> 1 day 22 hours left

Hovering over @to shows the exact time left and how long it lasts.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from . import units as U
from .currency import RateTable
from .values import CalcError, DateVal, Q, Value, add, add_nights, date_diff

DIRECTIVE_RE = re.compile(r"^\s*@(?P<word>from|to|від|до)(?=\s|$)", re.IGNORECASE)
STARTS = {"from", "від"}

WORDS = {
    "en": {"left": "{} left", "over": "{} over", "lasts": "lasts {}"},
    "uk": {"left": "залишилось: {}", "over": "перевищено: {}", "lasts": "триває: {}"},
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
        moved = None
        if self.start is not None and not self.start.has_time:
            # @from had no time, so 02:00 after "Walk: 2 hours" isn't a late arrival
            moved = add_nights(self.cursor, value, night_before=False)  # type: ignore[arg-type]
        if moved is None:
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
    """(signed value, amount to show, is over) for boundary minus cursor.

    A boundary with no time compares whole days: ending at 12:00 on 1 Jan is on time
    for @to 1 Jan.
    """
    if not boundary.has_time:
        days = (boundary.dt.date() - cursor.dt.date()).days
        return Q(Decimal(days), (("day", 1),)), Q(Decimal(abs(days)), (("day", 1),)), days < 0
    left = date_diff(cursor, boundary)
    if left.mag < 0:
        return left, date_diff(boundary, cursor), True
    return left, left, False


def short_time(q: Q) -> Q:
    """Short enough for the answers: 3 days 18 hours, or 18 hours 40 minutes under a day."""
    seconds = round(abs(q.mag) * U.factor(q.units[0][0], "second"))  # 83999.99 is 84000
    days, rest = divmod(seconds, 86400)
    hours, minutes = divmod(rest // 60, 60)
    if days:
        big, small = ("day", days), ("hour", hours)
    else:
        big, small = ("hour", hours), ("minute", minutes)
    if not small[1]:
        return Q(Decimal(big[1]), ((big[0], 1),))
    if not big[1]:
        return Q(Decimal(small[1]), ((small[0], 1),))
    parts = ((big[0], Decimal(big[1])), (small[0], Decimal(small[1])))
    per = 24 if days else 60
    return Q(Decimal(big[1]) + Decimal(small[1]) / per, ((big[0], 1),), parts=parts)


def left_text(amount: str, over: bool, lang: str) -> str:
    words = WORDS.get(lang, WORDS["en"])
    return words["over" if over else "left"].format(amount)


def lasts_text(amount: str, lang: str) -> str:
    return WORDS.get(lang, WORDS["en"])["lasts"].format(amount)
