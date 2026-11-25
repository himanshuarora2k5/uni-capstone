"""The three test-traffic sources used with ShopApp-mini.

    run_tests   hand-written requests (the "repository's own tests")
    crawl       follows links from the home page (reaches only linked pages)
    user_added  requests a user adds for routes nothing links to
"""
from __future__ import annotations

import urllib.error
import urllib.request
from html.parser import HTMLParser

# Never use environment proxies for loopback traffic.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(base: str, path: str, data: bytes | None = None) -> tuple[int, str]:
    req = urllib.request.Request(base + path, data=data, method="POST" if data is not None else "GET")
    try:
        with _OPENER.open(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)


def run_tests(base: str) -> list[str]:
    paths = ["/", "/products", "/about"]
    for p in paths:
        request(base, p)
    return paths


def crawl(base: str, start: str = "/", limit: int = 50) -> list[str]:
    seen: list[str] = []
    queue = [start]
    while queue and len(seen) < limit:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.append(path)
        _, body = request(base, path)
        parser = _Links()
        parser.feed(body)
        for href in parser.hrefs:
            if href.startswith("/") and not href.startswith("//") and href not in seen:
                queue.append(href)
    return seen


def user_added(base: str) -> list[str]:
    request(base, "/admin/export")
    request(base, "/webhook", data=b"{}")
    return ["GET /admin/export", "POST /webhook"]
