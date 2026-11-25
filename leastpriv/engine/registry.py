"""Format registry.

A format is described entirely by data: a regular expression (or a set of required JSON keys)
plus a mapping from OCSF attribute paths to value templates. Supporting a new log format means
adding one JSON file to a registry folder; no parser code changes.

Format file (one object, or {"formats": [ ... ]}):

    {
      "name": "apache_error",                  # lower-case letters, digits, underscore
      "description": "free text",
      "order": 60,                             # lower numbers are tried first (default 100)
      "type": "regex",                         # "regex" (default) or "json"
      "pattern": "^\\[(?P<time>[^\\]]+)\\] ...",   # regex: named groups are the template fields
      "require": ["eventSource"],              # json: keys that must be present (dotted paths)
      "mapping": {
        "metadata.original_time": "{time}",    # attribute path -> template
        "actor.process.pid": {"value": "{pid}", "type": "int"}
      }
    }

A mapping value is either a template string or an object with: value (template, required),
type ("str" or "int"), strip_suffix (removed if present), map (exact-value replacements).
If a template refers to a missing field, or an int conversion fails, that attribute is left out
of the event; the event itself is never dropped.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.\-]+)\}")
_NAME = re.compile(r"^[a-z0-9_]+$")
_ATTR = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$")
_RULE_KEYS = {"value", "type", "strip_suffix", "map"}
_FORMAT_KEYS = {"name", "description", "order", "type", "pattern", "require", "mapping"}


class RegistryError(ValueError):
    """A format file is invalid. The message names the file and the problem."""


@dataclass(frozen=True)
class Rule:
    template: str
    type: str = "str"
    strip_suffix: str | None = None
    value_map: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Format:
    name: str
    kind: str                               # "regex" or "json"
    mapping: dict[str, Rule]
    order: int = 100
    pattern: re.Pattern | None = None
    require: tuple[str, ...] = ()
    description: str = ""
    source: str = ""                        # file the format was loaded from


@dataclass(frozen=True)
class Registry:
    formats: tuple[Format, ...]

    def names(self) -> list[str]:
        return [f.name for f in self.formats]

    def get(self, name: str) -> Format:
        for f in self.formats:
            if f.name == name:
                return f
        raise KeyError(name)


def default_registry_dir() -> Path:
    """Folder with the formats that ship with the package."""
    return Path(__file__).resolve().parent.parent / "formats"


def _fail(source: str, name: str | None, msg: str) -> RegistryError:
    where = f"{source}" + (f" (format '{name}')" if name else "")
    return RegistryError(f"{where}: {msg}")


def _parse_rule(source: str, name: str, attr: str, raw) -> Rule:
    if isinstance(raw, str):
        return Rule(template=raw)
    if not isinstance(raw, dict):
        raise _fail(source, name, f"mapping '{attr}' must be a string or an object")
    unknown = set(raw) - _RULE_KEYS
    if unknown:
        raise _fail(source, name, f"mapping '{attr}' has unknown keys {sorted(unknown)}")
    if not isinstance(raw.get("value"), str):
        raise _fail(source, name, f"mapping '{attr}' needs a 'value' template")
    typ = raw.get("type", "str")
    if typ not in ("str", "int"):
        raise _fail(source, name, f"mapping '{attr}': type must be 'str' or 'int'")
    suffix = raw.get("strip_suffix")
    if suffix is not None and not isinstance(suffix, str):
        raise _fail(source, name, f"mapping '{attr}': strip_suffix must be a string")
    vmap = raw.get("map", {})
    if not isinstance(vmap, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in vmap.items()):
        raise _fail(source, name, f"mapping '{attr}': map must be an object of strings")
    return Rule(template=raw["value"], type=typ, strip_suffix=suffix, value_map=tuple(sorted(vmap.items())))


def _parse_format(source: str, obj) -> Format:
    if not isinstance(obj, dict):
        raise _fail(source, None, "a format must be a JSON object")
    name = obj.get("name")
    if not isinstance(name, str) or not _NAME.match(name):
        raise _fail(source, None, "'name' is required (lower-case letters, digits, underscore)")
    unknown = set(obj) - _FORMAT_KEYS
    if unknown:
        raise _fail(source, name, f"unknown keys {sorted(unknown)}")
    kind = obj.get("type", "regex")
    if kind not in ("regex", "json"):
        raise _fail(source, name, "'type' must be 'regex' or 'json'")
    order = obj.get("order", 100)
    if not isinstance(order, int) or isinstance(order, bool):
        raise _fail(source, name, "'order' must be an integer")

    pattern = None
    require: tuple[str, ...] = ()
    if kind == "regex":
        pat = obj.get("pattern")
        if not isinstance(pat, str):
            raise _fail(source, name, "a regex format needs a 'pattern'")
        try:
            pattern = re.compile(pat)
        except re.error as exc:
            raise _fail(source, name, f"pattern does not compile: {exc}") from exc
    else:
        req = obj.get("require")
        if not isinstance(req, list) or not req or not all(isinstance(r, str) for r in req):
            raise _fail(source, name, "a json format needs a non-empty 'require' list of key paths")
        require = tuple(req)

    raw_map = obj.get("mapping")
    if not isinstance(raw_map, dict) or not raw_map:
        raise _fail(source, name, "'mapping' must be a non-empty object")
    mapping: dict[str, Rule] = {}
    for attr, raw in raw_map.items():
        if not _ATTR.match(attr):
            raise _fail(source, name, f"'{attr}' is not a valid attribute path")
        rule = _parse_rule(source, name, attr, raw)
        if kind == "regex":
            for field in PLACEHOLDER.findall(rule.template):
                if field not in pattern.groupindex:
                    raise _fail(source, name, f"mapping '{attr}' uses {{{field}}} but the pattern has no such group")
        mapping[attr] = rule
    attrs = sorted(mapping)
    for a in attrs:
        for b in attrs:
            if a != b and b.startswith(a + "."):
                raise _fail(source, name, f"'{a}' and '{b}' conflict (one is a prefix of the other)")
    return Format(name=name, kind=kind, mapping=mapping, order=order, pattern=pattern,
                  require=require, description=str(obj.get("description", "")), source=source)


def _load_file(path: Path) -> list[Format]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _fail(str(path), None, f"not valid JSON: {exc}") from exc
    items = data["formats"] if isinstance(data, dict) and "formats" in data else [data]
    if not isinstance(items, list):
        raise _fail(str(path), None, "'formats' must be a list")
    return [_parse_format(str(path), item) for item in items]


def load_registry(*locations: str | Path) -> Registry:
    """Load formats from folders (every *.json inside) and/or single JSON files.

    Later locations override earlier ones when they define a format with the same name, so a
    team member can shadow a shipped format without editing it. Two files in the same location
    that define the same name are an error.
    """
    by_name: dict[str, Format] = {}
    for loc in locations:
        loc = Path(loc)
        if loc.is_dir():
            files: Iterable[Path] = sorted(loc.glob("*.json"))
        elif loc.is_file():
            files = [loc]
        else:
            raise RegistryError(f"{loc}: no such file or folder")
        seen_here: dict[str, str] = {}
        for f in files:
            for fmt in _load_file(f):
                if fmt.name in seen_here:
                    raise RegistryError(f"format '{fmt.name}' is defined in both {seen_here[fmt.name]} and {f}")
                seen_here[fmt.name] = str(f)
                by_name[fmt.name] = fmt
    ordered = sorted(by_name.values(), key=lambda f: (f.order, f.name))
    return Registry(formats=tuple(ordered))
