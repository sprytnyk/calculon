"""The sheet editor: text on the left, results in a column on the right."""

import re

from PySide6.QtCore import (
    QEasingCurve,
    QModelIndex,
    QObject,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QStandardItem,
    QStandardItemModel,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QPlainTextDocumentLayout,
    QPlainTextEdit,
    QScrollBar,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionSlider,
    QStyleOptionViewItem,
    QTextEdit,
    QWidget,
)

from ..engine import Config, FormatOptions, RateTable, SheetResult, evaluate_sheet
from ..engine import ukrainian as UK
from ..engine import units as U
from ..engine.currency import KNOWN_CODES
from ..engine.interpreter import AGGREGATES, FUNCTIONS, KEYWORDS, ROUNDERS
from .theme import Theme

WORD_RE = re.compile(r"[^\W\d_][\w]*$")
SYMBOL_RUN = re.compile(r"[-=<>!+*/|&:~.^%]{2,}")
MIN_RESULTS_WIDTH = 120
COMMENT_PREFIX = "// "
DOCUMENT_MARGIN = 14
MAX_MATCHES = 2000  # find highlights at most this many
KIND_ROLE = Qt.ItemDataRole.UserRole + 1
# autocomplete: the order kinds are listed in, and the colour each gets
KIND_ORDER = ("variable", "function", "currency", "unit", "keyword")


class Highlighter(QSyntaxHighlighter):
    def __init__(self, parent: QObject, theme: Theme):
        # parented to the editor, not a document: documents come and go with sheets
        super().__init__(parent)
        self.spans: list[list[tuple[int, int, str]]] = []
        self.set_theme(theme)

    def set_theme(self, theme: Theme) -> None:
        def fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            if italic:
                f.setFontItalic(True)
            return f

        self.formats = {
            "number": fmt(theme.number),
            "unit": fmt(theme.unit),
            "variable": fmt(theme.variable),
            "keyword": fmt(theme.keyword),
            "operator": fmt(theme.operator),
            "comment": fmt(theme.comment, italic=True),
            "heading": fmt(theme.heading, bold=True),
            "label": fmt(theme.label, bold=True),
            "tag": fmt(theme.tag),
        }

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt name
        n = self.currentBlock().blockNumber()
        if n >= len(self.spans):
            return
        spans = self.spans[n]
        for start, end, cls in spans:
            f = self.formats.get(cls)
            if f is not None and start < len(text):
                self.setFormat(start, min(end, len(text)) - start, f)
        # Font ligatures (<=, ->, >=, ===) only form when the whole run of symbols has one
        # format, so give each run outside comments the operator colour from end to end.
        comments = [(a, b) for a, b, cls in spans if cls == "comment"]
        for m in SYMBOL_RUN.finditer(text):
            if not any(a <= m.start() < b for a, b in comments):
                self.setFormat(m.start(), m.end() - m.start(), self.formats["operator"])


