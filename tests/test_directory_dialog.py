"""Directory-dialog colours as painted."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel

from calculon.ui import theme as themes
from calculon.ui.directory_dialog import DirectoryDialog
from calculon.ui.theme import GLACIER_DARK


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


@pytest.mark.parametrize("initial_error", ["", "This directory cannot be written to."])
def test_error_colour_in_startup_dialog(app, tmp_path, initial_error) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    try:
        themes.apply(app, GLACIER_DARK)
        dialog = DirectoryDialog(str(blocker / "Calculon"), initial_error, "en")
        try:
            dialog.show()
            app.processEvents()
            if initial_error:
                assert dialog.error.isVisible()
                assert_error_colour(dialog.error, GLACIER_DARK.error)
            else:
                assert dialog.error.isHidden()
            dialog.try_directory()
            assert dialog.error.isVisible()
            assert_error_colour(dialog.error, GLACIER_DARK.error)
        finally:
            dialog.close()
            dialog.deleteLater()
            QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
    finally:
        themes.apply(app, GLACIER_DARK)
