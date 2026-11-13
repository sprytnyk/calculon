"""Unit table and unit math.

Physical units are converted with pint, but only words from the table below are
recognised, so ordinary words like "at", "a" or "in" never turn into obscure units.
Magnitudes stay Decimal; pint only provides conversion factors.
"""

from decimal import Decimal
from functools import cache

import pint

UREG = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
for _prefix in ("", "kilo", "mega", "giga", "tera"):
    UREG.define(f"{_prefix}bit_per_second = {_prefix}bit / second")
    UREG.define(f"{_prefix}byte_per_second = {_prefix}byte / second")
UREG.define("night = day")

# A unit expression is a tuple of (atom, power). An atom is a pint unit name
# ("kilometer") or a currency code prefixed with CUR ("¤USD").
CUR = "¤"
type Units = tuple[tuple[str, int], ...]

# pint name, display (singular, plural), case-sensitive symbols, case-insensitive names
_DEFS: list[tuple[str, tuple[str, str], list[str], list[str]]] = [
    # length
    (
        "millimeter",
        ("mm", "mm"),
        ["mm"],
        ["millimeter", "millimeters", "millimetre", "millimetres"],
    ),
    (
        "centimeter",
        ("cm", "cm"),
        ["cm"],
        ["centimeter", "centimeters", "centimetre", "centimetres"],
    ),
    ("meter", ("m", "m"), ["m"], ["meter", "meters", "metre", "metres"]),
    ("kilometer", ("km", "km"), ["km"], ["kilometer", "kilometers", "kilometre", "kilometres"]),
    ("micrometer", ("µm", "µm"), ["µm", "um"], ["micrometer", "micrometers", "micron", "microns"]),
    ("nanometer", ("nm", "nm"), ["nm"], ["nanometer", "nanometers"]),
    ("inch", ("in", "in"), [], ["inch", "inches"]),
    ("foot", ("ft", "ft"), ["ft"], ["foot", "feet"]),
    ("yard", ("yd", "yd"), ["yd"], ["yard", "yards"]),
    ("mile", ("mi", "mi"), ["mi"], ["mile", "miles"]),
    ("nautical_mile", ("nmi", "nmi"), ["nmi"], ["nauticalmile", "nauticalmiles"]),
    ("light_year", ("ly", "ly"), ["ly"], ["lightyear", "lightyears"]),
    # mass
    ("milligram", ("mg", "mg"), ["mg"], ["milligram", "milligrams"]),
    ("gram", ("g", "g"), ["g"], ["gram", "grams", "gramme", "grammes"]),
    ("kilogram", ("kg", "kg"), ["kg"], ["kilogram", "kilograms", "kilo", "kilos"]),
    ("metric_ton", ("t", "t"), ["t"], ["tonne", "tonnes", "ton", "tons"]),
    ("pound", ("lb", "lb"), ["lb", "lbs"], ["pound", "pounds"]),
    ("ounce", ("oz", "oz"), ["oz"], ["ounce", "ounces"]),
    ("stone", ("st", "st"), ["st"], ["stone", "stones"]),
    ("carat", ("ct", "ct"), ["ct"], ["carat", "carats"]),
    # volume
    (
        "milliliter",
        ("ml", "ml"),
        ["ml", "mL"],
        ["milliliter", "milliliters", "millilitre", "millilitres"],
    ),
    (
        "centiliter",
        ("cl", "cl"),
        ["cl", "cL"],
        ["centiliter", "centiliters", "centilitre", "centilitres"],
    ),
    (
        "deciliter",
        ("dl", "dl"),
        ["dl", "dL"],
        ["deciliter", "deciliters", "decilitre", "decilitres"],
    ),
    ("liter", ("L", "L"), ["l", "L"], ["liter", "liters", "litre", "litres"]),
    ("gallon", ("gal", "gal"), ["gal"], ["gallon", "gallons"]),
    ("quart", ("qt", "qt"), ["qt"], ["quart", "quarts"]),
    ("pint", ("pt", "pt"), ["pt"], ["pint", "pints"]),
    ("cup", ("cup", "cups"), [], ["cup", "cups"]),
    ("tablespoon", ("tbsp", "tbsp"), ["tbsp"], ["tablespoon", "tablespoons"]),
    ("teaspoon", ("tsp", "tsp"), ["tsp"], ["teaspoon", "teaspoons"]),
    ("fluid_ounce", ("fl oz", "fl oz"), ["floz"], ["fluidounce", "fluidounces"]),
    # area
    ("hectare", ("ha", "ha"), ["ha"], ["hectare", "hectares"]),
    ("acre", ("acre", "acres"), [], ["acre", "acres"]),
    # time
    ("millisecond", ("ms", "ms"), ["ms"], ["millisecond", "milliseconds", "msec", "msecs"]),
    ("second", ("second", "seconds"), ["s"], ["second", "seconds", "sec", "secs"]),
    ("minute", ("minute", "minutes"), [], ["minute", "minutes", "min", "mins"]),
    ("hour", ("hour", "hours"), ["h"], ["hour", "hours", "hr", "hrs"]),
    ("day", ("day", "days"), ["d"], ["day", "days"]),
    ("night", ("night", "nights"), [], ["night", "nights"]),
    ("week", ("week", "weeks"), [], ["week", "weeks", "wk", "wks"]),
    ("fortnight", ("fortnight", "fortnights"), [], ["fortnight", "fortnights"]),
    ("month", ("month", "months"), [], ["month", "months", "mo", "mos"]),
    ("year", ("year", "years"), [], ["year", "years", "yr", "yrs"]),
    ("decade", ("decade", "decades"), [], ["decade", "decades"]),
    ("century", ("century", "centuries"), [], ["century", "centuries"]),
    # temperature
    ("degree_Celsius", ("°C", "°C"), ["°C", "℃", "C"], ["celsius", "degc"]),
    ("degree_Fahrenheit", ("°F", "°F"), ["°F", "℉", "F"], ["fahrenheit", "degf"]),
    ("kelvin", ("K", "K"), ["K"], ["kelvin", "kelvins"]),
    # data: exact case is SI (Mb megabit, MB megabyte); lowercase mb, gb, kb mean bytes,
    # the way people write file sizes. Anything with "bit" or "bps" is bits.
    ("bit", ("bit", "bits"), ["b"], ["bit", "bits"]),
    ("byte", ("B", "B"), ["B"], ["byte", "bytes"]),
    ("kilobit", ("kbit", "kbit"), ["kbit"], ["kilobit", "kilobits"]),
    ("megabit", ("Mb", "Mb"), ["Mb", "Mbit", "mbit"], ["megabit", "megabits"]),
    ("gigabit", ("Gb", "Gb"), ["Gb", "Gbit", "gbit"], ["gigabit", "gigabits"]),
    ("terabit", ("Tb", "Tb"), ["Tb", "Tbit", "tbit"], ["terabit", "terabits"]),
    ("kilobyte", ("kB", "kB"), ["kB", "KB", "kb"], ["kilobyte", "kilobytes"]),
    ("megabyte", ("MB", "MB"), ["MB", "mb"], ["megabyte", "megabytes"]),
    ("gigabyte", ("GB", "GB"), ["GB", "gb"], ["gigabyte", "gigabytes"]),
    ("terabyte", ("TB", "TB"), ["TB", "tb"], ["terabyte", "terabytes"]),
    ("petabyte", ("PB", "PB"), ["PB", "pb"], ["petabyte", "petabytes"]),
    ("kibibyte", ("KiB", "KiB"), ["KiB", "kib"], ["kibibyte", "kibibytes"]),
    ("mebibyte", ("MiB", "MiB"), ["MiB", "mib"], ["mebibyte", "mebibytes"]),
    ("gibibyte", ("GiB", "GiB"), ["GiB", "gib"], ["gibibyte", "gibibytes"]),
    ("tebibyte", ("TiB", "TiB"), ["TiB", "tib"], ["tebibyte", "tebibytes"]),
    # speed (compound units are also built with "/" and "per")
    ("mile_per_hour", ("mph", "mph"), ["mph"], []),
    ("kilometer_per_hour", ("km/h", "km/h"), ["kph", "kmh"], []),
    ("knot", ("kn", "kn"), ["kn", "kt"], ["knot", "knots"]),
    # "x_per_y" names are read as x / y, so 10 GB / 100 Mbps gives a time
    ("bit_per_second", ("bps", "bps"), ["bps"], []),
    ("kilobit_per_second", ("kbps", "kbps"), ["kbps", "Kbps"], []),
    ("megabit_per_second", ("Mbps", "Mbps"), ["Mbps", "mbps"], []),
    ("gigabit_per_second", ("Gbps", "Gbps"), ["Gbps", "gbps"], []),
    ("terabit_per_second", ("Tbps", "Tbps"), ["Tbps", "tbps"], []),
    ("byte_per_second", ("B/s", "B/s"), ["Bps"], []),
    ("kilobyte_per_second", ("kB/s", "kB/s"), ["kBps", "KBps", "kBs", "KBs", "kbs"], []),
    ("megabyte_per_second", ("MB/s", "MB/s"), ["MBps", "MBs", "mbs"], []),
    ("gigabyte_per_second", ("GB/s", "GB/s"), ["GBps", "GBs", "gbs"], []),
    ("terabyte_per_second", ("TB/s", "TB/s"), ["TBps", "TBs", "tbs"], []),
    # energy, power, pressure, frequency
    ("joule", ("J", "J"), ["J"], ["joule", "joules"]),
    ("kilojoule", ("kJ", "kJ"), ["kJ"], ["kilojoule", "kilojoules"]),
    ("calorie", ("cal", "cal"), ["cal"], ["calorie", "calories"]),
    ("kilocalorie", ("kcal", "kcal"), ["kcal", "Cal"], ["kilocalorie", "kilocalories"]),
    ("watt_hour", ("Wh", "Wh"), ["Wh"], []),
    ("kilowatt_hour", ("kWh", "kWh"), ["kWh"], []),
    ("watt", ("W", "W"), ["W"], ["watt", "watts"]),
    ("kilowatt", ("kW", "kW"), ["kW"], ["kilowatt", "kilowatts"]),
    ("megawatt", ("MW", "MW"), ["MW"], ["megawatt", "megawatts"]),
    ("horsepower", ("hp", "hp"), ["hp"], ["horsepower"]),
    ("pascal", ("Pa", "Pa"), ["Pa"], ["pascal", "pascals"]),
    ("kilopascal", ("kPa", "kPa"), ["kPa"], ["kilopascal", "kilopascals"]),
    ("bar", ("bar", "bar"), [], ["bar", "bars"]),
    ("psi", ("psi", "psi"), ["psi"], []),
    ("standard_atmosphere", ("atm", "atm"), ["atm"], ["atmosphere", "atmospheres"]),
    ("hertz", ("Hz", "Hz"), ["Hz"], ["hertz"]),
    ("kilohertz", ("kHz", "kHz"), ["kHz"], ["kilohertz"]),
    ("megahertz", ("MHz", "MHz"), ["MHz"], ["megahertz"]),
    ("gigahertz", ("GHz", "GHz"), ["GHz"], ["gigahertz"]),
    # angle
    ("degree", ("°", "°"), ["°", "deg"], ["degree", "degrees"]),
    ("radian", ("rad", "rad"), ["rad"], ["radian", "radians"]),
]