class ResultsArea(QWidget):
    """Painted inside the editor's right margin so it scrolls with the text."""

    copied = Signal(str)
    resized = Signal(int)

    def __init__(self, editor: SheetEdit):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)
        self.hover_block = -1
        self.flash_block = -1
        self._drag_x: int | None = None
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flash)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.editor.results_width, 0)

    def _end_flash(self) -> None:
        self.flash_block = -1
        self.update()

    def _block_at(self, y: int) -> int:
        block = self.editor.firstVisibleBlock()
        offset = self.editor.contentOffset()
        while block.isValid():
            geo = self.editor.blockBoundingGeometry(block).translated(offset)
            if geo.top() <= y < geo.bottom():
                return block.blockNumber()
            if geo.top() > y:
                break
            block = block.next()
        return -1

    def _near_edge(self, x: int) -> bool:
        return x < 6

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = int(event.position().x())
        if self._drag_x is not None:
            width = self.editor.results_width - (x - self._drag_x)
            self.editor.set_results_width(width)
            return
        self.setCursor(
            Qt.CursorShape.SplitHCursor if self._near_edge(x) else Qt.CursorShape.PointingHandCursor
        )
        n = self._block_at(int(event.position().y()))
        if n != self.hover_block:
            self.hover_block = n
            text = self.editor.result_text(n)
            self.setToolTip(text if text else "")
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.hover_block = -1
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = int(event.position().x())
        if event.button() == Qt.MouseButton.LeftButton and self._near_edge(x):
            self._drag_x = x
            return
        if event.button() == Qt.MouseButton.LeftButton:
            n = self._block_at(int(event.position().y()))
            text = self.editor.result_text(n)
            if text:
                self.flash_block = n
                self._flash_timer.start(700)
                self.copied.emit(text)
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_x is not None:
            self._drag_x = None
            self.resized.emit(self.editor.results_width)

    def paintEvent(self, event) -> None:  # noqa: N802
        ed = self.editor
        theme = ed.theme
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(theme.bg))
        painter.setPen(QColor(theme.border))
        painter.drawLine(0, 0, 0, self.height())
        result = ed.result
        if result is None:
            return
        font = QFont(ed.font())
        bold = QFont(font)
        bold.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(font)
        block = ed.firstVisibleBlock()
        offset = ed.contentOffset()
        current = ed.textCursor().blockNumber()
        pad = 12
        while block.isValid():
            geo = ed.blockBoundingGeometry(block).translated(offset)
            if geo.top() > event.rect().bottom():
                break
            n = block.blockNumber()
            if n < len(result.lines) and block.isVisible():
                line = result.lines[n]
                if line.text:
                    top = int(geo.top())
                    h = fm.height()
                    rect = QRect(pad, top, self.width() - 2 * pad, h)
                    if n == self.flash_block:
                        painter.fillRect(QRect(1, top, self.width(), h), QColor(theme.selection))
                    color = theme.result_hover if n in (self.hover_block, current) else theme.result
                    if n == self.flash_block:
                        color = theme.accent
                    painter.setPen(QColor(color))
                    painter.setFont(bold if line.is_total else font)
                    text = fm.elidedText(line.text, Qt.TextElideMode.ElideLeft, rect.width())
                    painter.drawText(
                        rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text
                    )
                    if line.is_total:
                        painter.setPen(QColor(theme.border))
                        painter.drawLine(pad, top, self.width() - pad, top)
            block = block.next()


class LineNumbers(QWidget):
    """Line numbers on the left, so "line12" is easy to find."""

    def __init__(self, editor: SheetEdit):
        super().__init__(editor)
        self.editor = editor

    def width_needed(self) -> int:
        digits = max(2, len(str(self.editor.blockCount())))
        return self.editor.fontMetrics().horizontalAdvance("9") * digits + 18

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # a click selects the whole line, like in code editors
        n = self.editor.results._block_at(int(event.position().y()))
        if n < 0:
            return
        block = self.editor.document().findBlockByNumber(n)
        cur = QTextCursor(block)
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cur)
        self.editor.setFocus()

    def paintEvent(self, event) -> None:  # noqa: N802
        ed = self.editor
        theme = ed.theme
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(theme.bg))
        font = QFont(ed.font())
        font.setPointSizeF(font.pointSizeF() * 0.85)
        painter.setFont(font)
        fm = QFontMetrics(ed.font())
        current = ed.textCursor().blockNumber()
        block = ed.firstVisibleBlock()
        offset = ed.contentOffset()
        while block.isValid():
            geo = ed.blockBoundingGeometry(block).translated(offset)
            if geo.top() > event.rect().bottom():
                break
            if block.isVisible() and geo.bottom() >= event.rect().top():
                n = block.blockNumber()
                painter.setPen(QColor(theme.text if n == current else theme.comment))
                rect = QRect(0, int(geo.top()), self.width() - 8, fm.height())
                painter.drawText(
                    rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(n + 1)
                )
            block = block.next()


