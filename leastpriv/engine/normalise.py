"""Normaliser: raw event text -> record {"format", "event", "raw"}.

The parser tries each registered format in order. A line that matches none goes to the fallback
format, which keeps the raw text and sets it as the message, so no event is dropped. The raw text
is always stored beside the normalised event.
"""
from __future__ import annotations

import json
from typing import Any

from .registry import PLACEHOLDER, Format, Registry, Rule

FALLBACK = "fallback"


def get_path(obj: Any, path: str) -> Any:
    """Follow a dotted path through dicts (key) and lists (integer index). Missing -> None."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
        if cur is None:
            return None
    return cur


def set_path(target: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = target
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _scalar(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return None


def _render(rule: Rule, lookup) -> Any:
    """Fill a template. Returns None when a field is missing or a conversion fails."""
    missing = False

    def sub(match):
        nonlocal missing
        val = _scalar(lookup(match.group(1)))
        if val is None or val == "":
            missing = True
            return ""
        return val

    text = PLACEHOLDER.sub(sub, rule.template)
    if missing:
        return None
    if rule.strip_suffix and text.endswith(rule.strip_suffix):
        text = text[: -len(rule.strip_suffix)]
    if rule.value_map:
        text = dict(rule.value_map).get(text, text)
    if rule.type == "int":
        try:
            return int(text)
        except ValueError:
            return None
    return text


class Normaliser:
    def __init__(self, registry: Registry):
        self.registry = registry

    def _try(self, fmt: Format, raw: str) -> dict | None:
        if fmt.kind == "regex":
            m = fmt.pattern.match(raw)
            if not m:
                return None
            lookup = m.groupdict().get
        else:
            if not raw.lstrip().startswith("{"):
                return None
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if not isinstance(doc, dict) or any(get_path(doc, p) is None for p in fmt.require):
                return None

            def lookup(path, _doc=doc):
                return get_path(_doc, path)

        event: dict = {}
        for attr, rule in fmt.mapping.items():
            value = _render(rule, lookup)
            if value is not None:
                set_path(event, attr, value)
        return event

    def normalise(self, raw: str) -> dict:
        raw = raw.rstrip("\r\n")
        for fmt in self.registry.formats:
            event = self._try(fmt, raw)
            if event is not None:
                return {"format": fmt.name, "event": event, "raw": raw}
        return {"format": FALLBACK, "event": {"message": raw}, "raw": raw}
