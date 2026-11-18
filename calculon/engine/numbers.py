"""The decimal and grouping separators shared by input, output and Settings."""

GROUPING_SPACES = " \u00a0\u202f\u2007\u2009"
DEFAULT_NUMBER_STYLE = "comma_dot"
NUMBER_STYLES = {
    "comma_dot": (",", "."),
    "dot_comma": (".", ","),
    "space_comma": ("\u202f", ","),
    "space_dot": ("\u202f", "."),
}
SPACE_TRANSLATION = str.maketrans(dict.fromkeys(GROUPING_SPACES, "\u202f"))


def separators(style: str) -> tuple[str, str]:
    return NUMBER_STYLES.get(style, NUMBER_STYLES[DEFAULT_NUMBER_STYLE])


def number_sample(style: str) -> str:
    group, point = separators(style)
    return f"1{group}234{point}56"


def decimal_mantissa(text: str, group: str, point: str) -> tuple[str | None, bool]:
    """Return the normalized number and whether more digits could complete it."""
    whole, decimal_mark, fraction = text.translate(SPACE_TRANSLATION).partition(point)
    if group in whole:
        first, *middle, last = whole.split(group)
        if not (first.isdecimal() and 1 <= len(first) <= 3):
            return None, False
        if any(not part.isdecimal() or len(part) != 3 for part in middle):
            return None, False
        if len(last) != 3 or not last.isdecimal():
            incomplete = not decimal_mark and len(last) < 3 and (not last or last.isdecimal())
            return None, incomplete
        whole = first + "".join(middle) + last
    elif whole and not whole.isdecimal():
        return None, False
    if not decimal_mark:
        return (whole, False) if whole else (None, True)
    if not fraction:
        return None, True
    if not fraction.isdecimal():
        return None, False
    return f"{whole}.{fraction}", False
