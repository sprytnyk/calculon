"""The sheet editor: text on the left, results in a column on the right."""

import re

from PySide6.QtCore import QRect, QSize, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

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


class Highlighter(QSyntaxHighlighter):
    def __init__(self, doc: QTextDocument, theme: Theme):
        super().__init__(doc)
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
        self.setTabChangesFocus(False)
        self.setCenterOnScroll(False)
        self.highlighter = Highlighter(self.document(), theme)
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
        self.updateRequest.connect(self._update_results)
        self.cursorPositionChanged.connect(self._cursor_moved)
        self._completer = QCompleter(self)
        self._completer.setWidget(self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setModelSorting(QCompleter.ModelSorting.CaseInsensitivelySortedModel)
        self._completer.activated.connect(self._insert_completion)
        self._words = QStringListModel(self)
        self._completer.setModel(self._words)
        self._static_words = sorted(
            set(U.all_words())
            | KNOWN_CODES
            | {k for k in KEYWORDS if len(k) > 2}
            | set(FUNCTIONS)
            | ROUNDERS
            | set(AGGREGATES)
            | set(UK.WORDS)
            | set(UK.FUNCTIONS),
            key=str.lower,
        )
        self._variables: list[str] = []
        self.set_results_width(self.results_width)
        self.apply_theme(theme)

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
        self.document().setDocumentMargin(14)
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
        self.setExtraSelections([sel] if not self.isReadOnly() else [])
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

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
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
        words = sorted(set(self._variables) | set(self._static_words), key=str.lower)
        words = [w for w in words if w.lower() != prefix.lower()]
        self._words.setStringList(words)
        self._completer.setCompletionPrefix(prefix)
        if self._completer.completionCount() == 0:
            popup.hide()
            return
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(
            popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 16
        )
        self._completer.complete(rect)
