"""Every request Calculon makes is built here, so they all say who is asking."""

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkRequest

from . import __version__

TIMEOUT_MS = 15000


def request(url: str) -> QNetworkRequest:
    req = QNetworkRequest(QUrl(url))
    req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, f"Calculon/{__version__}")
    req.setTransferTimeout(TIMEOUT_MS)
    return req
