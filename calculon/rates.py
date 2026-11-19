"""Exchange rates: fetched daily, cached on disk, bundled snapshot as a last resort."""

import json
import logging
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, QTimer, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import net
from .engine import RatesError, RateTable
from .paths import FALLBACK_RATES

log = logging.getLogger(__name__)

STALE_AFTER = 24 * 3600
CHECK_EVERY_MS = 60 * 60 * 1000
MAX_BYTES = 2_000_000


def fetch_rates(
    manager: QNetworkAccessManager, url: str, done: Callable[[RateTable | None, str], None]
) -> None:
    """Fetch one rates source for either the daily refresh or the Settings test."""
    request = net.request(url)
    request.setAttribute(
        QNetworkRequest.Attribute.RedirectPolicyAttribute,
        QNetworkRequest.RedirectPolicy.SameOriginRedirectPolicy,
    )
    reply = manager.get(request)
    # Let one extra byte through so we can detect an oversized reply.
    read_limit = MAX_BYTES + 1
    reply.setReadBufferSize(read_limit)
    deadline = QTimer(reply)
    deadline.setSingleShot(True)
    abort_reason = ""
    size_error = "rates response is too large"

    def abort(reason: str) -> None:
        nonlocal abort_reason
        abort_reason = reason
        reply.abort()

    def abort_if_oversized() -> None:
        if reply.bytesAvailable() > MAX_BYTES:
            abort(size_error)

    def finish() -> None:
        deadline.stop()
        reply.deleteLater()
        if abort_reason or reply.error() != QNetworkReply.NetworkError.NoError:
            done(None, abort_reason or reply.errorString())
            return
        body = reply.read(read_limit)
        if len(body) > MAX_BYTES:
            done(None, size_error)
            return
        try:
            table = RateTable.parse(bytes(body), request.url().host())
        except RatesError as exc:
            done(None, str(exc))
            return
        done(table, "")

    deadline.timeout.connect(lambda: abort("rates request timed out"))
    reply.readyRead.connect(abort_if_oversized)
    reply.finished.connect(finish)
    deadline.start(net.TIMEOUT_MS)


def cache_file() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "rates-cache.json"


class RatesService(QObject):
    changed = Signal()  # a new rate table is in self.table
    status_changed = Signal()

    def __init__(self, sources: list[str], parent: QObject | None = None):
        super().__init__(parent)
        self.sources = sources
        self.table = RateTable()
        self.fetched_at = 0.0
        self.error = ""
        self.busy = False
        self._net = QNetworkAccessManager(self)
        self._pending: list[str] = []
        self._load_initial()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_if_stale)
        self._timer.start(CHECK_EVERY_MS)

    def _load_initial(self) -> None:
        try:
            data = json.loads(cache_file().read_text(encoding="utf-8"))
            cached = data["table"]
            if not isinstance(cached, dict):
                raise RatesError("invalid rates cache")
            fetched_at = float(data["fetched_at"])
            table = RateTable.parse(json.dumps(cached), cached.get("source", ""))
        except OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError:
            pass
        else:
            self.table = table
            self.fetched_at = fetched_at
            return
        try:
            self.table = RateTable.parse(FALLBACK_RATES.read_bytes(), "bundled snapshot")
        except OSError, RatesError:
            log.warning("no bundled rates found at %s", FALLBACK_RATES)

    def _save_cache(self) -> None:
        path = cache_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"fetched_at": self.fetched_at, "table": json.loads(self.table.to_json())}
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            log.warning("could not write the rates cache", exc_info=True)

    def set_sources(self, sources: list[str]) -> None:
        if sources != self.sources:
            self.sources = sources
            self.refresh()

    def refresh_if_stale(self) -> None:
        if time.time() - self.fetched_at > STALE_AFTER:
            self.refresh()

    def refresh(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self._pending = list(self.sources)
        self.status_changed.emit()
        self._next()

    def _next(self) -> None:
        if not self._pending:
            self.busy = False
            self.status_changed.emit()
            return
        url = self._pending.pop(0)
        fetch_rates(self._net, url, partial(self._source_finished, url))

    def _source_finished(self, url: str, table: RateTable | None, error: str) -> None:
        if table is None:
            self.error = error
            log.info("rates from %s failed: %s", url, error)
            self._next()
            return
        self.table = table
        self.fetched_at = time.time()
        self.error = ""
        self._pending = []
        self.busy = False
        self._save_cache()
        self.changed.emit()
        self.status_changed.emit()