SYMBOLS: dict[str, str] = {}
NAMES: dict[str, str] = {}
DISPLAY: dict[str, tuple[str, str]] = {}
for _name, _disp, _syms, _names in _DEFS:
    DISPLAY[_name] = _disp
    for _s in _syms:
        SYMBOLS[_s] = _name
    for _n in _names:
        NAMES[_n] = _name

# Ukrainian: pint name, display (one, few, many), case-sensitive symbols, case-insensitive
# names. Display forms follow Ukrainian plurals: 1 година, 2 години, 5 годин, 1,5 години.
_UK_DEFS: list[tuple[str, tuple[str, str, str], list[str], list[str]]] = [
    ("millimeter", ("мм", "мм", "мм"), ["мм"], ["міліметр", "міліметри", "міліметрів"]),
    ("centimeter", ("см", "см", "см"), ["см"], ["сантиметр", "сантиметри", "сантиметрів"]),
    ("meter", ("м", "м", "м"), ["м"], ["метр", "метри", "метрів", "метра"]),
    ("kilometer", ("км", "км", "км"), ["км"], ["кілометр", "кілометри", "кілометрів"]),
    ("micrometer", ("мкм", "мкм", "мкм"), ["мкм"], ["мікрон", "мікрони", "мікронів"]),
    ("nanometer", ("нм", "нм", "нм"), ["нм"], ["нанометр", "нанометри", "нанометрів"]),
    ("inch", ("дюйм", "дюйми", "дюймів"), [], ["дюйм", "дюйми", "дюймів", "дюйма"]),
    ("foot", ("фут", "фути", "футів"), [], ["фут", "фути", "футів", "фута"]),
    ("yard", ("ярд", "ярди", "ярдів"), [], ["ярд", "ярди", "ярдів", "ярда"]),
    ("mile", ("миля", "милі", "миль"), [], ["миля", "милі", "миль", "милю"]),
    ("nautical_mile", ("мор. миля", "мор. милі", "мор. миль"), [], []),
    ("light_year", ("св. р.", "св. р.", "св. р."), [], []),
    ("milligram", ("мг", "мг", "мг"), ["мг"], ["міліграм", "міліграми", "міліграмів"]),
    ("gram", ("г", "г", "г"), ["г"], ["грам", "грами", "грамів", "грама"]),
    ("kilogram", ("кг", "кг", "кг"), ["кг"], ["кілограм", "кілограми", "кілограмів", "кіло"]),
    ("metric_ton", ("т", "т", "т"), ["т"], ["тонна", "тонни", "тонн", "тонну"]),
    ("pound", ("фунт", "фунти", "фунтів"), [], ["фунт", "фунти", "фунтів", "фунта"]),
    ("ounce", ("унція", "унції", "унцій"), [], ["унція", "унції", "унцій"]),
    ("stone", ("стоун", "стоуни", "стоунів"), [], []),
    ("carat", ("кар", "кар", "кар"), [], ["карат", "карати", "каратів"]),
    ("milliliter", ("мл", "мл", "мл"), ["мл"], ["мілілітр", "мілілітри", "мілілітрів"]),
    ("centiliter", ("сл", "сл", "сл"), [], []),
    ("deciliter", ("дл", "дл", "дл"), [], []),
    ("liter", ("л", "л", "л"), ["л"], ["літр", "літри", "літрів", "літра"]),
    ("gallon", ("гал", "гал", "гал"), [], ["галон", "галони", "галонів"]),
    ("quart", ("кварта", "кварти", "кварт"), [], []),
    ("pint", ("пінта", "пінти", "пінт"), [], ["пінта", "пінти", "пінт"]),
    ("cup", ("чашка", "чашки", "чашок"), [], ["чашка", "чашки", "чашок"]),
    ("tablespoon", ("ст. л.", "ст. л.", "ст. л."), [], []),
    ("teaspoon", ("ч. л.", "ч. л.", "ч. л."), [], []),
    ("fluid_ounce", ("рід. унц.", "рід. унц.", "рід. унц."), [], []),
    ("hectare", ("га", "га", "га"), ["га"], ["гектар", "гектари", "гектарів"]),
    ("acre", ("акр", "акри", "акрів"), [], ["акр", "акри", "акрів"]),
    ("millisecond", ("мс", "мс", "мс"), ["мс"], ["мілісекунда", "мілісекунди", "мілісекунд"]),
    (
        "second",
        ("секунда", "секунди", "секунд"),
        ["с"],
        ["секунда", "секунди", "секунд", "секунду", "сек"],
    ),
    (
        "minute",
        ("хвилина", "хвилини", "хвилин"),
        ["хв"],
        ["хвилина", "хвилини", "хвилин", "хвилину"],
    ),
    (
        "hour",
        ("година", "години", "годин"),
        ["год"],
        ["година", "години", "годин", "годину"],
    ),
    ("day", ("день", "дні", "днів"), ["дн"], ["день", "дні", "днів", "дня", "доба", "доби", "діб"]),
    ("night", ("ніч", "ночі", "ночей"), [], ["ніч", "ночі", "ночей"]),
    ("week", ("тиждень", "тижні", "тижнів"), ["тиж"], ["тиждень", "тижні", "тижнів", "тижня"]),
    (
        "month",
        ("місяць", "місяці", "місяців"),
        ["міс"],
        ["місяць", "місяці", "місяців", "місяця"],
    ),
    ("year", ("рік", "роки", "років"), [], ["рік", "роки", "років", "року"]),
    ("decade", ("десятиліття", "десятиліття", "десятиліть"), [], []),
    ("century", ("століття", "століття", "століть"), [], []),
    ("degree_Celsius", ("°C", "°C", "°C"), ["°С"], []),  # Cyrillic С
    ("kelvin", ("K", "K", "K"), ["К"], []),
    ("bit", ("біт", "біти", "бітів"), [], ["біт", "біти", "бітів"]),
    ("byte", ("Б", "Б", "Б"), ["Б"], ["байт", "байти", "байтів"]),
    ("kilobit", ("кбіт", "кбіт", "кбіт"), ["кбіт"], []),
    ("megabit", ("Мбіт", "Мбіт", "Мбіт"), ["Мбіт", "мбіт"], []),
    ("gigabit", ("Гбіт", "Гбіт", "Гбіт"), ["Гбіт", "гбіт"], []),
    ("terabit", ("Тбіт", "Тбіт", "Тбіт"), ["Тбіт", "тбіт"], []),
    ("kilobyte", ("кБ", "кБ", "кБ"), ["кБ", "КБ", "кб"], ["кілобайт", "кілобайти", "кілобайтів"]),
    ("megabyte", ("МБ", "МБ", "МБ"), ["МБ", "мб"], ["мегабайт", "мегабайти", "мегабайтів"]),
    ("gigabyte", ("ГБ", "ГБ", "ГБ"), ["ГБ", "гб"], ["гігабайт", "гігабайти", "гігабайтів"]),
    ("terabyte", ("ТБ", "ТБ", "ТБ"), ["ТБ", "тб"], ["терабайт", "терабайти", "терабайтів"]),
    ("petabyte", ("ПБ", "ПБ", "ПБ"), ["ПБ"], []),
    ("kibibyte", ("КіБ", "КіБ", "КіБ"), ["КіБ"], []),
    ("mebibyte", ("МіБ", "МіБ", "МіБ"), ["МіБ"], []),
    ("gibibyte", ("ГіБ", "ГіБ", "ГіБ"), ["ГіБ"], []),
    ("tebibyte", ("ТіБ", "ТіБ", "ТіБ"), ["ТіБ"], []),
    ("mile_per_hour", ("миль/год", "миль/год", "миль/год"), [], []),
    ("kilometer_per_hour", ("км/год", "км/год", "км/год"), [], []),
    ("knot", ("вузол", "вузли", "вузлів"), [], ["вузол", "вузли", "вузлів"]),
    ("kilobit_per_second", ("кбіт/с", "кбіт/с", "кбіт/с"), [], []),
    ("megabit_per_second", ("Мбіт/с", "Мбіт/с", "Мбіт/с"), [], []),
    ("gigabit_per_second", ("Гбіт/с", "Гбіт/с", "Гбіт/с"), [], []),
    ("joule", ("Дж", "Дж", "Дж"), ["Дж"], ["джоуль", "джоулі", "джоулів"]),
    ("kilojoule", ("кДж", "кДж", "кДж"), ["кДж"], []),
    ("calorie", ("кал", "кал", "кал"), ["кал"], ["калорія", "калорії", "калорій"]),
    (
        "kilocalorie",
        ("ккал", "ккал", "ккал"),
        ["ккал"],
        ["кілокалорія", "кілокалорії", "кілокалорій"],
    ),
    ("watt_hour", ("Вт·год", "Вт·год", "Вт·год"), [], []),
    ("kilowatt_hour", ("кВт·год", "кВт·год", "кВт·год"), [], []),
    ("watt", ("Вт", "Вт", "Вт"), ["Вт"], ["ват", "вати", "ватів"]),
    ("kilowatt", ("кВт", "кВт", "кВт"), ["кВт"], ["кіловат", "кіловати", "кіловатів"]),
    ("megawatt", ("МВт", "МВт", "МВт"), ["МВт"], []),
    ("horsepower", ("к. с.", "к. с.", "к. с."), [], []),
    ("pascal", ("Па", "Па", "Па"), ["Па"], []),
    ("kilopascal", ("кПа", "кПа", "кПа"), ["кПа"], []),
    ("bar", ("бар", "бар", "бар"), [], ["бар"]),
    ("standard_atmosphere", ("атм", "атм", "атм"), ["атм"], []),
    ("hertz", ("Гц", "Гц", "Гц"), ["Гц"], ["герц"]),
    ("kilohertz", ("кГц", "кГц", "кГц"), ["кГц"], []),
    ("megahertz", ("МГц", "МГц", "МГц"), ["МГц"], []),
    ("gigahertz", ("ГГц", "ГГц", "ГГц"), ["ГГц"], []),
    ("degree", ("°", "°", "°"), [], ["градус", "градуси", "градусів"]),
    ("radian", ("рад", "рад", "рад"), ["рад"], ["радіан", "радіани", "радіанів"]),
]
DISPLAY_UK: dict[str, tuple[str, str, str]] = {}
for _name, _forms, _syms, _names in _UK_DEFS:
    DISPLAY_UK[_name] = _forms
    for _s in _syms:
        SYMBOLS[_s] = _name
    for _n in _names:
        NAMES[_n] = _name


