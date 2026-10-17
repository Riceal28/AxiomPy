"""HTTP notification transport built on QtNetwork."""

from __future__ import annotations

from typing import Mapping

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from axiom.core.notify import NotifyConfig, render_notify


class NotifyClient(QObject):
    """Send rendered Notify requests without blocking the UI thread."""

    result = Signal(bool, int, str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)

    def send(
        self,
        config: NotifyConfig,
        context: Mapping[str, object],
    ) -> bool:
        rendered = render_notify(config, context)
        if not rendered.url.strip():
            self.result.emit(False, 0, "", "Notify URL is empty")
            return False

        request = QNetworkRequest(QUrl(rendered.url))
        for name, value in rendered.headers:
            request.setRawHeader(name.encode("utf-8"), value.encode("utf-8"))
        request.setTransferTimeout(max(1000, int(config.timeout_ms)))
        payload = rendered.body.encode("utf-8")
        method = rendered.method.upper()
        if method == "GET":
            reply = self.manager.get(request)
        elif method == "PUT":
            reply = self.manager.put(request, payload)
        elif method == "PATCH":
            reply = self.manager.sendCustomRequest(request, b"PATCH", payload)
        elif method == "DELETE":
            reply = self.manager.sendCustomRequest(
                request,
                b"DELETE",
                payload,
            )
        else:
            reply = self.manager.post(request, payload)
        reply.finished.connect(lambda: self._finish(reply))
        return True

    def _finish(self, reply: QNetworkReply) -> None:
        status = reply.attribute(
            QNetworkRequest.HttpStatusCodeAttribute
        ) or 0
        body = bytes(reply.readAll()).decode("utf-8", errors="replace")
        error = ""
        if reply.error() != QNetworkReply.NoError:
            error = reply.errorString()
        ok = reply.error() == QNetworkReply.NoError and 200 <= int(status) < 300
        self.result.emit(ok, int(status), body, error)
        reply.deleteLater()
