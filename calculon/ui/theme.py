"""Dark and light themes."""

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QProxyStyle,
    QStyle,
    QStyledItemDelegate,
    QStyleFactory,
)

from . import icons


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    sidebar: str
    surface: str
    border: str
    text: str
    muted: str
    accent: str
    focus: str  # border of the field being typed in
    selection: str
    current_line: str
    result: str
    result_hover: str
    number: str
    unit: str
    variable: str
    keyword: str
    operator: str
    comment: str
    heading: str
    label: str
    tag: str

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


DARK = Theme(
    name="dark",
    bg="#1a1b20",
    sidebar="#212228",
    surface="#2a2b33",
    border="#30323a",
    text="#e3e4e8",
    muted="#7d808c",
    accent="#f0a35e",
    focus="#6cb6ff",
    selection="#3b3f4f",
    current_line="#202128",
    result="#8fd6a4",
    result_hover="#c4f0d0",
    number="#f2c46d",
    unit="#79c3e6",
    variable="#c49cf2",
    keyword="#93a5c6",
    operator="#a3a7b1",
    comment="#5d6170",
    heading="#ffffff",
    label="#cfd1d8",
    tag="#6fcf97",
)

LIGHT = Theme(
    name="light",
    bg="#fbfbf9",
    sidebar="#f1f1ee",
    surface="#ffffff",
    border="#dddcd7",
    text="#24262b",
    muted="#8a8d95",
    accent="#c2410c",
    focus="#2563eb",
    selection="#cfe0f5",
    current_line="#f4f4f1",
    result="#15803d",
    result_hover="#0b5a29",
    number="#a85b06",
    unit="#0369a1",
    variable="#7c3aed",
    keyword="#4b5a70",
    operator="#6b7280",
    comment="#a3a7ae",
    heading="#111827",
    label="#374151",
    tag="#15803d",
)


# icon colours: bright shades on dark, deeper ones on light
ICONS_DARK = {
    "neutral": "#a3a7b1", "blue": "#6cb6ff", "amber": "#f2b35e", "violet": "#b794f6",
    "green": "#68d391", "teal": "#4fd1c5", "cyan": "#63c5ea", "rose": "#ff7b93",
    "red": "#ff6b6b", "yellow": "#f6d365", "indigo": "#8c9eff",
}  # fmt: skip
ICONS_LIGHT = {
    "neutral": "#64748b", "blue": "#2563eb", "amber": "#d97706", "violet": "#7c3aed",
    "green": "#16a34a", "teal": "#0d9488", "cyan": "#0891b2", "rose": "#e11d48",
    "red": "#dc2626", "yellow": "#ca8a04", "indigo": "#4f46e5",
}  # fmt: skip
UI_FONT_SCALE = 1.15  # menus, sidebar and dialogs a bit larger than the system default
_base_font: list[QFont] = []
_style: list[QStyle] = []


class _Style(QProxyStyle):
    """Fusion with larger icons in menus and lists, and plain dialog buttons."""

    def pixelMetric(self, metric, option=None, widget=None) -> int:  # noqa: N802
        if metric == QStyle.PixelMetric.PM_SmallIconSize:
            return icons.ICON_SIZE
        return super().pixelMetric(metric, option, widget)

    def styleHint(self, hint, option=None, widget=None, data=None) -> int:  # noqa: N802
        # no stock icons (red cross, green tick) on OK, Cancel, Yes, No, Close
        if hint == QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons:
            return 0
        return super().styleHint(hint, option, widget, data)


def system_is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    return hints.colorScheme() == Qt.ColorScheme.Dark


def resolve(setting: str) -> Theme:
    if setting == "light":
        return LIGHT
    if setting == "system":
        return DARK if system_is_dark() else LIGHT
    return DARK


