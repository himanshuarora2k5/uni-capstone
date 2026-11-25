"""Drift detection: an event the contract does not cover is a drift event.

v0.1 is alert-only (it reports; it blocks nothing). Prometheus export and the dashboard are
later releases (docs/ROADMAP.md).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Iterable

from ..contract import Contract
from ..engine.normalise import get_path
from ..observe import ACTION, DOMAIN, observations


@dataclass(frozen=True)
class DriftEvent:
    type: str            # "domain" or "cloud_action"
    value: str
    index: int           # position of the entry in the log
    original_time: str | None
    raw: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DriftReport:
    entries_checked: int = 0
    drift: list[DriftEvent] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.drift)

    def counts(self) -> dict[str, int]:
        c = Counter(d.type for d in self.drift)
        return {DOMAIN: c.get(DOMAIN, 0), ACTION: c.get(ACTION, 0)}

    def unique(self) -> list[tuple[str, str, int]]:
        """(type, value, how many times) sorted by type then value."""
        c = Counter((d.type, d.value) for d in self.drift)
        return [(t, v, n) for (t, v), n in sorted(c.items())]


def check_entries(contract: Contract, entries: Iterable[dict]) -> DriftReport:
    """Compare stored log entries (as yielded by integrity.read_entries) with a contract."""
    report = DriftReport()
    for entry in entries:
        report.entries_checked += 1
        record = entry["record"]
        when = get_path(record.get("event", {}), "metadata.original_time")
        for kind, value in observations(record):
            allowed = contract.allows_domain(value) if kind == DOMAIN else contract.allows_action(value)
            if not allowed:
                report.drift.append(DriftEvent(kind, value, entry["i"], when, record.get("raw", "")))
    return report
