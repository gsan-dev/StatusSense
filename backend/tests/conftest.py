from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _EchoHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/fail":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"error")
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

    def log_message(self, format, *args):  # noqa: A002
        pass  # silenciar logs del servidor de pruebas


@pytest.fixture
def local_http_server():
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield host, port
    server.shutdown()
    thread.join(timeout=2)
