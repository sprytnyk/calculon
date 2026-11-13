"""Rules the timeline answers rely on, checked on many random dates."""

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from calculon.engine.timeline import short_time, time_left
from calculon.engine.values import DateVal

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
