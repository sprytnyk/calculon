"""Make the generated parts of the website in docs/ from Calculon itself.

- docs/assets/sheets.js: the example sheets, with the answers and colours that
  Calculon's engine gives, and the window labels in English and Ukrainian.
- docs/assets/theme.css: the Glacier theme's colours, for light and dark mode.
- copies of the app icon, Fira Code and the Phosphor icons the page uses.

Run `make site` (python -m scripts.build_site) after changing the engine, the examples
or the Glacier theme.
tests/test_site.py fails when these files are out of date.
"""

import json
import shutil
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from calculon.engine import Config, FormatOptions, RateTable, evaluate_sheet, format_value
from calculon.engine.format import MONTHS_UK
from calculon.paths import FALLBACK_RATES
from calculon.translations import tr
from calculon.ui.icons import GROUPS
from calculon.ui.theme import GLACIER_DARK, GLACIER_LIGHT, Theme

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
# "now" for the examples, so answers don't depend on the day the script runs
NOW = datetime(2026, 11, 14, 10, 0)
STYLE = {"en": "comma_dot", "uk": "space_comma"}

SHEETS = {
    "en": {
        "hero": """# Weekend in Lviv
Train: 2 × 850 UAH
Hotel: 2 nights × 1,900 UAH
Coffee and cake: 4 × 180 UAH
Museum 2 × 250 UAH
total in EUR""",
        "basics": """# Moving budget
rent = $1,450
deposit = rent × 2
Movers: $380 for the truck + $45 tip
Sofa $1,200 - 15%
total""",
        "money": """# Shopping in London
Jacket: £89 in USD
Coffee £4.50 × 6 in EUR
20% off $80
Run: 10 km in miles
Oven 180 °C in °F
1.5 TB at 25 MB/s in hours""",
        "dates": """# Lisbon trip
@from 14.11.2026 09:00
Flight: 3 hours
Hotel: 2 nights
Tram tour: 90 minutes
@to
14.11.2026 + 3 weeks
days between 14.11.2026 and 25.12.2026""",
        "spelling": """# Ремонт кухні
Плитка: 650 грн × 12
Шпаклівкаа: 4 × 380 грн
Робота 15,000 грн
Кухонні меблі 48,000 грн − 10%
разом""",
    },
    "uk": {
        "hero": """# Вихідні у Львові
Потяг: 2 × 850 грн
Готель: 2 × 1 900 грн
Кава з тістечком: 4 × 180 грн
Музей 2 × 250 грн
разом у EUR""",
        "basics": """# Переїзд
оренда = 1 450 $
застава = оренда × 2
Вантажники: 380 $ за машину + 45 $ на чай
Диван 1 200 $ − 15%
разом""",
        "money": """# Покупки в Лондоні
Куртка: 89 £ у USD
Кава 4,50 £ × 6 у EUR
20% знижки від 80 $
Пробіжка: 10 км у милях
Духовка 180 °C у °F
1,5 ТБ при 25 МБ/с у годинах""",
        "dates": """# Поїздка до Лісабона
@from 14.11.2026 09:00
Переліт: 3 години
Готель: 2 ночі
Екскурсія трамваєм: 90 хвилин
@to
14.11.2026 + 3 тижні
днів між 14.11.2026 і 25.12.2026""",
        "spelling": """# Ремонт кухні
Плитка: 650 грн × 12
Шпаклівкаа: 4 × 380 грн
Робота 15 000 грн
Кухонні меблі 48 000 грн − 10%
разом""",
    },
}
# The misspelled word in the spelling sheet, and what Hunspell's uk_UA dictionary
# suggests for it. Browsers have no Hunspell, so this is written down here.
MISSPELLED = "Шпаклівкаа"
SUGGESTIONS = ["Шпаклівка", "Шпаклівкам", "Шпаклівках", "Шпаклівка а", "Шпаківка"]
# the sidebar of the window at the top of the page: (folder, [sheets]), then loose sheets
SIDEBAR = [("trips", ["hero", "dates"]), ("home", ["basics", "spelling"]), (None, ["money"])]
FOLDERS = {"en": {"trips": "Trips", "home": "Home"}, "uk": {"trips": "Подорожі", "home": "Дім"}}
# right-click menu: Edit menu items, their shortcuts and icons, as in the app
MENU = [
    [("undo", "Ctrl+Z", "undo"), ("redo", "Ctrl+Shift+Z", "redo")],
    [
        ("cut", "Ctrl+X", "cut"),
        ("copy", "Ctrl+C", "copy"),
        ("paste", "Ctrl+V", "paste"),
        ("select_all", "Ctrl+A", "select_all"),
    ],
    [
        ("toggle_comment", "Ctrl+/", "comment"),
        ("copy_result", "Ctrl+Shift+C", "copy_result"),
        ("insert_reference", "Ctrl+L", "insert_reference"),
    ],
]
# icons the page shows, besides the menu's
PAGE_ICONS = [
    "sheet", "folder", "help", "trash", "spell_add", "spell_ignore",
    "colours", "rates", "open_folder", "language", "numbers", "shortcuts",
]  # fmt: skip
COPIES = {
    "assets/icon.png": "icon.png",
    "assets/fonts/FiraCode-Regular.ttf": "fonts/FiraCode-Regular.ttf",
    "assets/fonts/FiraCode-Bold.ttf": "fonts/FiraCode-Bold.ttf",
    "assets/fonts/OFL.txt": "fonts/OFL.txt",
    "assets/icons/LICENSE.txt": "icons/LICENSE.txt",
}


