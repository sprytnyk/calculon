"""UI text in English and Ukrainian."""

from . import en, uk

LANGUAGES = {"en": "English", "uk": "Українська"}
_TABLES = {"en": en.T, "uk": uk.T}


def tr(lang: str, key: str, **kwargs: object) -> str:
    text = _TABLES.get(lang, en.T).get(key) or en.T.get(key, key)
    return text.format(**kwargs) if kwargs else text


__all__ = ["LANGUAGES", "tr"]
