"""QtNetwork HTTP transport for Notify."""

from __future__ import annotations

import threading
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
            lambda ok, status, body, error: results.append(
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
