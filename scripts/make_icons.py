"""Make assets/icon.png, icon.ico and icon.icns from assets/icon-source.png.

The source is the Calculon head cut from the seeklogo vector (see
assets/ICON-LICENSE.txt). If it is missing, the original robot artwork in
assets/robot-icon.svg is rendered instead.

Run with: QT_QPA_PLATFORM=offscreen uv run python scripts/make_icons.py
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
# macOS icon types that hold PNG data, and their sizes in pixels
ICNS_TYPES = [
    (b"icp4", 16),
    (b"icp5", 32),
    (b"ic11", 32),  # 16 on Retina
    (b"ic12", 64),  # 32 on Retina
    (b"ic07", 128),
    (b"ic13", 256),  # 128 on Retina
    (b"ic08", 256),
    (b"ic14", 512),  # 256 on Retina
    (b"ic09", 512),
    (b"ic10", 1024),  # 512 on Retina
]


def render(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(data.data())


def write_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for size, png in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    path.write_bytes(header + entries + b"".join(png for _, png in images))


def write_icns(path: Path, png_for_size) -> None:
    entries = b""
    for kind, size in ICNS_TYPES:
        png = png_for_size(size)
        entries += kind + struct.pack(">I", 8 + len(png)) + png
    path.write_bytes(b"icns" + struct.pack(">I", 8 + len(entries)) + entries)


def scaled(image: QImage, size: int) -> bytes:
    small = image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    small.save(buf, "PNG")
    return bytes(data.data())


def main() -> int:
    QGuiApplication(sys.argv)
    source = ASSETS / "icon-source.png"
    if source.exists():
        image = QImage(str(source)).convertToFormat(QImage.Format.Format_ARGB32)
        if image.isNull():
            print("icon-source.png did not load", file=sys.stderr)
            return 1
        biggest = min(image.width(), 512)
        (ASSETS / "icon.png").write_bytes(scaled(image, biggest))
        sizes = [s for s in ICO_SIZES if s <= image.width()]
        write_ico(ASSETS / "icon.ico", [(s, scaled(image, s)) for s in sizes])
        write_icns(ASSETS / "icon.icns", lambda s: scaled(image, s))
        return 0
    renderer = QSvgRenderer(str(ASSETS / "robot-icon.svg"))
    if not renderer.isValid():
        print("robot-icon.svg did not load", file=sys.stderr)
        return 1
    (ASSETS / "icon.png").write_bytes(render(renderer, 512))
    write_ico(ASSETS / "icon.ico", [(s, render(renderer, s)) for s in ICO_SIZES])
    write_icns(ASSETS / "icon.icns", lambda s: render(renderer, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
