"""Settings window: pages on the left, grouped cards on the right."""

import html
from dataclasses import replace

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..engine import RatesError, RateTable
from ..engine.currency import KNOWN_CODES
from ..settings import Settings
from ..spelling import Status, platform_key, probe
from ..translations import LANGUAGES
from . import icons
from .theme import DARK, PALETTES, Theme

NUMBER_STYLES = [
    ("auto", ""),
    ("comma_dot", "1,234.56"),
    ("dot_comma", "1.234,56"),
    ("space_comma", "1 234,56"),
    ("space_dot", "1 234.56"),
]


def _label(text: str) -> str:
    """Labels sit in their own column, so the trailing colons go."""
    return text.rstrip().rstrip(":")


def stylesheet(t: Theme) -> str:
    return f"""
    QDialog#settings {{ background: {t.sidebar}; }}
    QListWidget#nav {{ background: transparent; border: none; outline: 0; }}
    QListWidget#nav::item {{ padding: 8px 10px; margin: 1px 0; border-radius: 7px;
                             color: {t.text}; }}
    QListWidget#nav::item:selected {{ background: {t.selection}; }}
    QListWidget#nav::item:hover:!selected {{ background: {t.surface}; }}
    QWidget#page {{ background: {t.bg}; }}
    QScrollArea#pageScroll {{ background: {t.bg}; border: none;
                              border-left: 1px solid {t.border}; }}
    QLabel#pageTitle {{ color: {t.heading}; }}
    QLabel#cardTitle {{ color: {t.muted}; font-weight: 600; }}
    QFrame#card {{ background: {t.sidebar}; border: 1px solid {t.border};
                   border-radius: 10px; }}
    QFrame#card QLabel {{ background: transparent; }}
    QLabel#hint {{ color: {t.muted}; }}
    QLabel#code {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
                   border-radius: 6px; padding: 8px 10px; }}
    QLabel#testResult {{ color: {t.muted}; }}
    QLabel#ligatureSample {{ color: {t.operator}; background: {t.bg};
        border: 1px solid {t.border}; border-radius: 6px; padding: 3px 10px; }}
    QFrame#footer {{ background: {t.sidebar}; border-top: 1px solid {t.border}; }}
    """


def spell_hint(status: Status, tr) -> str:
    """What spell check uses here, or what it still needs."""

    def names(langs) -> str:
        return ", ".join(tr(f"spell_lang_{lang}") for lang in langs)

    if not status.supported:
        return tr("hint_spell_other")
    if not status.library:
        if platform_key() == "darwin":
            return tr("hint_spell_macos")
        return tr("hint_spell_linux", command=status.install_command())
    parts = []
    if status.dictionaries:
        parts.append(tr("hint_spell_ok", languages=names(status.dictionaries)))
    if status.missing:
        if platform_key() == "darwin":
            parts.append(tr("hint_spell_macos"))
        else:
            command = status.install_command()
            parts.append(tr("hint_spell_missing", languages=names(status.missing), command=command))
    return " ".join(parts)