# Locative forms for conversions: "90 хв у годинах", "5 миль у кілометрах".
for _word, _name in {
    "міліметрах": "millimeter", "сантиметрах": "centimeter", "метрах": "meter",
    "кілометрах": "kilometer", "дюймах": "inch", "футах": "foot", "ярдах": "yard",
    "милях": "mile", "грамах": "gram", "кілограмах": "kilogram", "тоннах": "metric_ton",
    "фунтах": "pound", "унціях": "ounce", "літрах": "liter", "мілілітрах": "milliliter",
    "галонах": "gallon", "гектарах": "hectare", "акрах": "acre", "секундах": "second",
    "хвилинах": "minute", "годинах": "hour", "днях": "day", "добах": "day", "ночах": "night",
    "тижнях": "week", "місяцях": "month", "роках": "year", "байтах": "byte",
    "кілобайтах": "kilobyte", "мегабайтах": "megabyte", "гігабайтах": "gigabyte",
    "терабайтах": "terabyte", "бітах": "bit", "градусах": "degree", "радіанах": "radian",
    "калоріях": "calorie", "кілокалоріях": "kilocalorie",
}.items():  # fmt: skip
    NAMES[_word] = _name


def uk_plural(amount: Decimal | None, forms: tuple[str, str, str]) -> str:
    """Pick the Ukrainian form: 1 година, 2 години, 5 годин; fractions take the second."""
    one, few, many = forms
    if amount is None:
        return one
    if not amount.is_finite() or abs(amount) >= Decimal("1e15"):
        return many  # shown as 1e25: "1e25 годин"; quantize fails this big
    amount = abs(amount).quantize(Decimal("1e-6"))  # as shown, not 44.9999999
    if amount != amount.to_integral_value():
        return few
    n = int(amount)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


