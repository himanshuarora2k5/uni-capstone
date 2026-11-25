"""E3: does the hash-chained log detect tampering, and at what cost?

Detection (paper Table 3): build a chain of N records; make five scripted changes at one position;
two attackers; with and without an anchor  ->  20 verifications.

    edit-only attacker   changes the stored entries and leaves every stored hash as it was
    rewriting attacker   also recomputes position, link and hash for every entry from the change on

Changes: edit the record, delete it, swap it with the next one, insert a forged record,
cut off the last 10 records (truncate). Position 0-based: "at" is the index of the changed entry.

Timing (paper Table 4): events written per second with and without chaining (50,000 records),
and verification time for chains of 1,000 / 10,000 / 100,000 records; mean and range of N runs.
Timing numbers depend on the machine; run this on the machine you report in the paper.

    python -m experiments.e3_integrity                     # detection table only
    python -m experiments.e3_integrity --timing            # plus timing (takes a minute or two)
    python -m experiments.e3_integrity --source Linux_2k.log   # use real log lines as records
"""
from __future__ import annotations

import argparse
import copy
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

from leastpriv.engine import Normaliser
from leastpriv.integrity import ChainedLog, dump_entry, link_hash, verify
from leastpriv.integrity.chain import GENESIS
from leastpriv.pipeline import build_registry

CHANGES = ("edit", "delete", "swap", "insert", "truncate")
TRUNCATE_BY = 10
HAS_POSITION = ("edit", "delete", "swap", "insert")


def synthetic_lines(n: int) -> list[str]:
    return [f"Jun 14 15:16:{i % 60:02d} combo sshd(pam_unix)[{1000 + i % 9000}]: authentication failure; "
            f"logname= uid=0 euid=0 tty=NODEVssh ruser= rhost=10.0.{i % 255}.{i % 200}" for i in range(n)]


def make_records(n: int, source: str | None = None) -> list[dict]:
    if source:
        lines = [ln.rstrip("\n") for ln in Path(source).read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()][:n]
        if len(lines) < n:
            raise SystemExit(f"{source} has only {len(lines)} non-blank lines; {n} needed")
    else:
        lines = synthetic_lines(n)
    norm = Normaliser(build_registry())
    return [norm.normalise(ln) for ln in lines]


def build_chain(path: Path, records: list[dict]) -> str:
    with ChainedLog(path) as log:
        for r in records:
            log.append(r)
        return log.head


def _write(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(dump_entry(e) + "\n" for e in entries), encoding="utf-8")


def _recompute(entries: list[dict], start: int) -> None:
    prev = entries[start - 1]["hash"] if start > 0 else GENESIS
    for k in range(start, len(entries)):
        entries[k]["i"] = k
        entries[k]["prev"] = prev
        entries[k]["hash"] = link_hash(prev, entries[k]["record"])
        prev = entries[k]["hash"]


def tamper(entries: list[dict], change: str, at: int, rewriting: bool) -> list[dict]:
    e = copy.deepcopy(entries)
    if change == "edit":
        e[at]["record"]["event"]["message"] = e[at]["record"]["event"].get("message", "") + " (edited)"
    elif change == "delete":
        del e[at]
    elif change == "swap":
        e[at], e[at + 1] = e[at + 1], e[at]
    elif change == "insert":
        forged = {"format": "forged", "event": {"message": "forged record"}, "raw": "forged record"}
        e.insert(at, {"i": at, "prev": e[at - 1]["hash"], "record": forged, "hash": e[at]["hash"]})
    elif change == "truncate":
        e = e[:-TRUNCATE_BY]
    else:
        raise ValueError(change)
    if rewriting and change != "truncate":
        _recompute(e, at)
    return e