class Card(QFrame):
    """A rounded group of rows: a label on the left, a control on the right, a hint below."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(16, 14, 16, 14)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(10)
        self.grid.setColumnStretch(1, 1)
        self._row = 0

    def add(self, label: str, control: QWidget | QHBoxLayout, hint: str = "") -> None:
        if label:
            lab = QLabel(_label(label))
            self.grid.addWidget(lab, self._row, 0, Qt.AlignmentFlag.AlignVCenter)
        if isinstance(control, QHBoxLayout):
            self.grid.addLayout(control, self._row, 1 if label else 0, 1, 1 if label else 2)
        else:
            self.grid.addWidget(control, self._row, 1 if label else 0, 1, 1 if label else 2)
        self._row += 1
        if hint:
            h = QLabel(hint)
            h.setObjectName("hint")
            h.setWordWrap(True)
            self.grid.addWidget(h, self._row, 1 if label else 0, 1, 1 if label else 2)
            self._row += 1


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, tr, parent: QWidget | None = None):
        super().__init__(parent)
        self.t = tr
        self.original = settings
        theme: Theme = getattr(parent, "theme", DARK)
        self.setObjectName("settings")
        self.setWindowTitle(tr("settings_title"))
        self.setWindowIcon(icons.icon("settings"))
        self.setStyleSheet(stylesheet(theme))
        self.resize(800, 620)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setIconSize(QSize(icons.ICON_SIZE, icons.ICON_SIZE))
        self.nav.setFixedWidth(200)
        self.pages = QStackedWidget()

        self._add_page("settings", tr("tab_general"), self._general(settings))
        self._add_page("numbers", tr("tab_numbers"), self._numbers(settings))
        self._add_page("rates", tr("tab_rates"), self._rates(settings))
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        side = QVBoxLayout()
        side.setContentsMargins(12, 16, 12, 12)
        side.addWidget(self.nav)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addLayout(side)
        body.addWidget(self.pages, 1)

        cancel = QPushButton(_label(tr("cancel")))
        cancel.clicked.connect(self.reject)
        ok = QPushButton(_label(tr("save")))
        ok.setObjectName("primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        footer = QFrame()
        footer.setObjectName("footer")
        row = QHBoxLayout(footer)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(10)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(ok)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(body, 1)
        layout.addWidget(footer)
        self._net = QNetworkAccessManager(self)

    def _add_page(self, icon_name: str, title: str, cards: list[tuple[str, QWidget]]) -> None:
        item = QListWidgetItem(icons.icon(icon_name), title)
        self.nav.addItem(item)
        page = QWidget()
        page.setObjectName("page")
        box = QVBoxLayout(page)
        box.setContentsMargins(28, 22, 28, 22)
        box.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        font = QFont(heading.font())
        font.setPointSizeF(font.pointSizeF() * 1.45)
        font.setWeight(QFont.Weight.DemiBold)
        heading.setFont(font)
        box.addWidget(heading)
        for name, card in cards:
            box.addSpacing(10)
            if name:
                label = QLabel(name.upper())
                label.setObjectName("cardTitle")
                small = QFont(label.font())
                small.setPointSizeF(small.pointSizeF() * 0.82)
                small.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
                label.setFont(small)
                box.addWidget(label)
            box.addWidget(card)
        box.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)

    def _general(self, s: Settings) -> list[tuple[str, QWidget]]:
        tr = self.t
        sheets = Card()
        self.sheets_dir = QLineEdit(s.sheets_dir)
        browse = QPushButton(_label(tr("browse")).rstrip("…").rstrip("."))
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.sheets_dir, 1)
        row.addWidget(browse)
        sheets.add(tr("sheets_dir"), row, tr("hint_sheets_dir"))

        look = Card()
        self.colours = QComboBox()
        for key in PALETTES:
            self.colours.addItem(tr(f"colours_{key}"), key)
        self.colours.setCurrentIndex(max(0, self.colours.findData(s.colours)))
        look.add(tr("colours"), self.colours)
        self.theme = QComboBox()
        for key in ("dark", "light", "system"):
            self.theme.addItem(icons.icon(f"theme_{key}"), tr(f"theme_{key}"), key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(s.theme)))
        look.add(tr("theme"), self.theme)
        self.language = QComboBox()
        for key, name in LANGUAGES.items():
            self.language.addItem(name, key)
        self.language.setCurrentIndex(max(0, self.language.findData(s.language)))
        look.add(tr("language"), self.language)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 40)
        self.font_size.setValue(s.font_size)
        self.font_size.setSuffix(" pt")
        look.add(tr("font_size"), self.font_size)
        self.ligatures = QCheckBox(tr("ligatures"))
        self.ligatures.setChecked(s.ligatures)
        # the example in the editor's font, ligatures on, so it shows what you get: ⇒ ≠ ≤ →
        sample = QLabel("=>  !=  <=  ->  >=")
        sample.setObjectName("ligatureSample")
        font = QFont(getattr(self.parent(), "font_family", "Fira Code"))
        font.setPointSizeF(sample.font().pointSizeF() * 1.1)
        sample.setFont(font)

        def show_ligatures(on: bool) -> None:
            f = QFont(sample.font())
            if on:
                f.unsetFeature(QFont.Tag("calt"))
            else:
                f.setFeature(QFont.Tag("calt"), 0)
            sample.setFont(f)

        self.ligatures.toggled.connect(show_ligatures)
        show_ligatures(s.ligatures)
        self.ligature_sample = sample
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self.ligatures)
        row.addWidget(sample)
        row.addStretch()
        look.add("", row)

        spelling = Card()
        status = getattr(self.parent(), "spell_status", None) or probe()
        self.spell_check = QCheckBox(tr("spell_check"))
        self.spell_check.setChecked(s.spell_check and status.available)
        self.spell_check.setEnabled(status.available)
        spelling.add("", self.spell_check)
        self.spell_hint = QLabel(spell_hint(status, tr))
        self.spell_hint.setObjectName("hint")
        self.spell_hint.setWordWrap(True)
        self.spell_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        spelling.add("", self.spell_hint)
        return [
            (tr("section_sheets"), sheets),
            (tr("section_appearance"), look),
            (tr("section_spelling"), spelling),
        ]

    def _numbers(self, s: Settings) -> list[tuple[str, QWidget]]:
        tr = self.t
        fmt = Card()
        self.number_style = QComboBox()
        for key, sample in NUMBER_STYLES:
            self.number_style.addItem(sample or tr("number_style_auto"), key)
        self.number_style.setCurrentIndex(max(0, self.number_style.findData(s.number_style)))
        fmt.add(tr("number_style"), self.number_style)
        self.date_order = QComboBox()
        self.date_order.addItem(tr("dmy"), "DMY")
        self.date_order.addItem(tr("mdy"), "MDY")
        self.date_order.setCurrentIndex(max(0, self.date_order.findData(s.date_order)))
        fmt.add(tr("date_order"), self.date_order)
        self.dollar = QComboBox()
        for code in ("USD", "CAD", "AUD", "NZD", "SGD", "HKD", "MXN", "TWD"):
            self.dollar.addItem(code, code)
        self.dollar.setEditable(True)
        self.dollar.setCurrentText(s.dollar)
        fmt.add(tr("dollar"), self.dollar, tr("hint_dollar"))

        decimals = Card()
        self.max_decimals = QSpinBox()
        self.max_decimals.setRange(0, 20)
        self.max_decimals.setValue(s.max_decimals)
        decimals.add(tr("max_decimals"), self.max_decimals)
        self.money_decimals = QSpinBox()
        self.money_decimals.setRange(0, 10)
        self.money_decimals.setValue(s.money_decimals)
        decimals.add(tr("money_decimals"), self.money_decimals, tr("hint_decimals"))
        return [(tr("section_format"), fmt), (tr("section_decimals"), decimals)]

    def _rates(self, s: Settings) -> list[tuple[str, QWidget]]:
        tr = self.t
        source = Card()
        self.rates_url = QLineEdit(s.rates_url)
        self.rates_url.setPlaceholderText("https://…")
        test = QPushButton(tr("test_url"))
        test.clicked.connect(self._test_url)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.rates_url, 1)
        row.addWidget(test)
        source.add(tr("rates_url"), row, tr("hint_rates_url"))
        self.test_result = QLabel()
        self.test_result.setObjectName("testResult")
        self.test_result.setWordWrap(True)
        self.test_result.hide()  # shown once a test has run
        source.add("", self.test_result)

        fmt = Card()
        help_text = QLabel(self._rates_help_html())
        help_text.setTextFormat(Qt.TextFormat.RichText)
        help_text.setWordWrap(True)
        help_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        fmt.add("", help_text)
        return [(tr("section_source"), source), (tr("section_json"), fmt)]

    def _rates_help_html(self) -> str:
        """The help text with the JSON example in a monospace block."""
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        parts = []
        for block in self.t("rates_help").split("\n\n"):
            text = html.escape(block)
            if block.lstrip().startswith("{"):
                parts.append(
                    f"<p style=\"font-family: 'Fira Code', '{mono}', monospace;\">{text}</p>"
                )
            else:
                parts.append(f"<p>{text.replace(chr(10), '<br>')}</p>")
        return "".join(parts)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.t("sheets_dir"), self.sheets_dir.text())
        if path:
            self.sheets_dir.setText(path)

    def _test_url(self) -> None:
        url = self.rates_url.text().strip()
        if not url:
            return
        self.test_result.show()
        self.test_result.setText("…")
        req = QNetworkRequest(QUrl(url))
        req.setTransferTimeout(15000)
        reply = self._net.get(req)

        def done() -> None:
            reply.deleteLater()
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.test_result.setText(self.t("test_fail", error=reply.errorString()))
                return
            try:
                table = RateTable.parse(bytes(reply.read(2_000_000).data()))
            except RatesError as exc:
                self.test_result.setText(self.t("test_fail", error=str(exc)))
                return
            self.test_result.setText(self.t("test_ok", count=len(table.rates), base=table.base))

        reply.finished.connect(done)

    def result_settings(self) -> Settings:
        dollar = self.dollar.currentText().strip().upper()
        return replace(
            self.original,
            sheets_dir=self.sheets_dir.text().strip() or self.original.sheets_dir,
            theme=self.theme.currentData(),
            colours=self.colours.currentData(),
            language=self.language.currentData(),
            font_size=self.font_size.value(),
            ligatures=self.ligatures.isChecked(),
            # a greyed-out box keeps what was saved, for when Hunspell turns up
            spell_check=(
                self.spell_check.isChecked()
                if self.spell_check.isEnabled()
                else self.original.spell_check
            ),
            number_style=self.number_style.currentData(),
            date_order=self.date_order.currentData(),
            dollar=dollar if dollar in KNOWN_CODES else self.original.dollar,
            max_decimals=self.max_decimals.value(),
            money_decimals=self.money_decimals.value(),
            rates_url=self.rates_url.text().strip(),
        )