# Two-word unit names, matched before single words.
PHRASES: dict[tuple[str, ...], str] = {
    ("fl", "oz"): "fluid_ounce",
    ("fluid", "ounce"): "fluid_ounce",
    ("fluid", "ounces"): "fluid_ounce",
    ("nautical", "mile"): "nautical_mile",
    ("nautical", "miles"): "nautical_mile",
    ("light", "year"): "light_year",
    ("light", "years"): "light_year",
}

TIME_UNITS = (
    "century",
    "decade",
    "year",
    "month",
    "fortnight",
    "week",
    "day",
    "night",
    "hour",
    "minute",
    "second",
    "millisecond",
)
TEMPERATURES = {"degree_Celsius", "degree_Fahrenheit", "kelvin"}


def lookup(word: str) -> str | None:
    """Return the pint unit name for a word, or None."""
    if word in SYMBOLS:
        return SYMBOLS[word]
    base = word
    power = ""
    if word and word[-1] in "²³":
        base, power = word[:-1], word[-1]
    if power:
        name = SYMBOLS.get(base) or NAMES.get(base.lower())
        return name and f"{name}{'**2' if power == '²' else '**3'}"
    return NAMES.get(word.lower())


def expand(atom: str, power: int) -> list[tuple[str, int]]:
    """'megabit_per_second' becomes megabit / second, so it divides and cancels like Mb/s."""
    head, sep, tail = atom.partition("_per_")
    if sep and tail:
        return [(head, power), (tail, -power)]
    return [(atom, power)]


