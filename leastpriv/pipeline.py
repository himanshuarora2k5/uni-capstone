"""Library entry points shared by the CLI, the demo, the experiments and the tests.

The point of this module: every stage is a plain function, so a new release adds a function or a
module and the existing ones keep working.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .engine import Normaliser, Registry, default_registry_dir, iter_raw_events, load_registry
from .integrity import ChainedLog, write_anchor


@dataclass
class IngestStats:
    events: int = 0
    blank_lines_skipped: int = 0
    per_format: Counter = field(default_factory=Counter)
    head: str = ""

    @property
    def fallback(self) -> int:
        return self.per_format.get("fallback", 0)


def build_registry(*extra: str | Path) -> Registry:
    """The shipped formats plus any extra folders/files (extras override by format name)."""
    return load_registry(default_registry_dir(), *extra)


def ingest(files: Iterable[str | Path], registry: Registry, log_path: str | Path,
           anchor_out: str | Path | None = None) -> IngestStats:
    """Normalise every raw event in `files` and append it to the hash-chained log.

    No event is dropped: lines no format matches are stored through the fallback. If
    `anchor_out` is given, the latest chain hash is written there; keep that file OUTSIDE the
    log store (another account/bucket/machine) or it protects nothing.
    """
    norm = Normaliser(registry)
    stats = IngestStats()
    with ChainedLog(log_path) as log:
        for f in files:
            raw_stats: dict = {}
            for raw in iter_raw_events(f, raw_stats):
                rec = norm.normalise(raw)
                log.append(rec)
                stats.events += 1
                stats.per_format[rec["format"]] += 1
            stats.blank_lines_skipped += raw_stats.get("blank", 0)
        stats.head = log.head
    if anchor_out is not None:
        write_anchor(anchor_out, stats.head)
    return stats
