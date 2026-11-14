"""Make docs/demo.gif for the README: the Lviv trip sheet typed out in Ember, then Glacier.

Run with: make gif (needs ffmpeg)

It drives the real app offscreen, with HOME and the XDG folders in a temp dir so
nothing touches your own settings or sheets. Rates come from the bundled snapshot.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from calculon import rates
from calculon.storage import SheetStore
from calculon.ui.main_window import WELCOME, MainWindow

GIF = Path(__file__).resolve().parent.parent / "docs" / "demo.gif"
# like the old screenshots: a 1414 x 863 window on a screen scaled to 120%
SCALE = 1.2
SIZE = (1178, 719)

LVIV = """# Weekend in Lviv
train = 2 × 850 UAH
hotel = 2 nights × 1,900 UAH
coffee = 4 × 180 UAH
museum = 2 × 250 UAH
trip = train + hotel + coffee + museum in EUR
trip / 2 // per person

# Shopping
$80 - 15%
180 is 10% off what
20% of 1,250

# Units and time
5 km in miles
3 hours 20 min in minutes
time in Tokyo
days until 25 December
sqrt(2) + 2^10
"""

OTHER_SHEETS = {
    "Budget.txt": "# Budget\nrent = $1,450\nfood = $600\nrent + food\n",
    "Trips/Kyiv weekend.txt": "# Kyiv weekend\ntrain = 2 × 850 UAH\nhotel = 2 nights × 1,900 UAH\n",
    "Groceries.txt": "# Groceries\nmilk 2 × $1.20\nbread $3.50\n",
}


def isolate(home: Path) -> None:
    """Point HOME and the XDG folders at home, before Qt looks them up."""
    os.environ.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local" / "share"),
        XDG_CACHE_HOME=str(home / ".cache"),
        QT_SCALE_FACTOR=str(SCALE),
    )


def make_sheets(folder: Path) -> None:
    store = SheetStore(folder)
    for rel, text in {**OTHER_SHEETS, "Welcome.txt": WELCOME, "Trips/Lviv.txt": ""}.items():
        store.path(rel).parent.mkdir(parents=True, exist_ok=True)
        store.write(rel, text)
    store.pin("Budget.txt")


def record(folder: Path) -> list[tuple[Path, float]]:
    """Save a PNG per step into folder, and return each with how long it shows."""
    rates.RatesService.refresh = lambda self: None  # keep the bundled snapshot
    sheets = folder / "sheets"
    make_sheets(sheets)
    qs = QSettings()
    qs.setValue("sheets_dir", str(sheets))
    qs.setValue("last_sheet", "Trips/Lviv.txt")
    qs.setValue("sidebar/expanded", ["Trips"])
    qs.sync()

    window = MainWindow()
    window.resize(*SIZE)
    window.show()
    window.editor.setFocus()
    frames: list[tuple[Path, float]] = []

    def snap(seconds: float) -> None:
        for _ in range(3):
            QApplication.processEvents()
        path = folder / f"{len(frames):04d}.png"
        window.grab().save(str(path))
        frames.append((path, seconds))

    def type_text(text: str) -> None:
        """Type a word at a time, with a pause at the end of each line."""
        cursor = window.editor.textCursor()
        for line in text.splitlines(keepends=True):
            words = line.rstrip("\n").split(" ")
            for i, word in enumerate(words):
                cursor.insertText(word if i == len(words) - 1 else word + " ")
                window.editor.setTextCursor(cursor)
                snap(0.09)
            if line.endswith("\n"):
                snap(0.35)
                cursor.insertText("\n")
                window.editor.setTextCursor(cursor)

    try:
        snap(0.8)
        type_text(LVIV)
        window.editor.moveCursor(QTextCursor.MoveOperation.Start)
        snap(3.0)
        window.set_colours("glacier")
        snap(3.5)
    finally:
        window.close()
    return frames


def write_gif(frames: list[tuple[Path, float]], gif: Path) -> None:
    """Join the frames with ffmpeg, using one shared palette of flat UI colours."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg isn't installed")
    lines = [f"file '{path}'\nduration {seconds}" for path, seconds in frames]
    # ffmpeg skips the last duration unless the last file is listed again
    lines.append(f"file '{frames[-1][0]}'")
    playlist = frames[0][0].parent / "frames.txt"
    playlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    palette = (
        "split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];"
        "[b][p]paletteuse=dither=none:diff_mode=rectangle"
    )
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0"]
        + ["-i", str(playlist), "-vf", palette, "-loop", "0", str(gif)],
        check=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        isolate(folder / "home")
        QCoreApplication.setOrganizationName("calculon-gif")
        QCoreApplication.setApplicationName("Calculon")
        app = QApplication(sys.argv)
        app.setDesktopFileName("calculon")
        write_gif(record(folder), GIF)
    print(f"wrote {GIF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
