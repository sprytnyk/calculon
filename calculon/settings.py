"""User settings, stored with QSettings in the place open_settings() picks."""

from dataclasses import dataclass, fields
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from .engine import Config, FormatOptions
from .engine.currency import KNOWN_CODES
from .engine.numbers import DEFAULT_NUMBER_STYLE, NUMBER_STYLES
from .paths import config_dir, data_dir, old_settings, uses_old_paths
from .translations import LANGUAGES
from .ui.theme import PALETTES

DEFAULT_RATES_URL = "https://open.er-api.com/v6/latest/USD"
FALLBACK_RATES_URL = "https://api.frankfurter.dev/v1/latest?base=USD"
TIME_FORMATS = ("24h", "12h")


def default_sheets_dir() -> str:
    """The sheets directory Calculon suggests on first start."""
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return str(Path(docs or Path.home()) / "Calculon")


def open_settings() -> QSettings:
    """settings.ini in config_dir(), or the old place for users who already have settings
    there."""
    if uses_old_paths():
        return old_settings()
    return QSettings(str(config_dir() / "settings.ini"), QSettings.Format.IniFormat)


def own_words_file() -> Path:
    """The words added with "Add to Dictionary", one per line."""
    return data_dir() / "words.txt"


def read_bool(value: object) -> bool:
    """A yes/no read back from QSettings, which gives "true" or "false" from its files."""
    return value in (True, "true", "1", 1)


@dataclass
class Settings:
    sheets_dir: str = ""  # empty until the user picks a directory on first start
    theme: str = "dark"  # dark, light, system
    colours: str = "glacier"  # glacier, ember
    language: str = "en"  # en, uk
    number_style: str = DEFAULT_NUMBER_STYLE
    time_format: str = "24h"
    dollar: str = "USD"
    max_decimals: int = 3
    money_decimals: int = 2
    rates_url: str = ""  # empty: built-in sources
    font_size: int = 14
    ligatures: bool = True
    line_numbers: bool = True
    always_on_top: bool = False
    spell_check: bool = False  # needs the system's spell checker, see calculon/spelling.py
    vim_mode: bool = False
    results_width: int = 260
    last_sheet: str = ""

    @classmethod
    def load(cls) -> Settings:
        qs = open_settings()
        s = cls()
        for f in fields(cls):
            default = getattr(s, f.name)
            value = qs.value(f.name, default)
            try:
                if isinstance(default, bool):
                    value = read_bool(value)
                elif isinstance(default, int):
                    value = int(value)  # type: ignore[arg-type]
                else:
                    value = str(value)
            except TypeError, ValueError:
                value = default
            setattr(s, f.name, value)
        # Use defaults for values this version doesn't recognize.
        choices = {
            "theme": ("dark", "light", "system"),
            "colours": tuple(PALETTES),
            "language": tuple(LANGUAGES),
            "number_style": tuple(NUMBER_STYLES),
            "time_format": TIME_FORMATS,
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
        qs = open_settings()
        for f in fields(self):
            qs.setValue(f.name, getattr(self, f.name))
        qs.sync()

    @property
    def time_24h(self) -> bool:
        return self.time_format == "24h"

    def engine_config(self) -> Config:
        return Config(
            number_style=self.number_style,
            dollar=self.dollar,
        )

    def format_options(self) -> FormatOptions:
        return FormatOptions(
            number_style=self.number_style,
            max_decimals=self.max_decimals,
            money_decimals=self.money_decimals,
            time_24h=self.time_24h,
            lang=self.language,
        )

    def rates_sources(self) -> list[str]:
        if self.rates_url.strip():
            return [self.rates_url.strip()]
        return [DEFAULT_RATES_URL, FALLBACK_RATES_URL]