class SheetScrollBar(QScrollBar):
    """A thin bar that shows while scrolling or under the mouse, then fades out.

    Find matches show as marks on it, so you can see where they are in the sheet.
    """

    HIDE_AFTER_MS = 1000

    def __init__(self, editor: SheetEdit):
        super().__init__(Qt.Orientation.Vertical, editor)
        self.setObjectName("sheetScroll")
        self.editor = editor
        self._hover = False
        self._pressed = False
        self.opacity = 0.0
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.valueChanged.connect(self._set_opacity)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(self.HIDE_AFTER_MS)
        self._hide_timer.timeout.connect(lambda: self._fade_to(0.0))
        self.valueChanged.connect(lambda _v: self.reveal())

    def _set_opacity(self, value: float) -> None:
        self.opacity = float(value)
        self.update()

    def _fade_to(self, target: float) -> None:
        if self._hover or self._pressed:
            return
        self._fade.stop()
        self._fade.setStartValue(self.opacity)
        self._fade.setEndValue(target)
        self._fade.start()

    def reveal(self) -> None:
        self._fade.stop()
        self._set_opacity(1.0)
        self._hide_timer.start()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.reveal()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._hide_timer.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._pressed = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._pressed = False
        self._hide_timer.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        theme = self.editor.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # find matches, always shown while there are any
        doc = self.editor.document()
        lines = max(1, doc.lastBlock().firstLineNumber() + doc.lastBlock().lineCount())
        color = QColor(theme.accent)
        color.setAlpha(200)
        for match in self.editor.find_matches():
            y = round(match.block().firstLineNumber() / lines * self.height())
            painter.fillRect(QRect(2, min(y, self.height() - 3), self.width() - 4, 3), color)
        if self.maximum() <= self.minimum() or self.opacity <= 0:
            return
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_ScrollBar, opt, QStyle.SubControl.SC_ScrollBarSlider, self
        )
        width = 8 if self._hover or self._pressed else 5
        rect = QRectF(self.width() - width - 2, handle.top() + 2, width, handle.height() - 4)
        color = QColor(theme.muted)
        color.setAlphaF(self.opacity * (0.9 if self._hover or self._pressed else 0.5))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, width / 2, width / 2)


class CompletionDelegate(QStyledItemDelegate):
    """A completion row: the word, with the typed part in the accent colour, and its kind."""

    def __init__(self, editor: SheetEdit):
        super().__init__(editor)
        self.editor = editor

    def _fonts(self) -> tuple[QFont, QFont]:
        font = QFont(self.editor.font())
        small = QFont(font)
        small.setPointSizeF(font.pointSizeF() * 0.8)
        return font, small

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        font, small = self._fonts()
        word = QFontMetrics(font).horizontalAdvance(index.data() or "")
        label = QFontMetrics(small).horizontalAdvance(self.editor.kind_label(index.data(KIND_ROLE)))
        return QSize(word + label + 44, QFontMetrics(font).height() + 8)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        theme = self.editor.theme
        font, small = self._fonts()
        rect = option.rect.adjusted(4, 1, -4, -1)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.selection))
            painter.drawRoundedRect(QRectF(rect), 5, 5)
        text_rect = rect.adjusted(8, 0, -8, 0)
        word = index.data() or ""
        typed = len(self.editor.completion_prefix())
        fm = QFontMetrics(font)
        align = Qt.AlignmentFlag.AlignVCenter
        painter.setFont(font)
        painter.setPen(QColor(theme.accent))
        painter.drawText(text_rect, align | Qt.AlignmentFlag.AlignLeft, word[:typed])
        painter.setPen(QColor(theme.text))
        rest = text_rect.adjusted(fm.horizontalAdvance(word[:typed]), 0, 0, 0)
        painter.drawText(rest, align | Qt.AlignmentFlag.AlignLeft, word[typed:])
        kind = index.data(KIND_ROLE)
        painter.setFont(small)
        colors = {
            "variable": theme.variable,
            "function": theme.keyword,
            "currency": theme.unit,
            "unit": theme.unit,
        }
        painter.setPen(QColor(colors.get(kind or "", theme.muted)))
        painter.drawText(
            text_rect, align | Qt.AlignmentFlag.AlignRight, self.editor.kind_label(kind)
        )
        painter.restore()