def rates() -> RateTable:
    return RateTable.parse(FALLBACK_RATES.read_bytes(), "bundled snapshot")


def rates_date(table: RateTable, lang: str) -> str:
    day = datetime.fromtimestamp(table.updated, UTC)
    if lang == "uk":
        return f"{day.day} {MONTHS_UK[day.month - 1]} {day.year}"
    return f"{day.day} {day:%B %Y}"


def sheet(text: str, lang: str, table: RateTable) -> dict[str, Any]:
    style = STYLE[lang]
    opts = FormatOptions(number_style=style, lang=lang)
    result = evaluate_sheet(text, table, Config(number_style=style, now=lambda: NOW), opts)
    lines: list[dict[str, Any]] = []
    for src, line in zip(text.splitlines(), result.lines, strict=True):
        if line.error:
            raise ValueError(f"{lang}: {src!r} gives an error: {line.error}")
        lines.append(
            {
                "text": src,
                "spans": [[a, b, cls] for a, b, cls in line.spans],
                "answer": line.text,
                "total": line.is_total,
            }
        )
    name = text.splitlines()[0].lstrip("# ")
    total = format_value(result.total, opts) if result.total is not None else ""
    return {"name": name, "lines": lines, "total": tr(lang, "total", text=total) if total else ""}


def page_data(lang: str, table: RateTable) -> dict[str, Any]:
    sheets = {key: sheet(text, lang, table) for key, text in SHEETS[lang].items()}
    spelling = sheets["spelling"]
    for n, line in enumerate(spelling["lines"]):
        if (start := line["text"].find(MISSPELLED)) >= 0:
            spelling["misspelled"] = {"line": n, "start": start, "end": start + len(MISSPELLED)}
    spelling["suggestions"] = SUGGESTIONS
    t = lambda key, **kw: tr(lang, key, **kw)  # noqa: E731
    return {
        "rates_date": rates_date(table, lang),
        "ui": {
            "menus": [t(f"menu_{k}").replace("&", "") for k in ("file", "edit", "view", "help")],
            "sheets": t("sheets"),
            "help": t("help"),
            "trash": t("trash"),
            "rates": t("rates_ok", when=rates_date(table, lang), source=t("rates_bundled")),
            "menu": [[[t(key), keys, icon] for key, keys, icon in group] for group in MENU],
            "spell_add": t("spell_add"),
            "spell_ignore": t("spell_ignore"),
        },
        "icon_groups": {name: GROUPS.get(name, "neutral") for name in icon_names()},
        "sidebar": [[FOLDERS[lang][folder] if folder else None, keys] for folder, keys in SIDEBAR],
        "sheets": sheets,
    }


def icon_names() -> list[str]:
    return sorted({icon for group in MENU for _key, _keys, icon in group} | set(PAGE_ICONS))


def theme_css() -> str:
    def block(theme: Theme) -> str:
        names = [f for f in theme.__dataclass_fields__ if f not in ("name", "icons")]
        lines = [f"  --{n.replace('_', '-')}: {getattr(theme, n)};" for n in names]
        lines += [f"  --icon-{k}: {v};" for k, v in theme.icons.items()]
        return "\n".join(lines)

    dark = textwrap.indent(block(GLACIER_DARK), "  ")

    return (
        "/* Made by scripts/build_site.py from Calculon's Glacier theme. Don't edit by hand. */\n"
        f":root {{\n  color-scheme: light dark;\n{block(GLACIER_LIGHT)}\n}}\n"
        "@media (prefers-color-scheme: dark) {\n"
        f"  :root {{\n{dark}\n  }}\n"
        "}\n"
    )


def build() -> dict[Path, str]:
    table = rates()
    data = {lang: page_data(lang, table) for lang in SHEETS}
    js = (
        "// Made by scripts/build_site.py from Calculon's engine. Don't edit by hand.\n"
        f"window.CALCULON = {json.dumps(data, ensure_ascii=False, indent=1)};\n"
    )
    return {DOCS / "assets" / "sheets.js": js, DOCS / "assets" / "theme.css": theme_css()}


def main() -> None:
    for path, text in build().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(path.relative_to(ROOT))
    copies = dict(COPIES) | {f"assets/icons/{n}.svg": f"icons/{n}.svg" for n in icon_names()}
    for src, dst in copies.items():
        target = DOCS / "assets" / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".svg":
            # Phosphor's files end without a newline; add one so pre-commit leaves them be
            target.write_text((ROOT / src).read_text(encoding="utf-8").rstrip("\n") + "\n")
        else:
            shutil.copyfile(ROOT / src, target)
    print(f"docs/assets: {len(copies)} copied files")


if __name__ == "__main__":
    main()
