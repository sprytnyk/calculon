"""Help → About: the version, the credits, and a check for a newer release, like Chrome's."""

import math

from PySide6.QtCore import QElapsedTimer, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QHideEvent, QPainter, QPaintEvent, QPen, QPixmap, QShowEvent
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, net
from ..updates import LATEST_URL, MAX_BYTES, Newer, Result, read_latest
from .theme import Theme

TURN_MS = 1568  # one full turn of the whole arc
CYCLE_MS = 1333  # the arc grows, then shrinks, once per cycle
GROW = 250  # degrees the arc grows by
SHORTEST = 20  # degrees the arc never shrinks below


def _ease(x: float) -> float:
    return x * x * (3 - 2 * x)


class Spinner(QWidget):
    """A circle that turns while its arc grows and shrinks, like Chrome's spinner."""

    def __init__(self, colour: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.colour = QColor(colour)
        self.setFixedSize(18, 18)
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        self._clock.start()
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        ms = self._clock.elapsed() if self._clock.isValid() else 0
        cycle, phase = divmod(ms / CYCLE_MS, 1)
        head = _ease(min(phase * 2, 1)) * GROW
        tail = _ease(max(phase * 2 - 1, 0)) * GROW
        start = ms / TURN_MS * 360 + tail + cycle * GROW
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = 2.0
        pen = QPen(self.colour, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        box = QRectF(self.rect()).adjusted(width, width, -width, -width)
        # Qt counts angles anticlockwise in 1/16 degree; Chrome's spinner turns clockwise
        p.drawArc(box, -math.floor(start * 16), -math.floor((head - tail + SHORTEST) * 16))


class AboutDialog(QDialog):
    def __init__(self, tr, theme: Theme, icon: QPixmap, parent: QWidget | None = None):
        super().__init__(parent)
        self.t = tr
        self.theme = theme
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # drops a check still running
        self.setWindowTitle(tr("about"))

        picture = QLabel()
        picture.setPixmap(icon)
        picture.setAlignment(Qt.AlignmentFlag.AlignTop)
        text = QLabel(tr("about_text", version=__version__))
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setOpenExternalLinks(True)

        self.spinner = Spinner(theme.accent)
        self.status = QLabel(tr("update_checking"))
        self.status.setTextFormat(Qt.TextFormat.RichText)
        self.status.setOpenExternalLinks(True)
        status_row = QHBoxLayout()
        status_row.addWidget(self.spinner)
        status_row.addWidget(self.status, 1)

        right = QVBoxLayout()
        right.addWidget(text)
        right.addLayout(status_row)
        top = QHBoxLayout()
        top.addWidget(picture)
        top.addLayout(right, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(buttons)

        self._net = QNetworkAccessManager(self)
        self.check()

    def check(self) -> None:
        reply = self._net.get(net.request(LATEST_URL))
        reply.finished.connect(lambda: self.finished_check(reply))

    def finished_check(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.show_result("failed")
        else:
            self.show_result(read_latest(bytes(reply.read(MAX_BYTES).data()), __version__))

    def show_result(self, result: Result) -> None:
        self.spinner.hide()
        self.status.setStyleSheet("")
        if isinstance(result, Newer):
            self.status.setText(self.t("update_newer", version=result.version, url=result.url))
        elif result == "up_to_date":
            self.status.setText(self.t("update_none"))
            self.status.setStyleSheet(f"color: {self.theme.accent};")
        else:
            self.status.setText(self.t("update_failed"))
