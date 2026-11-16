"""Folder-dialog colours as painted, including repeated theme changes."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel

from calculon.ui import theme as themes
from calculon.ui.folder_dialog import FolderDialog
from calculon.ui.theme import GLACIER_DARK, PALETTES


def assert_error_colour(label: QLabel, colour: str) -> None:
    image = label.grab().toImage()
    # Exclude the border: it has the same colour but does not prove the text does.
    inset = round(2 * image.devicePixelRatio())
    expected = QColor(colour)
    assert any(
        image.pixelColor(x, y) == expected
        for y in range(inset, image.height() - inset)
        for x in range(inset, image.width() - inset)
    ), (
        f"error text was not painted with {colour}; "
        f"palette={label.palette().color(QPalette.ColorRole.WindowText).name()}"
    )


@pytest.mark.parametrize("initial_error", ["", "This folder cannot be written to."])
def test_error_colours_survive_alternating_dialogs(app, tmp_path, initial_error) -> None:
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("")
    try:
        for theme in (*PALETTES["glacier"], *PALETTES["ember"]) * 4:
            themes.apply(app, theme)
            dialog = FolderDialog(str(blocker / "Calculon"), initial_error, "en", theme)
            try:
                dialog.show()
                app.processEvents()
                if initial_error:
                    assert dialog.error.isVisible()
                    assert_error_colour(dialog.error, theme.error)
                else:
                    assert dialog.error.isHidden()
                dialog.try_folder()
                assert dialog.error.isVisible()
                assert_error_colour(dialog.error, theme.error)
            finally:
                dialog.close()
                dialog.deleteLater()
                QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
    finally:
        themes.apply(app, GLACIER_DARK)
