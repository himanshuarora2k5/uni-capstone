"""Turn an input file into raw events (strings) for the normaliser.

Text files give one raw event per non-blank line. A .json file that is a CloudTrail export
({"Records": [...]}) or a JSON list of objects gives one raw event per record, as compact JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def _compact(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def iter_raw_events(path: str | Path, stats: dict | None = None) -> Iterator[str]:
    """Yield raw events. `stats["blank"]` counts blank lines that were skipped."""
    path = Path(path)
    if stats is not None:
        stats.setdefault("blank", 0)
    if path.suffix.lower() == ".json":
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = None
        records = None
        if isinstance(doc, dict) and isinstance(doc.get("Records"), list):
            records = doc["Records"]
        elif isinstance(doc, list):
            records = doc
        if records is not None:
            for rec in records:
                yield _compact(rec)
            return
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                if stats is not None:
                    stats["blank"] += 1
                continue
            yield line
