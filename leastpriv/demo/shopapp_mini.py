"""ShopApp-mini: six routes, four outbound calls to reserved `.example` hosts.

    GET  /              home page; links to /products, /about, /checkout
    GET  /products      -> outbound call to the product-images host
    GET  /about         (no outbound call)
    GET  /checkout      -> outbound call to the payment host
    GET  /admin/export  -> outbound call to the analytics host   (not linked from any page)
    POST /webhook       -> outbound call to the notifications host (not linked from any page)

The "outbound call" is only a DNS lookup of a reserved `.example` name. With a recorder active the
lookup is recorded and blocked; without one it simply fails to resolve. No third-party server is
ever contacted.
"""
from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOSTS = {
    "images": "images.shopapp.example",
    "payments": "payments.shopapp.example",
    "analytics": "analytics.shopapp.example",
    "notifications": "notifications.shopapp.example",
}
EXPECTED_DOMAINS = frozenset(HOSTS.values())

_HOME = (
    "<html><body><h1>ShopApp-mini</h1>"
    '<a href="/products">Products</a> <a href="/about">About</a> <a href="/checkout">Checkout</a>'
    "</body></html>"
)


def call_out(host: str) -> None:
    """Stand-in for an outbound call: look the name up and ignore the failure."""
    try:
        socket.getaddrinfo(host, 443)
    except OSError:
        pass


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: str, ctype: str = "text/html") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, _HOME)
        elif path == "/products":
            call_out(HOSTS["images"])
            self._send(200, "products", "text/plain")
        elif path == "/about":
            self._send(200, "about", "text/plain")
        elif path == "/checkout":
            call_out(HOSTS["payments"])
            self._send(200, "checkout", "text/plain")
        elif path == "/admin/export":
            call_out(HOSTS["analytics"])
            self._send(200, "export", "text/plain")
        elif path == "/webhook":
            self._send(405, "use POST", "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if self.path.split("?", 1)[0] == "/webhook":
            call_out(HOSTS["notifications"])
            self._send(200, "ok", "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    def log_message(self, *args) -> None:       # keep the console quiet
        pass


class ShopApp:
    """Context manager that serves the app on 127.0.0.1 (random free port)."""

    def __enter__(self) -> "ShopApp":
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.daemon_threads = True
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
