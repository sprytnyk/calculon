"""Start Calculon."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    # run as a plain script (PyInstaller does this): make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from calculon import __version__
from calculon.paths import APP_ICON


def say(text: str) -> None:
    # windowed Windows builds have no stdout; the exit code still tells the story
    if sys.stdout is not None:
        print(text)


def self_test() -> int:
    """Check a build has everything it needs: unit data, time zones, help, rates."""
    from calculon.engine import Config, FormatOptions, RateTable, evaluate_sheet
    from calculon.engine.format import LANGUAGE_NUMBER_STYLES
    from calculon.paths import FALLBACK_RATES, FONTS, HELP_DIR

    rates = RateTable.parse(FALLBACK_RATES.read_bytes())
    failed = []
    for lang in ("en", "uk"):
        text = (HELP_DIR / f"help_{lang}.txt").read_text(encoding="utf-8")
        style = LANGUAGE_NUMBER_STYLES[lang]
        opts = FormatOptions(number_style=style, lang=lang)
        res = evaluate_sheet(text, rates, Config(number_style=style), opts)
        for src, line in zip(text.split("\n"), res.lines, strict=True):
            if src.strip() and not src.lstrip().startswith(("#", "//", "---")) and not line.text:
                failed.append(f"{lang}: {src}")
    if not list(FONTS.glob("*.ttf")):
        failed.append("fonts missing")
    from PySide6.QtCore import QLibraryInfo, QTranslator

    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not QTranslator().load("qtbase_uk", folder):
        failed.append(f"Qt translations missing in {folder}")
    try:
        from PySide6.QtCore import QByteArray
        from PySide6.QtSvg import QSvgRenderer

        from calculon.ui.icons import NAMES, svg

        bad = []
        for n in sorted(NAMES):
            try:
                if not QSvgRenderer(QByteArray(svg(n, "#000"))).isValid():
                    bad.append(n)
            except OSError:
                bad.append(n)
        if bad:
            failed.append(f"icons: {', '.join(bad)}")
    except ImportError as exc:
        failed.append(f"icons: {exc}")
    for item in failed:
        say(f"FAIL {item}")
    say(f"calculon {__version__} self-test: {'ok' if not failed else 'failed'}")
    return 1 if failed else 0


def main() -> int:
    if "--version" in sys.argv[1:]:
        say(f"calculon {__version__}")
        return 0
    if "--self-test" in sys.argv[1:]:
        return self_test()
    QCoreApplication.setOrganizationName("sprytnyk.dev")
    QCoreApplication.setOrganizationDomain("sprytnyk.dev")
    QCoreApplication.setApplicationName("Calculon")
    QCoreApplication.setApplicationVersion(__version__)
    app = QApplication(sys.argv)
    app.setDesktopFileName("calculon")
    icon = QIcon(str(APP_ICON))
    app.setWindowIcon(icon)

    from calculon.ui.main_window import MainWindow

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