def split_power(atom: str) -> tuple[str, int]:
    if atom.endswith("**2"):
        return atom[:-3], 2
    if atom.endswith("**3"):
        return atom[:-3], 3
    return atom, 1


def is_currency(atom: str) -> bool:
    return atom.startswith(CUR)


CUSTOM = "~"


def is_custom(atom: str) -> bool:
    """Units made up on the fly from words used in rates: "€95/night"."""
    return atom.startswith(CUSTOM)


def singular(word: str) -> str:
    w = word.lower()
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def currency_code(units: Units) -> str | None:
    for atom, power in units:
        if is_currency(atom) and power == 1:
            return atom[1:]
    return None


@cache
def dimensionality(atom: str) -> str:
    if is_currency(atom):
        return "[currency]"
    if is_custom(atom):
        return f"[{atom}]"
    return str(UREG.Unit(atom).dimensionality)


def dims_of(units: Units) -> dict[str, int]:
    """Combined dimensionality as {base dimension: power}."""
    out: dict[str, int] = {}
    for atom, power in units:
        if is_currency(atom):
            out["[currency]"] = out.get("[currency]", 0) + power
            continue
        if is_custom(atom):
            out[f"[{atom}]"] = out.get(f"[{atom}]", 0) + power
            continue
        for dim, p in UREG.Unit(atom).dimensionality.items():
            out[dim] = out.get(dim, 0) + int(p * power)
    return {k: v for k, v in out.items() if v}