def apply(app: QApplication, theme: Theme) -> None:
    icons.set_palette(ICONS_DARK if theme.is_dark else ICONS_LIGHT)
    if not _style:
        _style.append(_Style(QStyleFactory.create("Fusion")))
        app.setStyle(_style[0])
    if not _base_font:
        _base_font.append(QFont(app.font()))
        font = QFont(_base_font[0])
        font.setPointSizeF(max(10.5, font.pointSizeF() * UI_FONT_SCALE))
        app.setFont(font)
    p = QPalette()
    c = QColor
    p.setColor(QPalette.ColorRole.Window, c(theme.sidebar))
    p.setColor(QPalette.ColorRole.WindowText, c(theme.text))
    p.setColor(QPalette.ColorRole.Base, c(theme.bg))
    p.setColor(QPalette.ColorRole.AlternateBase, c(theme.surface))
    p.setColor(QPalette.ColorRole.Text, c(theme.text))
    p.setColor(QPalette.ColorRole.PlaceholderText, c(theme.muted))
    p.setColor(QPalette.ColorRole.Button, c(theme.surface))
    p.setColor(QPalette.ColorRole.ButtonText, c(theme.text))
    p.setColor(QPalette.ColorRole.ToolTipBase, c(theme.surface))
    p.setColor(QPalette.ColorRole.ToolTipText, c(theme.text))
    p.setColor(QPalette.ColorRole.Highlight, c(theme.selection))
    p.setColor(QPalette.ColorRole.HighlightedText, c(theme.text))
    p.setColor(QPalette.ColorRole.Link, c(theme.accent))
    p.setColor(QPalette.ColorRole.BrightText, c(theme.accent))
    p.setColor(QPalette.ColorRole.Mid, c(theme.border))
    p.setColor(QPalette.ColorRole.Midlight, c(theme.border))
    p.setColor(QPalette.ColorRole.Dark, c(theme.border))
    p.setColor(QPalette.ColorRole.Light, c(theme.surface))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, c(theme.muted))
    app.setPalette(p)
    app.setStyleSheet(
        f"""
        QMainWindow::separator {{ background: {theme.border}; width: 1px; }}
        QSplitter::handle {{ background: {theme.border}; }}
        QStatusBar {{ background: {theme.sidebar}; color: {theme.muted};
                      border-top: 1px solid {theme.border}; }}
        QStatusBar QLabel {{ color: {theme.muted}; padding: 0 6px; }}
        QStatusBar QLabel#total {{ color: {theme.result}; font-weight: 600; }}
        QTreeWidget {{ background: {theme.sidebar}; border: none; outline: 0;
                       show-decoration-selected: 0; }}
        QTreeWidget::item {{ padding: 4px 2px; }}
        QTreeWidget#sheetTree::item:selected, QTreeWidget#sheetTree::item:hover {{
            background: transparent; color: {theme.text}; }}
        QTreeWidget:!focus::item:selected {{ color: {theme.text}; }}
        QLineEdit#search {{ background: {theme.bg}; border: 1px solid {theme.border};
                            border-radius: 6px; padding: 4px 8px; }}
        QLineEdit#search:focus {{ border-color: {theme.focus}; }}
        QPlainTextEdit {{ border: none; selection-background-color: {theme.selection}; }}
        QToolButton#sidebarButton {{ border: none; padding: 4px 6px; border-radius: 4px;
                                     color: {theme.muted}; }}
        QToolButton#sidebarButton:hover {{ background: {theme.surface}; color: {theme.text}; }}
        QLabel#banner {{ background: {theme.surface}; color: {theme.muted}; padding: 6px 12px;
                         border-bottom: 1px solid {theme.border}; }}
        QMenu {{ background: {theme.surface}; border: 1px solid {theme.border}; padding: 4px; }}
        QMenu::item {{ padding: 6px 28px 6px 8px; border-radius: 5px; }}
        QMenu::item:selected {{ background: {theme.selection}; }}
        QMenu::icon {{ padding-left: 6px; }}
        QMenu::separator {{ height: 1px; background: {theme.border}; margin: 4px 8px; }}
        QMenuBar {{ background: {theme.sidebar}; border: none; padding: 2px 4px; }}
        QMenuBar::item {{ background: transparent; color: {theme.text}; padding: 4px 10px;
                          margin: 1px 1px; border: none; border-radius: 6px; }}
        QMenuBar::item:selected {{ background: {theme.surface}; }}
        QMenuBar::item:pressed {{ background: {theme.selection}; }}
        QToolTip {{ background: {theme.surface}; color: {theme.text};
                    border: 1px solid {theme.border}; }}
        """
        + controls_stylesheet(theme)
    )
    install_input_margins(app)


