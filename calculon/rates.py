"""Exchange rates: fetched daily, cached on disk, bundled snapshot as a last resort."""

import json
import logging
import time
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import __version__
from .engine import RatesError, RateTable
from .paths import FALLBACK_RATES

log = logging.getLogger(__name__)

STALE_AFTER = 24 * 3600
CHECK_EVERY_MS = 60 * 60 * 1000
MAX_BYTES = 2_000_000


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
            self.table = RateTable.parse(json.dumps(data["table"]), data["table"].get("source", ""))
            self.fetched_at = float(data["fetched_at"])
            return
        except OSError, ValueError, KeyError, TypeError, RatesError:
            pass
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
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, f"Calculon/{__version__}")
        req.setTransferTimeout(15000)
        reply = self._net.get(req)
        reply.finished.connect(lambda: self._done(reply, url))

    def _done(self, reply: QNetworkReply, url: str) -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.error = reply.errorString()
            log.info("rates from %s failed: %s", url, self.error)
            self._next()
            return
        body = bytes(reply.read(MAX_BYTES).data())
        try:
            table = RateTable.parse(body, QUrl(url).host())
        except RatesError as exc:
            self.error = str(exc)
            log.info("rates from %s unusable: %s", url, exc)
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
