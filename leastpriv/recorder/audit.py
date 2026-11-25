"""In-process stand-in for the egress proxy (Python audit hook on DNS lookups).

While an AuditRecorder is active, every host name the process looks up (other than loopback) is
written as one line in the `egress_proxy` format, and the lookup is blocked, so nothing leaves the
machine. This only sees Python code in this process; the real recorder (an egress proxy in the
sandbox network) is a later release (docs/ROADMAP.md, v0.3).
"""
from __future__ import annotations

import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

_WATCHED = ("socket.getaddrinfo", "socket.gethostbyname")
_LOCK = threading.Lock()
_ACTIVE: list["AuditRecorder"] = []
_INSTALLED = False
_SAFE = re.compile(r"[^A-Za-z0-9._\-]")


def _is_loopback(host: str) -> bool:
    return host in ("", "localhost", "::1") or host.startswith("127.")


def _hook(event: str, args: tuple) -> None:
    if event not in _WATCHED or not _ACTIVE:
        return
    host = args[0] if args else None
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str) or _is_loopback(host):
        return
    port = args[1] if len(args) > 1 else None
    if _ACTIVE[-1]._record(host, port):
        raise OSError(f"outbound lookup of '{host}' was recorded and blocked by the sandbox recorder")


def _install() -> None:
    global _INSTALLED
    with _LOCK:
        if not _INSTALLED:
            sys.addaudithook(_hook)     # audit hooks cannot be removed; _hook is a no-op when idle
            _INSTALLED = True


class AuditRecorder:
    """Context manager. `lines` holds the recorded events; `out_path` (optional) gets them too."""

    def __init__(self, application: str, out_path: str | Path | None = None, block: bool = True):
        self.application = _SAFE.sub("_", application) or "app"
        self.block = block
        self.lines: list[str] = []
        self._fh = open(out_path, "a", encoding="utf-8", newline="\n") if out_path else None

    def _record(self, host: str, port) -> bool:
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y-%m-%dT%H:%M:%S") + f".{now.microsecond // 1000:03d}Z"
        port_txt = str(port) if isinstance(port, int) else "-"
        line = f"{stamp} {self.application} CONNECT {_SAFE.sub('_', host)}:{port_txt} recorded"
        with _LOCK:
            self.lines.append(line)
            if self._fh:
                self._fh.write(line + "\n")
                self._fh.flush()
        return self.block

    def raw_events(self) -> list[str]:
        with _LOCK:
            return list(self.lines)

    def domains_seen(self) -> set[str]:
        return {ln.split()[3].rsplit(":", 1)[0] for ln in self.raw_events()}

    def __enter__(self) -> "AuditRecorder":
        _install()
        with _LOCK:
            _ACTIVE.append(self)
        return self

    def __exit__(self, *exc) -> None:
        with _LOCK:
            if self in _ACTIVE:
                _ACTIVE.remove(self)
            if self._fh:
                self._fh.close()
