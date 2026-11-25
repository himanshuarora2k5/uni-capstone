"""What counts as an observed destination or cloud action.

One place defines this, so the contract generator and the drift watcher can never disagree.
Both read the OCSF-shaped event produced by the log engine:

    destination  <-  dst_endpoint.hostname
    cloud action <-  api.service.name + ":" + api.operation      (e.g. "s3:GetObject")
"""
from __future__ import annotations

from .engine.normalise import get_path

DOMAIN = "domain"
ACTION = "cloud_action"


def normalise_domain(host: str) -> str:
    return host.strip().lower().rstrip(".")


def observations(record: dict) -> list[tuple[str, str]]:
    """Return [(kind, value), ...] found in one stored record."""
    event = record.get("event", {}) if isinstance(record, dict) else {}
    found: list[tuple[str, str]] = []
    host = get_path(event, "dst_endpoint.hostname")
    if isinstance(host, str) and host.strip():
        found.append((DOMAIN, normalise_domain(host)))
    service = get_path(event, "api.service.name")
    operation = get_path(event, "api.operation")
    if isinstance(service, str) and isinstance(operation, str) and service and operation:
        found.append((ACTION, f"{service.strip().lower()}:{operation.strip()}"))
    return found