def detection(records: int = 1000, at: int | None = None, source: str | None = None) -> list[dict]:
    """Return one result row per (attacker, anchor)."""
    at = records // 2 if at is None else at
    recs = make_records(records, source)
    rows = []
    with tempfile.TemporaryDirectory(prefix="leastpriv-e3-") as tmp:
        base = Path(tmp) / "base.jsonl"
        head = build_chain(base, recs)
        entries = [json.loads(ln) for ln in base.read_text(encoding="utf-8").splitlines()]
        for attacker in ("edit-only", "rewriting"):
            for anchored in (False, True):
                detected, positioned = 0, 0
                per_change = {}
                for change in CHANGES:
                    p = Path(tmp) / f"{attacker}-{change}.jsonl"
                    _write(p, tamper(entries, change, at, rewriting=(attacker == "rewriting")))
                    res = verify(p, anchor=head if anchored else None)
                    hit = not res.ok
                    detected += hit
                    named = hit and res.bad_index == at and change in HAS_POSITION
                    positioned += named
                    per_change[change] = {"detected": hit, "bad_index": res.bad_index, "reason": res.reason}
                rows.append({"attacker": attacker, "anchor": anchored, "detected": detected, "m": len(CHANGES),
                             "position_correct": positioned, "position_possible": len(HAS_POSITION),
                             "per_change": per_change})
    return rows


def _fmt_range(vals: list[float], digits: int) -> str:
    return f"{statistics.mean(vals):,.{digits}f} ({min(vals):,.{digits}f} to {max(vals):,.{digits}f})"


def timing(runs: int = 5, write_n: int = 50_000, sizes=(1000, 10_000, 100_000), source: str | None = None) -> dict:
    recs = make_records(write_n, source) if source else make_records(write_n)
    out: dict = {"runs": runs}
    with tempfile.TemporaryDirectory(prefix="leastpriv-e3t-") as tmp:
        for label, chained in (("with chaining", True), ("without chaining", False)):
            rates = []
            for r in range(runs):
                p = Path(tmp) / f"w-{label[:4]}-{r}.jsonl"
                t0 = time.perf_counter()
                with ChainedLog(p, chained=chained) as log:
                    for rec in recs:
                        log.append(rec)
                rates.append(write_n / (time.perf_counter() - t0))
                p.unlink()
            out[f"events_per_second_{'chained' if chained else 'plain'}"] = rates
        for n in sizes:
            p = Path(tmp) / f"v-{n}.jsonl"
            build_chain(p, recs[:n] if n <= len(recs) else make_records(n))
            times = []
            for _ in range(runs):
                t0 = time.perf_counter()
                res = verify(p)
                times.append(time.perf_counter() - t0)
                assert res.ok
            out[f"verify_seconds_{n}"] = times
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--records", type=int, default=1000, help="chain length for the detection test (default 1000)")
    ap.add_argument("--source", help="text log whose first lines become the records (default: synthetic lines)")
    ap.add_argument("--timing", action="store_true", help="also run the timing measurements")
    ap.add_argument("--runs", type=int, default=5, help="repetitions for timing (default 5)")
    ap.add_argument("--json", action="store_true", help="print raw results as JSON")
    args = ap.parse_args(argv)

    rows = detection(args.records, source=args.source)
    result: dict = {"detection": rows}
    if args.timing:
        result["timing"] = timing(args.runs, source=args.source)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"E3 detection: {args.records}-record chain, changes at entry {args.records // 2}, "
          f"records from {'the given file' if args.source else 'synthetic syslog-style lines'}")
    print(f"{'Attacker':<11} {'Anchor':<7} {'Changes detected':<20} Position named correctly")
    for r in rows:
        pct = 100 * r["detected"] / r["m"]
        pos = ("not applicable" if r["detected"] == 0 else
               f"{r['position_correct']} of {r['position_possible']} changes that have a position")
        print(f"{r['attacker']:<11} {'Yes' if r['anchor'] else 'No':<7} "
              f"{r['detected']} of {r['m']} ({pct:.0f}%)".ljust(40) + f" {pos}")
    if args.timing:
        t = result["timing"]
        print(f"\nE3 timing: mean (min to max) of {t['runs']} runs")
        print("  machine:", platform.platform(), "| Python", platform.python_version(), "|", platform.processor() or platform.machine())
        print("  Events written per second, with chaining   ", _fmt_range(t["events_per_second_chained"], 0))
        print("  Events written per second, without chaining", _fmt_range(t["events_per_second_plain"], 0))
        for n in (1000, 10_000, 100_000):
            print(f"  Verification time, {n:>7,} records       ", _fmt_range(t[f"verify_seconds_{n}"], 4), "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
