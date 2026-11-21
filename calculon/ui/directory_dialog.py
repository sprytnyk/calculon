"""Asks where to keep sheets, on first start or when the saved directory doesn't work."""

import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..settings import Settings, default_sheets_dir
from ..storage import SheetStore
from ..translations import tr
from . import icons
from . import theme as themes
from .settings_dialog import Card, stylesheet
from .theme import GLACIER_DARK


def directory_error(language: str, directory: str, exc: OSError) -> str:
    """Why directory can't hold sheets, and what to do about it."""
    # strerror leaves out the path of the test file that failed to write
    text = tr(language, "directory_blocked", directory=directory, error=exc.strerror or exc)
    advice = "directory_blocked_windows" if sys.platform == "win32" else "directory_pick_another"
    return f"{text}\n\n{tr(language, advice)}"


def check_directory(language: str, directory: str) -> str:
    """Empty if sheets can go in directory, otherwise the reason they can't."""
    try:
        SheetStore(Path(directory).expanduser())
    except OSError as exc:
        return directory_error(language, directory, exc)
    return ""


class DirectoryDialog(QDialog):
    """Stays open until the directory in the box can be created and written to."""

    def __init__(self, directory: str, error: str, language: str) -> None:
        super().__init__()
        self.language = language
        self.setObjectName("settings")  # the Settings window's look
        self.setWindowTitle(self.t("app_name"))
        self.setMinimumWidth(640)

        heading = QLabel(self.t("directory_question"))
        heading.setObjectName("pageTitle")
        heading.setWordWrap(True)
        font = QFont(heading.font())
        font.setPointSizeF(font.pointSizeF() * 1.3)
        font.setWeight(QFont.Weight.DemiBold)
        heading.setFont(font)
        self.icon = QLabel()
        self.icon.setPixmap(icons.icon("directory").pixmap(QSize(40, 40)))
        title = QHBoxLayout()
        title.setSpacing(14)
        title.addWidget(self.icon)
        title.addWidget(heading, 1)

        self.directory = QLineEdit(directory)
        browse = QPushButton(self.t("browse").rstrip("…").rstrip("."))
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.directory, 1)
        row.addWidget(browse)
        card = Card()
        card.add(self.t("sheets_dir"), row, self.t("hint_sheets_dir"))

        self.error = QLabel(error)
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.setVisible(bool(error))

        page = QWidget()
        page.setObjectName("page")
        box = QVBoxLayout(page)
        box.setContentsMargins(28, 22, 28, 22)
        box.setSpacing(14)
        box.addLayout(title)
        box.addWidget(card)
        box.addWidget(self.error)
        box.addStretch()

        self.quit_button = QPushButton(self.t("quit"))
        self.quit_button.clicked.connect(self.reject)
        self.use_button = QPushButton(self.t("directory_use"))
        self.use_button.setObjectName("primary")
        self.use_button.clicked.connect(self.try_directory)
        footer = QFrame()
        footer.setObjectName("footer")
        buttons = QHBoxLayout(footer)
        buttons.setContentsMargins(16, 12, 16, 12)
        buttons.setSpacing(10)
        buttons.addStretch()
        buttons.addWidget(self.quit_button)
        buttons.addWidget(self.use_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page, 1)
        layout.addWidget(footer)
        self.use_button.setDefault(True)  # only sticks once the button is in the dialog
        # Apply the selectors once every child has its final parent and object name.
        self.setStyleSheet(
            stylesheet(GLACIER_DARK)
            + f"""
            QLabel#error {{ color: {GLACIER_DARK.error}; background: {GLACIER_DARK.surface};
                border: 1px solid {GLACIER_DARK.error}; border-radius: 8px; padding: 8px 10px; }}
            """
        )

    def t(self, key: str, **kw) -> str:
        return tr(self.language, key, **kw)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._fit_height()

    def _fit_height(self) -> None:
        """Grow tall enough for the wrapped error text. Qt sizes a window once, so a
        message shown later would otherwise be cut off."""
        layout = self.layout()
        layout.activate()
        needed = layout.totalHeightForWidth(self.width())
        if needed > self.height():
            self.resize(self.width(), needed)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.t("sheets_dir"), self.directory.text())
        if path:
            self.directory.setText(path)

    def try_directory(self) -> None:
        directory = self.directory.text().strip()
        if not directory:
            return
        error = check_directory(self.language, directory)
        if error:
            self.error.setText(error)
            self.error.show()
            self._fit_height()
            return
        self.accept()


def choose_sheets_directory() -> Settings | None:
    """Return settings whose sheets directory works. Ask for a directory on first start, or when
    the saved one can't be written to. Return None if the user quits."""
    s = Settings.load()
    error = check_directory(s.language, s.sheets_dir) if s.sheets_dir else ""
    if s.sheets_dir and not error:
        return s
    app = QApplication.instance()
    if isinstance(app, QApplication):
        themes.apply(app, GLACIER_DARK)  # the main window isn't open yet to do it
    dialog = DirectoryDialog(s.sheets_dir or default_sheets_dir(), error, s.language)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    s.sheets_dir = dialog.directory.text().strip()
    s.save()
    return s
