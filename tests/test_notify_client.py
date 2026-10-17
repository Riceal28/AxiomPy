"""QtNetwork HTTP transport for Notify."""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from axiom.core.notify import NotifyConfig, NotifyHeader
from axiom.ui.notify_client import NotifyClient


def test_notify_client_posts_rendered_http_request(qtbot):
    received: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            received["path"] = self.path
            received["header"] = self.headers.get("X-Test", "")
            received["body"] = self.rfile.read(length).decode("utf-8")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        config = NotifyConfig.defaults()
        config.url = f"http://127.0.0.1:{port}/hook/{{status}}"
        config.headers = [
            NotifyHeader(True, "Content-Type", "application/json"),
            NotifyHeader(True, "X-Test", "{status}"),
        ]
        config.body = '{"message": {message_json}, "code": {exit_code}}'
        client = NotifyClient()
        results = []
        client.result.connect(
            lambda _request_id, ok, status, body, error: results.append(
                (ok, status, body, error)
            )
        )
        assert client.send(
            config,
            {
                "status": "Completed",
                "exit_code": "0",
                "output_name": "clip.mp4",
            },
        )
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
    finally:
        server.shutdown()
        server.server_close()

    assert results
    assert results[0][0] is True
    assert results[0][1] == 200
    assert received["path"] == "/hook/Completed"
    assert received["body"] == (
        '{"message": "Status: Completed\\nExit Code: 0\\n'
        'Output Name: clip.mp4", "code": 0}'
    )


def test_notify_client_rejects_invalid_json_without_sending(qtbot):
    config = NotifyConfig.defaults()
    config.url = "http://127.0.0.1:1/hook"
    config.body = '{"message": {missing_placeholder}}'
    client = NotifyClient()
    results = []
    client.result.connect(
        lambda _request_id, ok, status, body, error: results.append(
            (ok, status, body, error)
        )
    )

    assert client.send(config, {"status": "Completed"}) is False

    assert results
    assert results[0][0] is False
    assert "Invalid JSON body" in results[0][3]


def test_notify_client_rejects_relative_url(qtbot):
    config = NotifyConfig.defaults()
    config.url = "example.test/hook"
    client = NotifyClient()
    results = []
    client.result.connect(
        lambda request_id, ok, status, body, error: results.append(
            (request_id, ok, error)
        )
    )

    assert client.send(config, {}, "bad-url") is False

    assert results == [
        (
            "bad-url",
            False,
            "Notify URL must be an absolute HTTP or HTTPS URL",
        )
    ]


def test_notify_client_omits_disabled_headers(qtbot):
    received: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            received["content_type"] = self.headers.get(
                "Content-Type",
                "",
            )
            received["x_test"] = self.headers.get("X-Test", "")
            self.rfile.read(length)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        config = NotifyConfig.defaults()
        config.url = f"http://127.0.0.1:{port}/hook"
        config.headers = [
            NotifyHeader(False, "Content-Type", "application/json"),
            NotifyHeader(False, "X-Test", "hidden"),
        ]
        client = NotifyClient()
        results = []
        client.result.connect(
            lambda _request_id, ok, status, body, error: results.append(
                (ok, status, body, error)
            )
        )
        assert client.send(
            config,
            {
                "status": "Completed",
                "exit_code": "0",
                "output_name": "clip.mp4",
            },
        )
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
    finally:
        server.shutdown()
        server.server_close()

    assert results[0][0] is True
    assert received["content_type"] == ""
    assert received["x_test"] == ""


def test_notify_client_sends_explicit_get_body(qtbot):
    received: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            received["body"] = self.rfile.read(length).decode("utf-8")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        config = NotifyConfig.defaults()
        config.method = "GET"
        config.url = f"http://127.0.0.1:{port}/hook"
        config.headers = []
        config.body = '{"message":"{status}"}'
        client = NotifyClient()
        results = []
        client.result.connect(
            lambda request_id, ok, status, body, error: results.append(
                (request_id, ok, status, body, error)
            )
        )

        assert client.send(
            config,
            {"status": "Completed"},
            "job-1",
        )
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
    finally:
        server.shutdown()
        server.server_close()

    assert received["body"] == '{"message":"Completed"}'
    assert results[0][0] == "job-1"
    assert results[0][1] is True


def test_notify_client_can_wait_for_pending_reply(qtbot):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            time.sleep(0.15)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        config = NotifyConfig.defaults()
        config.url = f"http://127.0.0.1:{port}/hook"
        config.headers = []
        config.body = "{}"
        client = NotifyClient()
        results = []
        client.result.connect(
            lambda request_id, ok, status, body, error: results.append(
                (request_id, ok, status)
            )
        )

        assert client.send(config, {}, "slow-job")
        assert client.wait_for_finished(2000) is True
    finally:
        server.shutdown()
        server.server_close()

    assert results == [("slow-job", True, 204)]
