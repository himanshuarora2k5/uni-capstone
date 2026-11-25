"""Hash-chained, append-only log (JSON Lines) with an optional external anchor.

Each stored entry is one line:  {"i": position, "prev": previous hash, "record": {...}, "hash": h}
with

    h_i = SHA-256( h_{i-1}  ||  c(r_i) )

where c(r) is the canonical JSON of the record (sorted keys, no spaces, UTF-8), `||` is
concatenation of the previous hash as its 64-character hex string and that JSON text, and
h_0 (the hash before the first entry) is 64 zeros.

What the chain does and does not give you (see docs/ARCHITECTURE.md):
  * editing, deleting, inserting or reordering an entry breaks the chain from that point;
  * cutting entries off the END of the log is not detectable from the log alone;
  * an attacker who recomputes every hash after a change is not detectable from the log alone;
  * both of the last two ARE detected if the latest hash (the anchor) is kept outside the log store.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

GENESIS = "0" * 64


class ChainError(Exception):
    pass


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def link_hash(prev: str, record: Any) -> str:
    return hashlib.sha256((prev + canonical_json(record)).encode("utf-8")).hexdigest()


def dump_entry(entry: dict) -> str:
    """The one-line JSON form of a stored entry (used by the writer and by the experiments)."""
    return json.dumps(entry, ensure_ascii=False, separators=(",", ":"))


class ChainedLog:
    """Append-only writer. Re-opening an existing log continues its chain.

    Re-opening does NOT re-verify the old entries; run `verify` for that. With chained=False the
    entries carry no hash fields (used only to measure the cost of chaining).
    """

    def __init__(self, path: str | Path, chained: bool = True):
        self.path = Path(path)
        self.chained = chained
        self._next = 0
        self._head = GENESIS
        if self.path.exists() and self.path.stat().st_size:
            last, count = None, 0
            with self.path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        last, count = line, count + 1
            if chained:
                try:
                    self._head = json.loads(last)["hash"]
                except (ValueError, KeyError, TypeError) as exc:
                    raise ChainError(f"{self.path}: last entry has no readable hash; cannot continue the chain") from exc
            self._next = count
        self._fh = self.path.open("a", encoding="utf-8", newline="\n")

    @property
    def head(self) -> str:
        return self._head

    def __len__(self) -> int:
        return self._next

    def append(self, record: dict) -> dict:
        if self.chained:
            h = link_hash(self._head, record)
            entry = {"i": self._next, "prev": self._head, "record": record, "hash": h}
            self._head = h
        else:
            entry = {"i": self._next, "record": record}
        self._fh.write(dump_entry(entry) + "\n")
        self._next += 1
        return entry

    def flush(self) -> None:
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "ChainedLog":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    entries: int                    # entries that passed the check
    head: str                       # hash of the last entry that passed (GENESIS if none)
    bad_index: int | None = None    # position of the first bad entry, when one can be named
    reason: str | None = None

    def __str__(self) -> str:
        if self.ok:
            return f"OK: {self.entries} entries, head {self.head[:16]}..."
        where = f"entry {self.bad_index}" if self.bad_index is not None else "chain head"
        return f"FAILED at {where}: {self.reason}"


def read_entries(path: str | Path) -> Iterator[dict]:
    """Yield stored entries without checking them. Call `verify` first if integrity matters."""
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def verify(path: str | Path, anchor: str | None = None) -> VerifyResult:
    """Walk the chain from the start; report the first entry whose position, link or hash is wrong.

    If an anchor (the expected head hash, stored outside the log) is given, also require that the
    head of the chain equals it. A head mismatch is reported without a position.
    """
    expected_prev = GENESIS
    count = 0
    with Path(path).open(encoding="utf-8") as fh:
        for idx, line in enumerate(fh):
            try:
                entry = json.loads(line)
            except ValueError:
                return VerifyResult(False, count, expected_prev, idx, "line is not valid JSON")
            if not (isinstance(entry, dict) and {"i", "prev", "record", "hash"} <= set(entry)):
                return VerifyResult(False, count, expected_prev, idx, "entry is missing a field")
            if entry["i"] != idx:
                return VerifyResult(False, count, expected_prev, idx,
                                    "position field does not match the entry's place in the log")
            if entry["prev"] != expected_prev:
                return VerifyResult(False, count, expected_prev, idx, "link to the previous entry does not match")
            if not isinstance(entry["hash"], str) or link_hash(entry["prev"], entry["record"]) != entry["hash"]:
                return VerifyResult(False, count, expected_prev, idx,
                                    "stored hash does not match the entry's content")
            expected_prev = entry["hash"]
            count += 1
    if anchor is not None and anchor.strip() != expected_prev:
        return VerifyResult(False, count, expected_prev, None, "head of the chain does not match the anchor")
    return VerifyResult(True, count, expected_prev)


def write_anchor(path: str | Path, head: str) -> None:
    Path(path).write_text(head + "\n", encoding="utf-8")


def read_anchor(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()
