"""Make the README's demo and the website's pictures from the real app:

- docs/demo.gif: the Lviv trip sheet typed out in Glacier, then Ember.
- docs/screenshot.png and docs/screenshot-uk.png: the link previews of the English and
  Ukrainian pages, with the trip sheet in each language.
- docs/screenshot-small.png: a short sheet in a small square window, in focus mode, on a
  square picture.

The screenshots sit on soft glows of the theme's colours. The link previews are
1200 x 630, the size sites show them at.

Run with: make gif (needs ffmpeg)

It drives the real app offscreen, with HOME and the XDG folders in a temp dir so
nothing touches your own settings or sheets. Rates come from the bundled snapshot.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from array import array
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsScene,
)

from calculon import rates
from calculon.storage import SheetStore
from calculon.ui.main_window import WELCOME, MainWindow
from calculon.ui.theme import GLACIER_DARK

DOCS = Path(__file__).resolve().parent.parent / "docs"
GIF = DOCS / "demo.gif"
# the same as the old screenshots, a 1414 x 863 window on a screen scaled to 120%
SCALE = 1.2
SIZE = (1178, 719)
# the link previews' size, then for every picture the space around the window and its corners
PREVIEW = (1200, 630)
MARGIN = 48
RADIUS = 10
# The screenshots use Glacier's dark mode, the app's default. The backdrop uses its
# colours, violet top left, blue top right and green bottom right.
THEME = GLACIER_DARK
GLOWS = [((0, 0), THEME.variable), ((1, 0), THEME.accent), ((1, 1), THEME.result)]
# 4 x 4 ordered dither, what each pixel adds before it's rounded down to 8 bits
BAYER = [
    [(n + 0.5) / 16 for n in row]
    for row in ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
]

LVIV = {
    "en": """# Weekend in Lviv
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
""",
    "uk": """# Вихідні у Львові
потяг = 2 × 850 грн
готель = 2 ночі × 1 900 грн
кава = 4 × 180 грн
музей = 2 × 250 грн
поїздка = потяг + готель + кава + музей у EUR
поїздка / 2 // на людину

# Покупки
80 $ − 15%
180 це 10% знижки від чого
20% від 1 250

# Одиниці й час
5 км у милях
3 години 20 хв у хвилинах
час у Токіо
днів до 25 грудня
sqrt(2) + 2^10
""",
}
LVIV_SHEET = {"en": "Trips/Lviv.txt", "uk": "Подорожі/Львів.txt"}

# short lines from the sheet above, for a small square window
SHORT = """# Weekend in Lviv
train = 2 × 850 UAH
hotel = 2 × 1,900 UAH
coffee = 4 × 180 UAH
museum = 2 × 250 UAH
trip = total in EUR
trip / 2 // each

# Shopping
$80 - 15%
180 is 10% off what
20% of 1,250

