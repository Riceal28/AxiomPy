"""HTTP notification transport built on QtNetwork."""

from __future__ import annotations

from typing import Mapping

from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from axiom.core.notify import NotifyConfig, render_notify


class NotifyClient(QObject):
    """Send rendered Notify requests without blocking the UI thread."""

    result = Signal(str, bool, int, str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self._replies: set[QNetworkReply] = set()

    def send(
        self,
        config: NotifyConfig,
        context: Mapping[str, object],
        request_id: str = "",
    ) -> bool:
        rendered = render_notify(config, context)
        if not rendered.url.strip():
            self.result.emit(
                request_id,
                False,
                0,
                "",
                "Notify URL is empty",
            )
            return False
        payload = rendered.body.encode("utf-8")
        method = rendered.method.upper()
        if rendered.body_error and (method != "GET" or payload):
            self.result.emit(
                request_id,
                False,
                0,
                "",
                rendered.body_error,
            )
            return False

        url = QUrl(rendered.url)
        if (
            not url.isValid()
            or url.scheme().lower() not in {"http", "https"}
            or not url.host()
        ):
            self.result.emit(
                request_id,
                False,
                0,
                "",
                "Notify URL must be an absolute HTTP or HTTPS URL",
            )
            return False

        request = QNetworkRequest(url)
        for name, value in rendered.headers:
            request.setRawHeader(name.encode("utf-8"), value.encode("utf-8"))
        request.setTransferTimeout(max(1000, int(config.timeout_ms)))
        if method == "GET":
            reply = (
                self.manager.sendCustomRequest(request, b"GET", payload)
                if payload
                else self.manager.get(request)
            )
        elif method == "PUT":
            # sendCustomRequest does not inject Qt's default form
            # Content-Type when the user disabled that header.
            reply = self.manager.sendCustomRequest(
                request,
                b"PUT",
                payload,
            )
        elif method == "PATCH":
            reply = self.manager.sendCustomRequest(request, b"PATCH", payload)
        elif method == "DELETE":
            reply = self.manager.sendCustomRequest(
                request,
                b"DELETE",
                payload,
            )
        else:
            reply = self.manager.sendCustomRequest(
                request,
                b"POST",
                payload,
            )
        self._replies.add(reply)
        reply.finished.connect(
            lambda: self._finish(reply, request_id)
        )
        return True

    def wait_for_finished(self, timeout_ms: int = 2000) -> bool:
        """Wait briefly for active replies so closing the app does not drop them."""

        if not self._replies:
            return True
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        poll = QTimer()
        poll.setInterval(20)

        def check_finished() -> None:
            if not self._replies:
                loop.quit()

        poll.timeout.connect(check_finished)
        timer.start(max(0, int(timeout_ms)))
        poll.start()
        loop.exec()
        timer.stop()
        poll.stop()
        return not self._replies

    def _finish(self, reply: QNetworkReply, request_id: str) -> None:
        status = reply.attribute(
            QNetworkRequest.HttpStatusCodeAttribute
        ) or 0
        body = bytes(reply.readAll()).decode("utf-8", errors="replace")
        error = ""
        if reply.error() != QNetworkReply.NoError:
            error = reply.errorString()
        ok = reply.error() == QNetworkReply.NoError and 200 <= int(status) < 300
        self.result.emit(request_id, ok, int(status), body, error)
        self._replies.discard(reply)
        reply.deleteLater()
