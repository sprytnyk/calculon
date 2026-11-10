"""Ukrainian words in sheets.

Each Ukrainian word or phrase turns into the item its English counterpart gives, so both
languages go through the same parser: "180 це 10% знижки від чого" reads as
"180 is 10% off what". Function names (sqrt, round, sin...) stay as they are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import units as U

if TYPE_CHECKING:
    from .interpreter import Item

# word -> English keyword
WORDS = {
    # conversion and percentages
    "у": "in", "в": "in", "як": "as", "це": "is", "є": "is",
    "чого": "what", "що": "what", "скільки": "what",
    "відсоток": "percent", "відсотки": "percent", "відсотків": "percent",
    "дріб": "fraction", "дробом": "fraction", "множник": "multiplier",
    "множником": "multiplier",
    # arithmetic
    "плюс": "plus", "мінус": "minus", "поділити": "divided", "поділене": "divided",
    "ділене": "divided", "помножити": "multiplied", "помножене": "multiplied",
    "остача": "remainder",
    # number formats
    "шістнадцяткове": "hex", "шістнадцятковий": "hex", "шістнадцятковому": "hex",
    "шістнадцятковій": "hex", "двійкове": "binary", "двійковий": "binary",
    "двійковому": "binary", "двійковій": "binary", "вісімкове": "octal",
    "вісімковий": "octal", "вісімковому": "octal", "вісімковій": "octal",
    "десяткове": "decimal", "десятковий": "decimal", "десятковому": "decimal",
    "десятковій": "decimal", "наукове": "sci", "науковий": "sci", "науковому": "sci",
    "науковій": "sci",
    # totals
    "разом": "total", "сума": "sum", "підсумок": "subtotal", "середнє": "average",
    "медіана": "median", "кількість": "count",
    # dates
    "сьогодні": "today", "завтра": "tomorrow", "вчора": "yesterday", "зараз": "now",
    "час": "time", "тому": "ago", "після": "after", "перед": "before", "між": "between",
    "протягом": "for",
    "наступний": "next", "наступна": "next", "наступне": "next", "наступного": "next",
    "наступної": "next", "наступну": "next",
    "минулий": "last", "минула": "last", "минуле": "last", "минулого": "last",
    "минулої": "last", "минулу": "last",
    "цей": "this", "ця": "this", "цього": "this", "цієї": "this", "цю": "this",
    # lists and earlier lines
    "і": "and", "й": "and", "та": "and",
    "рядок": "line", "рядка": "line", "попередній": "prev", "попереднє": "prev",
    "попередня": "prev", "попереднього": "prev", "відповідь": "answer",
}  # fmt: skip
FUNCTIONS = {"корінь": "sqrt", "округлити": "round", "округли": "round"}
CONSTANTS = {"пі": "pi"}

# phrases: words -> what they become, as (kind, key) pairs
PHRASES: dict[tuple[str, ...], list[tuple[str, str]]] = {
    ("остача", "від", "ділення"): [("kw", "remainder"), ("kw", "of")],
    ("знижки", "від"): [("kw", "off")],
    ("знижка", "від"): [("kw", "off")],
    ("знижку", "від"): [("kw", "off")],
    ("націнки", "до"): [("kw", "on")],
    ("націнка", "до"): [("kw", "on")],
    ("націнку", "до"): [("kw", "on")],
    ("зі", "знижкою"): [("kw", "minus")],
    ("із", "знижкою"): [("kw", "minus")],
    ("з", "націнкою"): [("kw", "plus")],
    ("за", "курсом"): [("kw", "at")],
    ("за", "модулем"): [("kw", "mod")],
    ("у", "степені"): [("op", "^")],
    ("в", "степені"): [("op", "^")],
    ("у", "квадраті"): [("kw", "squared")],
    ("в", "квадраті"): [("kw", "squared")],
    ("у", "кубі"): [("kw", "cubed")],
    ("в", "кубі"): [("kw", "cubed")],
    ("квадратний", "корінь"): [("fn", "sqrt")],
    ("кубічний", "корінь"): [("fn", "cbrt")],
    ("округлити", "вниз"): [("fn", "floor")],
    ("округлити", "вгору"): [("fn", "ceil")],
    ("без", "перерахунку", "у"): [("kw", "cast")],
    ("без", "перерахунку", "в"): [("kw", "cast")],
}
_MAX_PHRASE = max(len(k) for k in PHRASES)

# cities for "час у Токіо", "15:00 у Лондоні" (nominative and locative)
CITIES = {
    "київ": "Europe/Kyiv", "києві": "Europe/Kyiv", "львів": "Europe/Kyiv",
    "львові": "Europe/Kyiv", "одеса": "Europe/Kyiv", "одесі": "Europe/Kyiv",
    "харків": "Europe/Kyiv", "харкові": "Europe/Kyiv", "дніпро": "Europe/Kyiv",
    "дніпрі": "Europe/Kyiv", "лондон": "Europe/London", "лондоні": "Europe/London",
    "париж": "Europe/Paris", "парижі": "Europe/Paris", "берлін": "Europe/Berlin",
    "берліні": "Europe/Berlin", "варшава": "Europe/Warsaw", "варшаві": "Europe/Warsaw",
    "прага": "Europe/Prague", "празі": "Europe/Prague", "рим": "Europe/Rome",
    "римі": "Europe/Rome", "мадрид": "Europe/Madrid", "мадриді": "Europe/Madrid",
    "лісабон": "Europe/Lisbon", "лісабоні": "Europe/Lisbon", "відень": "Europe/Vienna",
    "відні": "Europe/Vienna", "стамбул": "Europe/Istanbul", "стамбулі": "Europe/Istanbul",
    "дубай": "Asia/Dubai", "дубаї": "Asia/Dubai", "токіо": "Asia/Tokyo",
    "пекін": "Asia/Shanghai", "пекіні": "Asia/Shanghai", "делі": "Asia/Kolkata",
    "сідней": "Australia/Sydney", "сіднеї": "Australia/Sydney",
    "торонто": "America/Toronto", "чикаго": "America/Chicago",
}  # fmt: skip
CITY_NAMES = {
    "Europe/Kyiv": "Київ", "Europe/London": "Лондон", "Europe/Paris": "Париж",
    "Europe/Berlin": "Берлін", "Europe/Warsaw": "Варшава", "Europe/Prague": "Прага",
    "Europe/Rome": "Рим", "Europe/Madrid": "Мадрид", "Europe/Lisbon": "Лісабон",
    "Europe/Vienna": "Відень", "Europe/Istanbul": "Стамбул", "Asia/Dubai": "Дубай",
    "Asia/Tokyo": "Токіо", "Asia/Shanghai": "Шанхай", "Asia/Kolkata": "Калькутта",
    "Australia/Sydney": "Сідней", "America/Toronto": "Торонто",
    "America/Chicago": "Чикаго", "America/New_York": "Нью-Йорк",
    "America/Los_Angeles": "Лос-Анджелес", "UTC": "UTC",
}  # fmt: skip

_CONTEXT = {"на", "за", "по", "до", "від", "з", "із", "зі"}


def _text(it: Item) -> str | None:
    return it.tok.text.lower() if it.tok is it.end_tok and it.tok.kind == "WORD" else None


def apply(items: list[Item]) -> list[Item]:
    """Rewrite Ukrainian phrases and context words in a classified line."""
    from .interpreter import Item

    out: list[Item] = []
    k = 0
    while k < len(items):
        for size in range(min(_MAX_PHRASE, len(items) - k), 1, -1):
            words = tuple(_text(items[k + m]) for m in range(size))
            if words in PHRASES:
                for kind, key in PHRASES[words]:
                    out.append(Item(kind, key, items[k].tok, items[k + size - 1].end_tok))
                k += size
                break
        else:
            out.append(items[k])
            # "протягом року" means "for a year": add the "a" English would have
            nxt = items[k + 1] if k + 1 < len(items) else None
            if _text(items[k]) == "протягом" and nxt is not None and nxt.kind == "unit":
                out.append(Item("kw", "a", items[k].tok, items[k].end_tok))
            k += 1
    for k, it in enumerate(out):
        word = _text(it)
        if word in _CONTEXT and it.kind == "noise":
            key = _context(word, out, k)
            if key:
                it.kind, it.key = "kw", key
    return out


def _is_time_unit(it: Item) -> bool:
    return it.kind == "unit" and it.key in U.TIME_UNITS


def _context(word: str, items: list[Item], k: int) -> str | None:
    prev = items[k - 1] if k else None
    nxt = items[k + 1] if k + 1 < len(items) else None
    # "днів до 25 грудня", "годин від 9:00": a bare time unit starts the line
    counting = k == 1 and prev is not None and _is_time_unit(prev)
    if word == "на":
        if prev is not None and prev.kind == "kw" and prev.key in ("divided", "multiplied"):
            return "by"  # 1 000 поділити на 8
        if any(i.kind == "kw" and i.key == "remainder" for i in items[:k]):
            return "by"  # остача від ділення 21 на 5
        if nxt is not None and nxt.kind == "unit" and prev is not None:
            return "per"  # $99 на тиждень
        return None  # ₴190 на сніданок
    if word == "за":
        return "per" if nxt is not None and nxt.kind == "unit" and prev is not None else None
    if word == "по":
        return "at" if nxt is not None and nxt.kind in ("cur", "num") else None
    if word == "до":
        return "until" if counting else "to"  # з 50 до 75, з 3 березня до 30 травня
    if word == "від":
        return "since" if counting else "of"
    if prev is not None and prev.kind == "fn":
        return "of"  # корінь з 81
    return None