# Units and time
5 km in miles
3 hours in minutes
sqrt(2) + 2^10
"""

# the other sheets in the sidebar; the first one is pinned
OTHER_SHEETS = {
    "en": {
        "Budget.txt": "# Budget\nrent = $1,450\nfood = $600\nrent + food\n",
        "Trips/Kyiv weekend.txt": (
            "# Kyiv weekend\ntrain = 2 × 850 UAH\nhotel = 2 nights × 1,900 UAH\n"
        ),
        "Groceries.txt": "# Groceries\nmilk 2 × $1.20\nbread $3.50\n",
        "Welcome.txt": WELCOME,
    },
    "uk": {
        "Бюджет.txt": "# Бюджет\nоренда = 1 450 $\nїжа = 600 $\nоренда + їжа\n",
        "Подорожі/Вихідні в Києві.txt": (
            "# Вихідні в Києві\nпотяг = 2 × 850 грн\nготель = 2 ночі × 1 900 грн\n"
        ),
        "Продукти.txt": "# Продукти\nмолоко 2 × 1,20 $\nхліб 3,50 $\n",
    },
}


@dataclass(frozen=True)
class Shot:
    file: str  # in docs/
    lang: str
    sheet: str  # the open sheet, as a path in the sheets folder
    text: str
    size: tuple[int, int] = SIZE
    focus: bool = False
    results_width: int = 260
    picture: tuple[int, int] = PREVIEW  # the saved file, with the window in the middle


SHOTS = [
    Shot("screenshot.png", "en", LVIV_SHEET["en"], LVIV["en"]),
    Shot("screenshot-uk.png", "uk", LVIV_SHEET["uk"], LVIV["uk"]),
    Shot(
        "screenshot-small.png",
        "en",
        "Short.txt",
        SHORT,
        size=(500, 500),
        focus=True,
        results_width=150,
        picture=(696, 696),  # the 600 px window at full size, with MARGIN on every side
    ),
]


def isolate(home: Path) -> None:
    """Point HOME and the XDG folders at home, before Qt looks them up."""
    os.environ.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local" / "share"),
        XDG_CACHE_HOME=str(home / ".cache"),
        QT_SCALE_FACTOR=str(SCALE),
    )


def open_window(folder: Path, lang: str, sheet: str, text: str, focus: bool = False) -> MainWindow:
    """Fill a new sheets folder in folder, and open the app on sheet, in Glacier."""
    store = SheetStore(folder)
    sheets = {**OTHER_SHEETS[lang], sheet: text}
    for rel, body in sheets.items():
        store.path(rel).parent.mkdir(parents=True, exist_ok=True)
        store.write(rel, body)
    store.pin(next(iter(sheets)))
    qs = QSettings()
    for key, value in {
        "sheets_dir": str(folder),
        "language": lang,
        "colours": "glacier",
        "last_sheet": sheet,
        "sidebar/expanded": [str(Path(sheet).parent)],
        "window/focus": focus,
    }.items():
        qs.setValue(key, value)
    qs.sync()
    return MainWindow()


def settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


def record(folder: Path) -> list[tuple[Path, float]]:
    """Save a PNG per step into folder. Return each with how long it shows."""
    window = open_window(folder / "sheets", "en", LVIV_SHEET["en"], "")
    window.resize(*SIZE)
    window.show()
    window.editor.setFocus()
    frames: list[tuple[Path, float]] = []

    def snap(seconds: float) -> None:
        settle()
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
        type_text(LVIV["en"])
        window.editor.moveCursor(QTextCursor.MoveOperation.Start)
        snap(3.0)
        window.set_colours("ember")
        snap(3.5)
    finally:
        window.close()
    return frames


def screenshot(folder: Path, shot: Shot) -> QImage:
    window = open_window(folder, shot.lang, shot.sheet, shot.text, shot.focus)
    window.resize(*shot.size)
    window.show()
    window.editor.set_results_width(shot.results_width)  # after show(): it caps at half the width
    window.editor.setFocus()
    window.editor.moveCursor(QTextCursor.MoveOperation.Start)
    try:
        settle()
        image = window.grab().toImage()
        # The grab says it's at 120% (SCALE), so QPainter would draw it 1/1.2 the size.
        image.setDevicePixelRatio(1)
        return image
    finally:
        window.close()


def backdrop(size: tuple[int, int]) -> QImage:
    """Soft glows of the theme's colours on its background, like a mesh gradient.
    It draws with 16 bits a channel and dithers down to 8, so the dark blends show no steps."""
    w, h = size
    deep = QImage(w, h, QImage.Format.Format_RGBA64)
    deep.fill(QColor(THEME.bg))
    painter = QPainter(deep)
    for (x, y), colour in GLOWS:
        glow = QRadialGradient(QPointF(x * w, y * h), 0.8 * w)
        for i in range(11):
            s = i / 10
            tint = QColor(colour)
            # fades out smoothly, with no ring at the edge
            tint.setAlphaF(0.45 * (1 - s * s * (3 - 2 * s)))
            glow.setColorAt(s, tint)
        painter.fillRect(deep.rect(), glow)
    painter.end()

    deep_bytes = deep.constBits().tobytes()
    channels = array("H", deep_bytes[: w * h * 8])  # R, G, B, A for each pixel
    out = bytearray(w * h * 3)
    i = 0
    for y in range(h):
        steps = BAYER[y % 4]
        for x in range(w):
            step = steps[x % 4]
            first = (y * w + x) * 4
            for channel in range(3):
                out[i] = min(255, int(channels[first + channel] / 257 + step))
                i += 1
    return QImage(bytes(out), w, h, w * 3, QImage.Format.Format_RGB888).copy()


def framed(window: QImage, size: tuple[int, int] = PREVIEW) -> QImage:
    """The window with round corners and a shadow, in the middle of the backdrop."""
    room = (size[0] - 2 * MARGIN, size[1] - 2 * MARGIN)
    scale = min(room[0] / window.width(), room[1] / window.height(), 1)
    shown = window.scaled(
        round(window.width() * scale),
        round(window.height() * scale),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    rounded = QImage(shown.size(), QImage.Format.Format_ARGB32_Premultiplied)
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(rounded.rect()), RADIUS, RADIUS)
    painter.setClipPath(path)
    painter.drawImage(0, 0, shown)
    # A faint light outline, as dark-mode windows have. Without it, the edges fade into the
    # dark corner of the backdrop.
    painter.setClipping(False)
    painter.setPen(QColor(255, 255, 255, 36))
    painter.drawRoundedRect(QRectF(rounded.rect()).adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
    painter.end()

    scene = QGraphicsScene(0, 0, *size)
    scene.addPixmap(QPixmap.fromImage(backdrop(size)))
    item = scene.addPixmap(QPixmap.fromImage(rounded))
    item.setPos(QPointF((size[0] - shown.width()) / 2, (size[1] - shown.height()) / 2))
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(48)
    shadow.setOffset(0, 14)
    shadow.setColor(QColor(0, 0, 0, 140))
    item.setGraphicsEffect(shadow)
    out = QImage(*size, QImage.Format.Format_RGB32)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(painter, QRectF(out.rect()), scene.sceneRect())
    painter.end()
    return out


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
        rates.RatesService.refresh = lambda self: None  # keep the bundled snapshot
        write_gif(record(folder / "gif"), GIF)
        print(GIF)
        for shot in SHOTS:
            image = framed(screenshot(folder / Path(shot.file).stem, shot), shot.picture)
            image.save(str(DOCS / shot.file))
            print(DOCS / shot.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
