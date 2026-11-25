"""The recorder interface.

A recorder is anything that watches a sandboxed run and produces raw events as text (one string
per event). The log engine turns raw events into OCSF-shaped records, so a new recorder (the real
egress proxy, a CloudTrail puller, ...) plugs in by producing text in a registered format; nothing
downstream changes.
"""
from __future__ import annotations

from typing import Iterable, Protocol


class Recorder(Protocol):
    def raw_events(self) -> Iterable[str]:
        """Raw events recorded so far, in order."""
        ...
