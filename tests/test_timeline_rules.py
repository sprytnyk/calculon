"""Rules the timeline answers rely on, checked on many random dates."""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from calculon.engine import RateTable
from calculon.engine.timeline import short_time, time_left
from calculon.engine.values import DateVal, Q, add

ZONES = [None, ZoneInfo("Europe/Kyiv"), ZoneInfo("Asia/Tokyo"), ZoneInfo("America/New_York")]
MINUTES = {"day": 1440, "hour": 60, "minute": 1}


def _wall(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def test_time_left_matches_the_real_gap() -> None:
    """The short answer is the gap cut to whole hours (a day or more) or whole minutes."""
    rng = random.Random(1)
    for _ in range(3000):
        tz = rng.choice(ZONES)
        a = datetime(2026, 1, 1, tzinfo=tz) + timedelta(minutes=rng.randrange(3 * 365 * 1440))
        gap = rng.choice([rng.randrange(-3000, 3000), rng.randrange(-400 * 1440, 400 * 1440)])
        b = a + timedelta(minutes=gap)
        value, shown, over = time_left(DateVal(a, True, True), DateVal(b, True, True))
        q = short_time(shown)
        got = sum(int(v) * MINUTES[u] for u, v in q.parts or ((q.units[0][0], q.mag),))
        real = abs(int((_wall(b) - _wall(a)).total_seconds())) // 60
        assert got == (real if real < 1440 else real - real % 60), (a, b)
        assert over == (b < a) and (value.mag < 0) == (b < a), (a, b)


def test_nights_end_at_check_out() -> None:
    rng = random.Random(2)
    rates = RateTable()
    for _ in range(3000):
        tz = rng.choice(ZONES)
        base = datetime(2026, 10, 20 if rng.random() < 0.5 else 1, tzinfo=tz)  # DST on 25 Oct
        a = base + timedelta(minutes=rng.randrange(20 * 1440))
        n = rng.randint(1, 10)

        def stay(arrival: datetime, nights: int) -> datetime:
            moved = add(DateVal(arrival, True, True), Q(Decimal(nights), (("night", 1),)), rates)
            assert isinstance(moved, DateVal)
            return moved.dt

        end = stay(a, n)
        hours = (_wall(end) - _wall(a)).total_seconds() / 3600
        assert (end.hour, end.minute) == (12, 0), a
        assert _wall(end) > _wall(a), a
        assert 6 <= hours - 24 * (n - 1) <= 30, a
        assert _wall(stay(a, n + 1)) - _wall(end) == timedelta(days=1), a
        assert _wall(stay(a + timedelta(minutes=1), n)) >= _wall(end), a
        assert end.tzinfo == a.tzinfo
