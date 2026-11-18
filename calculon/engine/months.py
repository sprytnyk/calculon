"""English and Ukrainian month names accepted in calculations."""

MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ]
    )
    for m in names
}
MONTHS |= {
    m: i + 1
    for i, names in enumerate(
        [
            ("січень", "січня", "січ"),
            ("лютий", "лютого", "лют"),
            ("березень", "березня"),
            ("квітень", "квітня"),
            ("травень", "травня"),
            ("червень", "червня"),
            ("липень", "липня"),
            ("серпень", "серпня"),
            ("вересень", "вересня"),
            ("жовтень", "жовтня"),
            ("листопад", "листопада"),
            ("грудень", "грудня"),
        ]
    )
    for m in names
}