class SheetEdit(QPlainTextEdit):
    evaluated = Signal(object)  # SheetResult
    copied = Signal(str)
    results_resized = Signal(int)

    def __init__(self, theme: Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self.theme = theme
        self.rates = RateTable()
        self.config = Config()
        self.opts = FormatOptions()
        self.result: SheetResult | None = None
        self.results_width = 260
        self.show_line_numbers = True
        self._last_text: str | None = None
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBar(SheetScrollBar(self))
        self.setTabChangesFocus(False)
        self.setCenterOnScroll(False)
        self.highlighter = Highlighter(self, theme)
        self.highlighter.setDocument(self.document())
        self.kind_labels: dict[str, str] = {}
        self._needle = ""
        self._matches: list[QTextCursor] = []
        self.results = ResultsArea(self)
        self.results.copied.connect(self.copied)
        self.results.resized.connect(self.results_resized)
        self.gutter = LineNumbers(self)
        self.blockCountChanged.connect(lambda _n: self._update_margins())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.recalculate)
        self.textChanged.connect(self._schedule)
        self.textChanged.connect(self._refresh_matches)
        self.updateRequest.connect(self._update_results)
        self.cursorPositionChanged.connect(self._cursor_moved)
        self._completer = QCompleter(self)
        self._completer.setWidget(self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setMaxVisibleItems(9)
        self._completer.activated.connect(self._insert_completion)
        self._words = QStandardItemModel(self)
        self._completer.setModel(self._words)
        popup = self._completer.popup()
        popup.setObjectName("completer")
        popup.setItemDelegate(CompletionDelegate(self))
        popup.setUniformItemSizes(True)
        popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        popup.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        kinds = {w: "keyword" for w in {k for k in KEYWORDS if len(k) > 2} | set(AGGREGATES)}
        kinds |= {w: "keyword" for w in UK.WORDS}
        kinds |= dict.fromkeys(U.all_words(), "unit")
        kinds |= dict.fromkeys(KNOWN_CODES, "currency")
        kinds |= dict.fromkeys(set(FUNCTIONS) | ROUNDERS | set(UK.FUNCTIONS), "function")
        self._static_words = kinds
        self._variables: list[str] = []
        self.set_results_width(self.results_width)
        self.apply_theme(theme)

    def new_document(self, text: str, parent: QObject) -> QTextDocument:
        """A document for one sheet; it keeps that sheet's undo history."""
        doc = QTextDocument(parent)
        doc.setDocumentLayout(QPlainTextDocumentLayout(doc))
        doc.setDefaultFont(self.font())
        doc.setDocumentMargin(DOCUMENT_MARGIN)
        doc.setPlainText(text)
        return doc

    def show_document(self, doc: QTextDocument) -> None:
        if doc is self.document():
            return
        doc.setDefaultFont(self.font())  # the zoom may have changed while it was away
        self.highlighter.spans = []
        self._last_text = None
        self.setDocument(doc)
        self.highlighter.setDocument(doc)
        self._update_margins()
        self._refresh_matches()

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.highlighter.set_theme(theme)
        self.highlighter.rehighlight()
        self.setStyleSheet(f"QPlainTextEdit {{ background: {theme.bg}; color: {theme.text}; }}")
        self._cursor_moved()
        self.results.update()
        self.gutter.update()

    def set_engine(self, rates: RateTable, config: Config, opts: FormatOptions) -> None:
        self.rates, self.config, self.opts = rates, config, opts
        self._last_text = None
        self.recalculate()

    def set_results_width(self, width: int) -> None:
        width = max(MIN_RESULTS_WIDTH, min(width, max(MIN_RESULTS_WIDTH, self.width() // 2 or 600)))
        self.results_width = width
        self._update_margins()

    def set_line_numbers(self, show: bool) -> None:
        self.show_line_numbers = show
        self.gutter.setVisible(show)
        self._update_margins()

    def _update_margins(self) -> None:
        left = self.gutter.width_needed() if self.show_line_numbers else 0
        self.setViewportMargins(left, 0, self.results_width, 0)
        self._place_results()

    def setFont(self, font: QFont) -> None:  # noqa: N802
        super().setFont(font)
        self.document().setDefaultFont(font)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)
        self.document().setDocumentMargin(DOCUMENT_MARGIN)
        self._update_margins()
        self.results.update()

    def _schedule(self) -> None:
        # long sheets: wait for a pause in typing so keystrokes never lag
        blocks = self.document().blockCount()
        self._timer.setInterval(0 if blocks < 150 else min(250, blocks // 2))
        self._timer.start()

    def recalculate(self) -> None:
        text = self.toPlainText()
        if text == self._last_text:
            return
        self._last_text = text
        self.result = evaluate_sheet(text, self.rates, self.config, self.opts)
        old = self.highlighter.spans
        new = [line.spans for line in self.result.lines]
        self.highlighter.spans = new
        doc = self.document()
        self.blockSignals(True)
        try:
            for n, spans in enumerate(new):
                if n >= len(old) or old[n] != spans:
                    block = doc.findBlockByNumber(n)
                    if block.isValid():
                        self.highlighter.rehighlightBlock(block)
        finally:
            self.blockSignals(False)
        self._variables = self.result.variables
        self.results.update()
        self.evaluated.emit(self.result)

    def result_text(self, block_number: int) -> str:
        if self.result is None or not 0 <= block_number < len(self.result.lines):
            return ""
        return self.result.lines[block_number].text

    def current_result(self) -> str:
        return self.result_text(self.textCursor().blockNumber())

    def text_with_results(self) -> str:
        lines = self.toPlainText().split("\n")
        width = max((len(line) for line in lines), default=0)
        out = []
        for n, line in enumerate(lines):
            res = self.result_text(n)
            out.append(f"{line.ljust(width)}  = {res}" if res else line)
        return "\n".join(out)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_results()

    def _place_results(self) -> None:
        vr = self.viewport().geometry()
        self.results.setGeometry(QRect(vr.right() + 1, vr.top(), self.results_width, vr.height()))
        if hasattr(self, "gutter"):
            left = self.gutter.width_needed() if self.show_line_numbers else 0
            self.gutter.setGeometry(QRect(vr.left() - left, vr.top(), left, vr.height()))

    def _update_results(self, rect: QRect, dy: int) -> None:
        if dy:
            self.results.scroll(0, dy)
            self.gutter.scroll(0, dy)
        else:
            self.results.update(0, rect.y(), self.results.width(), rect.height())
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())

    def _cursor_moved(self) -> None:
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(self.theme.current_line))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        found = []
        color = QColor(self.theme.accent)
        color.setAlpha(70)
        for match in self._matches:
            f = QTextEdit.ExtraSelection()
            f.format.setBackground(color)
            f.cursor = match
            found.append(f)
        self.setExtraSelections(([sel] if not self.isReadOnly() else []) + found)
        self.results.update()
        if hasattr(self, "gutter"):
            self.gutter.update()

    def toggle_comment(self) -> None:
        cur = self.textCursor()
        doc = self.document()
        start = doc.findBlock(cur.selectionStart()).blockNumber()
        end_pos = cur.selectionEnd()
        end_block = doc.findBlock(end_pos)
        if (
            cur.hasSelection()
            and end_pos == end_block.position()
            and end_block.blockNumber() > start
        ):
            end = end_block.blockNumber() - 1
        else:
            end = end_block.blockNumber()
        blocks = [doc.findBlockByNumber(n) for n in range(start, end + 1)]
        texts = [b.text() for b in blocks]
        uncomment = all(t.lstrip().startswith("//") for t in texts if t.strip())
        edit = QTextCursor(doc)
        edit.beginEditBlock()
        for b, t in zip(blocks, texts, strict=True):
            if not t.strip():
                continue
            indent = len(t) - len(t.lstrip())
            c = QTextCursor(b)
            c.setPosition(b.position() + indent)
            if uncomment:
                rest = t[indent:]
                n = 3 if rest.startswith(COMMENT_PREFIX) else 2
                c.setPosition(b.position() + indent + n, QTextCursor.MoveMode.KeepAnchor)
                c.removeSelectedText()
            else:
                c.insertText(COMMENT_PREFIX)
        edit.endEditBlock()

    def set_find(self, needle: str) -> None:
        """Highlight every place `needle` appears (any case); empty clears it."""
        self._needle = needle
        self._refresh_matches()

    def _refresh_matches(self) -> None:
        if not self._needle and not self._matches:
            return
        self._matches = []
        doc = self.document()
        cur = doc.find(self._needle, 0) if self._needle else QTextCursor()
        while not cur.isNull() and len(self._matches) < MAX_MATCHES:
            self._matches.append(cur)
            cur = doc.find(self._needle, cur)
        self._cursor_moved()
        self.verticalScrollBar().update()

    def find_matches(self) -> list[QTextCursor]:
        return self._matches

    def match_count(self) -> tuple[int, int]:
        """(number of the selected match, from 1, or 0; how many there are)."""
        cur = self.textCursor()
        for n, m in enumerate(self._matches, 1):
            if (m.selectionStart(), m.selectionEnd()) == (cur.selectionStart(), cur.selectionEnd()):
                return n, len(self._matches)
        return 0, len(self._matches)

    def find_next(self, backward: bool = False, start: int | None = None) -> None:
        """Select the next match after the cursor (or `start`), going round at the end."""
        if not self._matches:
            return
        cur = self.textCursor()
        if backward:
            pos = cur.selectionStart() if start is None else start
            before = [m for m in self._matches if m.selectionEnd() <= pos]
            match = before[-1] if before else self._matches[-1]
        else:
            pos = cur.selectionEnd() if start is None else start
            after = [m for m in self._matches if m.selectionStart() >= pos]
            match = after[0] if after else self._matches[0]
        self.setTextCursor(QTextCursor(match))
        self.centerCursor()

    def kind_label(self, kind: str | None) -> str:
        return self.kind_labels.get(kind or "", "")

    def completion_prefix(self) -> str:
        return self._completer.completionPrefix()

    def _word_before_cursor(self) -> str:
        cur = self.textCursor()
        text = cur.block().text()[: cur.positionInBlock()]
        m = WORD_RE.search(text)
        return m.group() if m else ""

    def _insert_completion(self, completion: str) -> None:
        prefix = self._word_before_cursor()
        cur = self.textCursor()
        cur.movePosition(
            QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(prefix)
        )
        cur.insertText(completion)
        self.setTextCursor(cur)

    def delete_to_line_edge(self, forward: bool) -> None:
        """Delete from the cursor to the start (or end) of the line, as one undo step.

        At the very start of a line it joins the line above, like Backspace.
        """
        if self.isReadOnly():
            return
        cur = self.textCursor()
        if not cur.hasSelection():
            at_edge = cur.atBlockEnd() if forward else cur.atBlockStart()
            move = QTextCursor.MoveOperation
            if at_edge:
                cur.movePosition(
                    move.NextCharacter if forward else move.PreviousCharacter,
                    QTextCursor.MoveMode.KeepAnchor,
                )
            else:
                cur.movePosition(
                    move.EndOfBlock if forward else move.StartOfBlock,
                    QTextCursor.MoveMode.KeepAnchor,
                )
        cur.removeSelectedText()
        self.setTextCursor(cur)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        line_edge = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        if event.modifiers() == line_edge and event.key() in (
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
        ):
            self._completer.popup().hide()
            self.delete_to_line_edge(forward=event.key() == Qt.Key.Key_Delete)
            return
        popup = self._completer.popup()
        if popup.isVisible() and event.key() in (
            Qt.Key.Key_Enter,
            Qt.Key.Key_Return,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Escape,
            Qt.Key.Key_Backtab,
        ):
            if event.key() == Qt.Key.Key_Escape:
                popup.hide()
                return
            index = popup.currentIndex()
            if index.isValid():
                self._insert_completion(index.data())
                popup.hide()
                return
            popup.hide()
        super().keyPressEvent(event)
        if self.isReadOnly():
            return
        text = event.text()
        if not text or not (text.isalnum() or text == "_"):
            popup.hide()
            return
        prefix = self._word_before_cursor()
        if len(prefix) < 2:
            popup.hide()
            return
        low = prefix.lower()
        kinds = self._static_words | dict.fromkeys(self._variables, "variable")
        words = sorted(
            (w for w in kinds if w.lower().startswith(low) and w.lower() != low),
            key=lambda w: (KIND_ORDER.index(kinds[w]), len(w), w.lower()),
        )
        self._words.clear()
        for w in words[:200]:
            item = QStandardItem(w)
            item.setData(kinds[w], KIND_ROLE)
            self._words.appendRow(item)
        self._completer.setCompletionPrefix(prefix)
        if self._completer.completionCount() == 0:
            popup.hide()
            return
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.translate(self.viewportMargins().left(), 4)
        rect.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 8)
        self._completer.complete(rect)
