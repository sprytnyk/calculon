"""Start Calculon."""

import sys

if __package__ in (None, ""):
    from pathlib import Path

    # run as a plain script (PyInstaller does this): make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calculon import __version__


def say(text: str) -> None:
    # windowed Windows builds have no stdout; the exit code still tells the story
    if sys.stdout is not None:
        print(text)


def self_test() -> int:
    """Check a build has everything it needs: unit data, time zones, help, rates."""
    from datetime import datetime
    from pathlib import Path

    from PySide6.QtCore import QByteArray, QLibraryInfo, QTranslator
    from PySide6.QtSvg import QSvgRenderer

    from calculon.engine import Config, FormatOptions, RateTable, evaluate_sheet
    from calculon.engine.numbers import NUMBER_STYLES
    from calculon.help_sheet import read_help
    from calculon.paths import FALLBACK_RATES, FONTS
    from calculon.spelling import SpellChecker, probe
    from calculon.ui.icons import NAMES, svg

    rates = RateTable.parse(FALLBACK_RATES.read_bytes())
    failed = []
    now = datetime.now().astimezone()
    config = Config(now=lambda: now)
    for lang in ("en", "uk"):
        expected_values = None
        for style in NUMBER_STYLES:
            text = read_help(lang, style)
            opts = FormatOptions(number_style=style, lang=lang)
            res = evaluate_sheet(text, rates, config, opts)
            if expected_values is None:
                expected_values = [line.value for line in res.lines]
            for src, line, value in zip(text.split("\n"), res.lines, expected_values, strict=True):
                is_example = src.strip() and not src.lstrip().startswith(("#", "//", "---"))
                if is_example and (line.value is None or line.value != value):
                    failed.append(f"{lang} ({style}): {src}")
    if not list(FONTS.glob("*.ttf")):
        failed.append("fonts missing")
    directory = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not QTranslator().load("qtbase_uk", directory):
        failed.append(f"Qt translations missing in {directory}")
    bad = []
    for n in sorted(NAMES):
        try:
            if not QSvgRenderer(QByteArray(svg(n, "#000"))).isValid():
                bad.append(n)
        except OSError:
            bad.append(n)
    if bad:
        failed.append(f"icons: {', '.join(bad)}")
    # spell check uses the system's spell checker, so a missing one is news, not a failure
    spell = probe()
    if spell.available:
        # en_US for a Hunspell file, en-US for a Windows language
        found = ", ".join(f"{lang} ({Path(src).name})" for lang, src in spell.dictionaries.items())
        say(f"spell check: {found}")
        # a build carries its own libraries; make sure the system's spell checker still works
        checker = SpellChecker.load(spell)
        samples = {"en": ("hotel", "hotell"), "uk": ("оренда", "оредна")}
        for lang in checker.languages:
            good, typo = samples[lang]
            if not checker.check(good) or checker.check(typo):
                failed.append(f"spell check: {lang} dictionary gives wrong answers")
        checker.close()
    else:
        say(f"spell check: off ({spell.install_command() or 'see the README'})")
    for item in failed:
        say(f"FAIL {item}")
    say(f"calculon {__version__} self-test: {'ok' if not failed else 'failed'}")
    return 1 if failed else 0


def _run_gui() -> int:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from calculon.paths import APP_ICON
    from calculon.ui.directory_dialog import choose_sheets_directory

    QCoreApplication.setOrganizationName("sprytnyk.dev")
    QCoreApplication.setOrganizationDomain("sprytnyk.dev")
    QCoreApplication.setApplicationName("Calculon")
    QCoreApplication.setApplicationVersion(__version__)
    app = QApplication(sys.argv)
    app.setDesktopFileName("calculon")
    icon = QIcon(str(APP_ICON))
    app.setWindowIcon(icon)
    settings = choose_sheets_directory()
    if settings is None:
        return 0

    from calculon.ui.main_window import MainWindow

    window = MainWindow(settings)
    window.setWindowIcon(icon)
    window.show()
    return app.exec()


def main() -> int:
    args = sys.argv[1:]
    if "--version" in args:
        say(f"calculon {__version__}")
        return 0
    if "--self-test" in args:
        return self_test()
    return _run_gui()


if __name__ == "__main__":
    sys.exit(main())