def round_factor(f: float) -> Decimal:
    return Decimal(f"{f:.12g}")


@cache
def factor(src: str, dst: str) -> Decimal:
    """How many dst are in one src (both physical, same dimensionality)."""
    return round_factor(UREG.Quantity(1, src).to(dst).magnitude)


def physical_factor(src: Units, dst: Units) -> Decimal:
    """Factor converting the physical part of src into the physical part of dst."""
    a = _pint_expr(src)
    b = _pint_expr(dst)
    if a == b:
        return Decimal(1)
    return _expr_factor(a, b)


@cache
def _expr_factor(a: str, b: str) -> Decimal:
    q = UREG.Quantity(1, a or "dimensionless")
    return round_factor(q.to(b or "dimensionless").magnitude)


def _pint_expr(units: Units) -> str:
    parts = []
    for atom, power in units:
        if is_currency(atom) or is_custom(atom):
            continue
        name, p = split_power(atom)
        parts.append(f"{name}**{p * power}")
    return " * ".join(parts)


def convert_temperature(value: Decimal, src: str, dst: str) -> Decimal:
    q = UREG.Quantity(float(value), src).to(dst).magnitude
    return round_factor(q)


def normalize(units: Units) -> Units:
    """Merge equal atoms and drop zero powers, keeping first-seen order."""
    order: list[str] = []
    powers: dict[str, int] = {}
    for atom, power in units:
        name, p = split_power(atom)
        if name not in powers:
            order.append(name)
            powers[name] = 0
        powers[name] += p * power
    return tuple((a, powers[a]) for a in order if powers[a])


