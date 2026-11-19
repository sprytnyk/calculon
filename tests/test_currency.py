"""Exchange rate parsing."""

import json
from decimal import Decimal

import pytest
from PySide6.QtCore import QByteArray, QObject, QTimer, Signal
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

from calculon import rates
from calculon.engine.currency import RatesError, RateTable


def test_parse_frankfurter_v2_rates() -> None:
    table = RateTable.parse(
        '[{"date":"2026-11-16","base":"USD","quote":"EUR","rate":0.9},'
        '{"date":"2026-11-16","base":"USD","quote":"GBP","rate":0.8}]'
    )
    assert table.base == "USD"
    assert table.rates == {"USD": Decimal(1), "EUR": Decimal("0.9"), "GBP": Decimal("0.8")}


@pytest.mark.parametrize(
    "value",
    [
        '"NaN"',
        '"sNaN"',
        '"-NaN"',
        '"NaN123"',
        "NaN",
        '"Infinity"',
        '"-Infinity"',
        "Infinity",
        "-Infinity",
        "1e9999",
        "-1e9999",
        "0",
        "-1",
        '"invalid"',
    ],
)
def test_parse_skips_unusable_rates(value: str) -> None:
    table = RateTable.parse('{"rates": {"EUR": ' + value + ', "GBP": 0.8}}')
    assert table.rates == {"USD": Decimal(1), "GBP": Decimal("0.8")}

    with pytest.raises(RatesError, match="no usable rates in the document"):
        RateTable.parse('{"rates": {"EUR": ' + value + "}}")


@pytest.mark.parametrize("field,value", [("base", "<b>USD</b>"), ("updated", "Infinity")])
def test_rates_reject_invalid_metadata(field, value) -> None:
    with pytest.raises(RatesError, match="invalid"):
        RateTable.parse(json.dumps({"rates": {"EUR": 0.9}, field: value}))


class FakeRatesReply(QObject):
    readyRead = Signal()
    finished = Signal()

    def __init__(self, body: bytes = b"") -> None:
        super().__init__()
        self.body = body
        self.buffer_size = 0
        self.aborted = False

    def setReadBufferSize(self, size: int) -> None:
        self.buffer_size = size

    def bytesAvailable(self) -> int:
        return len(self.body)

    def read(self, size: int) -> QByteArray:
        return QByteArray(self.body[:size])

    def error(self) -> QNetworkReply.NetworkError:
        return QNetworkReply.NetworkError.NoError

    def abort(self) -> None:
        self.aborted = True
        self.finished.emit()


@pytest.mark.parametrize("failure", ["oversize", "timeout", "timestamp"])
def test_bad_rate_reply_uses_fallback(app, monkeypatch, tmp_path, failure) -> None:
    primary = FakeRatesReply(b'{"rates":{"EUR":0.9},"updated":"Infinity"}')
    fallback = FakeRatesReply(b'{"rates":{"EUR":0.8}}')
    replies = iter((primary, fallback))
    requests = []

    def get(request):
        requests.append(request)
        return next(replies)

    cache = tmp_path / "rates.json"
    monkeypatch.setattr(rates, "cache_file", lambda: cache)
    monkeypatch.setattr(rates, "MAX_BYTES", 100)
    service = rates.RatesService(
        ["https://primary.invalid/rates", "https://fallback.invalid/rates"]
    )
    monkeypatch.setattr(service._net, "get", get)
    last_good = service.table
    service.refresh()

    assert requests[0].attribute(QNetworkRequest.Attribute.RedirectPolicyAttribute) == (
        QNetworkRequest.RedirectPolicy.SameOriginRedirectPolicy
    )
    assert primary.buffer_size == rates.MAX_BYTES + 1
    if failure == "oversize":
        primary.body = b" " * rates.MAX_BYTES
        primary.readyRead.emit()
        assert len(requests) == 1
        primary.body += b" "
        primary.readyRead.emit()
        assert primary.aborted
    elif failure == "timeout":
        primary.findChild(QTimer).timeout.emit()
        assert primary.aborted
    else:
        primary.finished.emit()

    assert len(requests) == 2
    assert service.table is last_good
    assert not cache.exists()
    fallback.finished.emit()
    assert not service.busy
    assert service.table.rate("USD", "EUR") == Decimal("0.8")
    assert json.loads(cache.read_text())["table"]["source"] == "fallback.invalid"