def controls_stylesheet(t: Theme) -> str:
    """Text fields, dropdowns, number fields and buttons everywhere in the app."""
    on_focus = "#10131a" if t.is_dark else "#ffffff"
    down = icons.icon_file("caret_down", t.muted)
    up = icons.icon_file("caret_up", t.muted)
    return f"""
    QLineEdit, QComboBox, QAbstractSpinBox {{
        background: {t.bg}; color: {t.text}; border: 1px solid {t.border};
        border-radius: 6px; padding: 5px 10px; min-height: 22px;
        selection-background-color: {t.selection}; selection-color: {t.text}; }}
    QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover {{ border-color: {t.muted}; }}
    QLineEdit:focus, QComboBox:focus, QComboBox:on, QAbstractSpinBox:focus {{
        border-color: {t.focus}; }}
    QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{ color: {t.muted}; }}
    QComboBox QLineEdit, QAbstractSpinBox QLineEdit {{
        border: none; background: transparent; padding: 0; min-height: 0; }}
    QComboBox {{ combobox-popup: 0; }}
    QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right;
        width: 28px; border: none; background: transparent; }}
    QComboBox::down-arrow {{ image: url("{down}"); width: 12px; height: 12px; }}
    QComboBox::down-arrow:on {{ image: url("{up}"); }}
    QComboBox QAbstractItemView {{
        background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
        padding: 4px; outline: 0; }}
    QComboBox QAbstractItemView::item {{ padding: 6px 10px; min-height: 22px;
        border-radius: 6px; }}
    QComboBox QAbstractItemView::item:selected,
    QComboBox QAbstractItemView::item:hover {{ background: {t.selection}; color: {t.text}; }}
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
        subcontrol-origin: border; width: 24px; border: none; background: transparent; }}
    QAbstractSpinBox::up-button {{ subcontrol-position: top right;
        border-top-right-radius: 6px; }}
    QAbstractSpinBox::down-button {{ subcontrol-position: bottom right;
        border-bottom-right-radius: 6px; }}
    QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
        background: {t.surface}; }}
    QAbstractSpinBox::up-arrow {{ image: url("{up}"); width: 10px; height: 10px; }}
    QAbstractSpinBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}
    QPushButton {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
        border-radius: 7px; padding: 7px 18px; min-width: 64px; }}
    QPushButton:hover {{ border-color: {t.muted}; }}
    QPushButton:pressed {{ background: {t.selection}; }}
    QPushButton:focus {{ border-color: {t.focus}; }}
    QPushButton#primary {{ background: {t.focus}; border-color: {t.focus};
        color: {on_focus}; font-weight: 600; }}
    QPushButton#primary:hover {{ border-color: {t.text}; }}
    """


class _InputMargins(QObject):
    """Spin boxes keep their text off the left border, and dropdown rows get padding.

    A spin box's text sits in an inner field that the stylesheet padding doesn't reach,
    so the margin goes on that field directly when the widget is first shown.
    """

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(obj, QAbstractSpinBox):
            edit = obj.findChild(QLineEdit)
            if edit is not None and edit.textMargins().left() == 0:
                edit.setTextMargins(10, 0, 0, 0)
        if (
            event.type() == QEvent.Type.Show
            and isinstance(obj, QComboBox)
            and not isinstance(obj.itemDelegate(), QStyledItemDelegate)
        ):
            obj.setItemDelegate(QStyledItemDelegate(obj))  # lets ::item padding apply
        return False


_filters: list[QObject] = []


def install_input_margins(app: QApplication) -> None:
    if not _filters:
        _filters.append(_InputMargins(app))
        app.installEventFilter(_filters[0])