def larger(a: str, b: str) -> str:
    """Of two same-dimension units, the larger one."""
    return a if factor(a, b) >= 1 else b


COMPOUND_NAMES: dict[Units, str] = {
    (("kilometer", 1), ("hour", -1)): "km/h",
    (("mile", 1), ("hour", -1)): "mph",
    (("meter", 1), ("second", -1)): "m/s",
    (("megabyte", 1), ("second", -1)): "MB/s",
    (("gigabyte", 1), ("second", -1)): "GB/s",
    (("kilobyte", 1), ("second", -1)): "kB/s",
    (("byte", 1), ("second", -1)): "B/s",
    (("terabyte", 1), ("second", -1)): "TB/s",
    (("kibibyte", 1), ("second", -1)): "KiB/s",
    (("mebibyte", 1), ("second", -1)): "MiB/s",
    (("gibibyte", 1), ("second", -1)): "GiB/s",
    (("bit", 1), ("second", -1)): "bps",
    (("kilobit", 1), ("second", -1)): "kbps",
    (("megabit", 1), ("second", -1)): "Mbps",
    (("gigabit", 1), ("second", -1)): "Gbps",
    (("terabit", 1), ("second", -1)): "Tbps",
}
COMPOUND_NAMES_UK: dict[Units, str] = {
    (("kilometer", 1), ("hour", -1)): "км/год",
    (("mile", 1), ("hour", -1)): "миль/год",
    (("meter", 1), ("second", -1)): "м/с",
    (("megabyte", 1), ("second", -1)): "МБ/с",
    (("gigabyte", 1), ("second", -1)): "ГБ/с",
    (("kilobyte", 1), ("second", -1)): "кБ/с",
    (("byte", 1), ("second", -1)): "Б/с",
    (("terabyte", 1), ("second", -1)): "ТБ/с",
    (("kibibyte", 1), ("second", -1)): "КіБ/с",
    (("mebibyte", 1), ("second", -1)): "МіБ/с",
    (("gibibyte", 1), ("second", -1)): "ГіБ/с",
    (("bit", 1), ("second", -1)): "біт/с",
    (("kilobit", 1), ("second", -1)): "кбіт/с",
    (("megabit", 1), ("second", -1)): "Мбіт/с",
    (("gigabit", 1), ("second", -1)): "Гбіт/с",
    (("terabit", 1), ("second", -1)): "Тбіт/с",
}


