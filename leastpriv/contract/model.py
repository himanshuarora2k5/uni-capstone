"""The contract: the allowed destinations and cloud actions of one application.

A contract is a YAML file a person reviews and approves. The generator only drafts it from
recorded events; it never approves anything. Patterns may use `*` (e.g. "*.cdn.example"), but a
pattern that matches everything is rejected, because such a contract is not least-privilege.
"""
from __future__ import annotations

import fnmatch
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ..observe import ACTION, DOMAIN, normalise_domain, observations

CONTRACT_VERSION = 1
STATUSES = ("draft", "approved")
_HEADER = (
    "# Least-privilege contract, drafted from a recorded run. A person must review it before it is approved:\n"
    "# remove anything the application should not need, then run `leastpriv contract approve`.\n"
    "# 'evidence' only shows how often each item was seen in the recording; it is not enforced.\n"
)


class ContractError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _match(patterns: Iterable[str], value: str) -> bool:
    return any(fnmatch.fnmatchcase(value, p) for p in patterns)


@dataclass
class Contract:
    application: str
    allowed_domains: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    status: str = "draft"
    generated_at: str = ""
    approved_by: str | None = None
    approved_at: str | None = None
    source: dict = field(default_factory=dict)       # {"log_head": ..., "events": N}
    evidence: dict = field(default_factory=dict)     # {"domains": {...}, "actions": {...}}
    version: int = CONTRACT_VERSION

    def allows_domain(self, host: str) -> bool:
        return _match(self.allowed_domains, normalise_domain(host))

    def allows_action(self, action: str) -> bool:
        return _match(self.allowed_actions, action)

    def approve(self, by: str, now: str | None = None) -> None:
        if not by.strip():
            raise ContractError("approval needs the reviewer's name")
        self.status = "approved"
        self.approved_by = by.strip()
        self.approved_at = now or _now()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "application": self.application,
            "status": self.status,
            "generated_at": self.generated_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "source": self.source,
            "allowed_domains": list(self.allowed_domains),
            "allowed_actions": list(self.allowed_actions),
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: object, where: str = "contract") -> "Contract":
        if not isinstance(data, dict):
            raise ContractError(f"{where}: top level must be a mapping")
        if data.get("version") != CONTRACT_VERSION:
            raise ContractError(f"{where}: unsupported contract version {data.get('version')!r} (this release reads {CONTRACT_VERSION})")
        app = data.get("application")
        if not isinstance(app, str) or not app:
            raise ContractError(f"{where}: 'application' is required")
        status = data.get("status", "draft")
        if status not in STATUSES:
            raise ContractError(f"{where}: status must be one of {STATUSES}")
        lists = {}
        for key in ("allowed_domains", "allowed_actions"):
            val = data.get(key) or []
            if not isinstance(val, list) or not all(isinstance(v, str) and v.strip() for v in val):
                raise ContractError(f"{where}: '{key}' must be a list of non-empty strings")
            for v in val:
                if v.strip() in ("*", "*:*"):
                    raise ContractError(f"{where}: '{v}' in {key} matches everything; a contract must list specific items")
            lists[key] = [v.strip() for v in val]
        if status == "approved" and not data.get("approved_by"):
            raise ContractError(f"{where}: an approved contract must name who approved it")
        return cls(
            application=app, status=status,
            allowed_domains=[normalise_domain(d) for d in lists["allowed_domains"]],
            allowed_actions=lists["allowed_actions"],
            generated_at=str(data.get("generated_at") or ""),
            approved_by=data.get("approved_by"), approved_at=data.get("approved_at"),
            source=data.get("source") or {}, evidence=data.get("evidence") or {},
            version=CONTRACT_VERSION,
        )


def generate(records: Iterable[dict], application: str, log_head: str | None = None,
             now: str | None = None) -> Contract:
    """Merge and de-duplicate the observed destinations and actions into a draft contract."""
    domains: Counter = Counter()
    actions: Counter = Counter()
    events = 0
    for rec in records:
        events += 1
        for kind, value in observations(rec):
            (domains if kind == DOMAIN else actions)[value] += 1
    return Contract(
        application=application,
        allowed_domains=sorted(domains),
        allowed_actions=sorted(actions),
        status="draft",
        generated_at=now or _now(),
        source={"log_head": log_head, "events": events},
        evidence={"domains": dict(sorted(domains.items())), "actions": dict(sorted(actions.items()))},
    )


def _yaml():
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise ContractError("PyYAML is required for contract files: pip install pyyaml") from exc
    return yaml


def dump(contract: Contract, path: str | Path) -> None:
    yaml = _yaml()
    text = yaml.safe_dump(contract.to_dict(), sort_keys=False, default_flow_style=False, allow_unicode=True)
    Path(path).write_text(_HEADER + text, encoding="utf-8")


def load(path: str | Path) -> Contract:
    yaml = _yaml()
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"{path}: not valid YAML: {exc}") from exc
    return Contract.from_dict(data, where=str(path))
