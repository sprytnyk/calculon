"""User settings, stored with QSettings in the usual place for each OS."""

from dataclasses import dataclass, fields
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from .engine import Config, FormatOptions
from .engine.currency import KNOWN_CODES
from .engine.format import LANGUAGE_NUMBER_STYLES, NUMBER_STYLES
from .translations import LANGUAGES

DEFAULT_RATES_URL = "https://open.er-api.com/v6/latest/USD"
FALLBACK_RATES_URL = "https://api.frankfurter.dev/v1/latest?base=USD"


def default_sheets_dir() -> str:
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return str(Path(docs or Path.home()) / "Calculon")


def own_words_file() -> Path:
    """The words added with "Add to Dictionary", one per line."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "words.txt"


def fallback_sheets_dir() -> str:
    """Used when the sheets folder can't be written, e.g. Windows blocks Documents."""
    data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    return str(Path(data or Path.home()) / "Sheets")


@dataclass
class Settings:
    sheets_dir: str = ""
    theme: str = "dark"  # dark, light, system
    colours: str = "ember"  # ember, glacier
    language: str = "en"  # en, uk
    number_style: str = "auto"  # auto follows the language: 1,234.56 or 1 234,56
    date_order: str = "DMY"
    dollar: str = "USD"
    max_decimals: int = 6
    money_decimals: int = 2
    rates_url: str = ""  # empty: built-in sources
    font_size: int = 14
    ligatures: bool = True
    line_numbers: bool = True
    spell_check: bool = False  # needs the system's Hunspell, see calculon/spelling.py
    results_width: int = 260
    last_sheet: str = ""

    @classmethod
    def load(cls) -> Settings:
        qs = QSettings()
        s = cls()
        for f in fields(cls):
            default = getattr(s, f.name)
            value = qs.value(f.name, default)
            try:
                if isinstance(default, bool):
                    value = value in (True, "true", "1", 1)
                elif isinstance(default, int):
                    value = int(value)  # type: ignore[arg-type]
                else:
                    value = str(value)
            except TypeError, ValueError:
                value = default
            setattr(s, f.name, value)
        if not s.sheets_dir:
            s.sheets_dir = default_sheets_dir()
        # a hand-edited or newer config can hold values this version doesn't know
        choices = {
            "theme": ("dark", "light", "system"),
            "colours": ("ember", "glacier"),
            "language": tuple(LANGUAGES),
            "number_style": ("auto", *NUMBER_STYLES),
            "date_order": ("DMY", "MDY"),
            "dollar": tuple(KNOWN_CODES),
        }
        for name, allowed in choices.items():
            if getattr(s, name) not in allowed:
                setattr(s, name, getattr(cls(), name))
        s.max_decimals = max(0, min(s.max_decimals, 20))
        s.money_decimals = max(0, min(s.money_decimals, 10))
        s.font_size = max(8, min(s.font_size, 40))
        return s

    def save(self) -> None:
        qs = QSettings()
        for f in fields(self):
            qs.setValue(f.name, getattr(self, f.name))
        qs.sync()

    def resolved_number_style(self) -> str:
        if self.number_style in NUMBER_STYLES:
            return self.number_style
        return LANGUAGE_NUMBER_STYLES.get(self.language, "comma_dot")

    def engine_config(self) -> Config:
        return Config(
            number_style=self.resolved_number_style(),
            date_order=self.date_order,
            dollar=self.dollar,
        )

    def format_options(self) -> FormatOptions:
        return FormatOptions(
            number_style=self.resolved_number_style(),
            max_decimals=self.max_decimals,
            money_decimals=self.money_decimals,
            time_24h=self.date_order != "MDY",
            lang=self.language,
        )

    def rates_sources(self) -> list[str]:
        if self.rates_url.strip():
            return [self.rates_url.strip()]
        return [DEFAULT_RATES_URL, FALLBACK_RATES_URL]