def display_units(
    units: Units, magnitude: Decimal | None = None, lang: str = "en"
) -> tuple[str, str]:
    """Return (prefix, suffix) text for a value's units, e.g. ("$", "/week")."""
    compound = COMPOUND_NAMES_UK if lang == "uk" else COMPOUND_NAMES
    if units in compound:
        return "", " " + compound[units]
    pos = [(a, p) for a, p in units if p > 0]
    neg = [(a, -p) for a, p in units if p < 0]
    prefix = ""
    num_parts = []
    for atom, p in pos:
        if is_currency(atom) and p == 1 and not prefix and not num_parts:
            prefix = atom
            continue
        num_parts.append(atom_text(atom, p, magnitude, lang))
    den_parts = [atom_text(a, p, None, lang) for a, p in neg]
    suffix = ""
    if num_parts:
        suffix = " " + "·".join(num_parts)
    if den_parts:
        suffix += "/" + "·".join(den_parts)
    return prefix, suffix


_SUPER = {2: "²", 3: "³"}


def atom_text(atom: str, power: int, magnitude: Decimal | None, lang: str = "en") -> str:
    """One unit as text. magnitude None means singular (as in "/hour")."""
    plural = magnitude is not None and abs(magnitude) != 1
    if is_currency(atom):
        text = atom[1:]
    elif is_custom(atom):
        text = atom[1:]
        if plural and not text.endswith("s") and text.isascii():
            text = text[:-1] + "ies" if text.endswith("y") and len(text) > 2 else text + "s"
    elif lang == "uk" and atom in DISPLAY_UK:
        text = uk_plural(magnitude if power == 1 else None, DISPLAY_UK[atom])
    else:
        sing, plur = DISPLAY.get(atom, (atom, atom))
        text = plur if plural else sing
    if power == 1:
        return text
    return text + _SUPER.get(power, f"^{power}")


def all_words() -> list[str]:
    """Unit words for autocomplete."""
    words = set(SYMBOLS) | set(NAMES)
    return sorted(w for w in words if len(w) > 1 and w.isalpha())
