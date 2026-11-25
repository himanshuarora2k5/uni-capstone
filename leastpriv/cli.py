"""Command line: python -m leastpriv <command> ...

Exit codes: 0 success / nothing found, 1 a finding (verification failed, drift found),
2 the command could not run (bad input, broken log when integrity was required).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .contract import Contract, ContractError, dump, generate, load
from .engine import RegistryError
from .integrity import ChainError, read_anchor, read_entries, verify
from .pipeline import build_registry, ingest
from .watcher import check_entries


def _anchor(args) -> str | None:
    if getattr(args, "anchor", None):
        return args.anchor.strip()
    if getattr(args, "anchor_file", None):
        return read_anchor(args.anchor_file)
    return None


def _add_anchor_args(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--anchor", help="expected head hash (kept outside the log store)")
    g.add_argument("--anchor-file", help="file holding the expected head hash")


def cmd_formats(args) -> int:
    reg = build_registry(*args.registry)
    for f in reg.formats:
        print(f"{f.order:>4}  {f.name:<14} {f.kind:<6} {f.source}")
    return 0


def cmd_ingest(args) -> int:
    reg = build_registry(*args.registry)
    stats = ingest(args.files, reg, args.log, anchor_out=args.anchor_out)
    print(f"ingested {stats.events} events into {args.log}")
    for name, n in sorted(stats.per_format.items()):
        print(f"  {name:<14} {n}")
    if stats.blank_lines_skipped:
        print(f"  ({stats.blank_lines_skipped} blank lines skipped)")
    print(f"chain head: {stats.head}")
    if args.anchor_out:
        print(f"anchor written to {args.anchor_out}  (keep it OUTSIDE the log store)")
    return 0


def cmd_verify(args) -> int:
    result = verify(args.log, anchor=_anchor(args))
    print(result)
    return 0 if result.ok else 1


def cmd_contract_generate(args) -> int:
    head = None
    if not args.skip_verify:
        res = verify(args.log, anchor=_anchor(args))
        if not res.ok:
            print(f"refusing to build a contract from a log that fails verification: {res}", file=sys.stderr)
            return 2
        head = res.head
    records = (e["record"] for e in read_entries(args.log))
    contract = generate(records, application=args.app, log_head=head)
    dump(contract, args.output)
    print(f"draft contract written to {args.output}: "
          f"{len(contract.allowed_domains)} domains, {len(contract.allowed_actions)} cloud actions")
    print("review it, then: python -m leastpriv contract approve", args.output, "--by 'Your Name'")
    return 0


def cmd_contract_approve(args) -> int:
    contract = load(args.file)
    contract.approve(args.by)
    dump(contract, args.file)
    print(f"{args.file}: approved by {contract.approved_by} at {contract.approved_at}")
    return 0


def cmd_contract_show(args) -> int:
    c = load(args.file)
    print(f"application: {c.application}   status: {c.status}"
          + (f" (by {c.approved_by})" if c.approved_by else ""))
    print(f"evidence: {c.source.get('events', '?')} events, log head {str(c.source.get('log_head'))[:16]}...")
    print("allowed domains:")
    for d in c.allowed_domains:
        print(f"  {d}   (seen {c.evidence.get('domains', {}).get(d, '-')}x)")
    print("allowed cloud actions:")
    for a in c.allowed_actions:
        print(f"  {a}   (seen {c.evidence.get('actions', {}).get(a, '-')}x)")
    return 0


def cmd_watch(args) -> int:
    contract = load(args.contract)
    if contract.status != "approved" and not args.allow_draft:
        print(f"{args.contract} is a draft. A person must approve it first "
              "(`contract approve`), or pass --allow-draft for a trial run.", file=sys.stderr)
        return 2
    res = verify(args.log, anchor=_anchor(args))
    if not res.ok:
        print(f"integrity check failed, so the log is not trusted: {res}", file=sys.stderr)
        return 2
    report = check_entries(contract, read_entries(args.log))
    if args.drift_out:
        with open(args.drift_out, "w", encoding="utf-8") as fh:
            for d in report.drift:
                fh.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps({"entries_checked": report.entries_checked, "counts": report.counts(),
                          "drift": [d.to_dict() for d in report.drift]}, indent=2))
    else:
        print(f"integrity: {res}")
        print(f"checked {report.entries_checked} events against contract '{contract.application}' ({contract.status})")
        if not report.has_drift:
            print("no drift")
        else:
            c = report.counts()
            print(f"DRIFT: {c['domain']} destination event(s), {c['cloud_action']} cloud-action event(s) outside the contract")
            for kind, value, n in report.unique():
                print(f"  {kind:<13} {value}   x{n}")
    return 1 if report.has_drift else 0


def cmd_demo(args) -> int:
    from .demo.scenario import run_demo
    run_demo(args.workdir)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="leastpriv", description=__doc__.split("\n\n")[0])
    p.add_argument("--version", action="version", version=f"leastpriv {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("formats", help="list the registered log formats")
    s.add_argument("--registry", action="append", default=[], metavar="PATH", help="extra registry folder or file")
    s.set_defaults(func=cmd_formats)

    s = sub.add_parser("ingest", help="normalise raw events and append them to a hash-chained log")
    s.add_argument("files", nargs="+")
    s.add_argument("--log", required=True, help="chained log file (JSON Lines); appended to if it exists")
    s.add_argument("--anchor-out", help="write the latest chain hash here (store it outside the log store)")
    s.add_argument("--registry", action="append", default=[], metavar="PATH", help="extra registry folder or file")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("verify", help="check the hash chain (and the anchor, if given)")
    s.add_argument("--log", required=True)
    _add_anchor_args(s)
    s.set_defaults(func=cmd_verify)

    c = sub.add_parser("contract", help="draft, approve and show contracts")
    csub = c.add_subparsers(dest="contract_command", required=True)
    s = csub.add_parser("generate", help="draft a contract from a verified log")
    s.add_argument("--log", required=True)
    s.add_argument("--app", required=True, help="application name")
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--skip-verify", action="store_true", help="do not verify the log first (not recommended)")
    _add_anchor_args(s)
    s.set_defaults(func=cmd_contract_generate)
    s = csub.add_parser("approve", help="mark a reviewed contract as approved")
    s.add_argument("file")
    s.add_argument("--by", required=True, help="reviewer's name")
    s.set_defaults(func=cmd_contract_approve)
    s = csub.add_parser("show", help="print a contract")
    s.add_argument("file")
    s.set_defaults(func=cmd_contract_show)

    s = sub.add_parser("watch", help="report events outside an approved contract (alert-only)")
    s.add_argument("--contract", required=True)
    s.add_argument("--log", required=True)
    s.add_argument("--drift-out", help="write drift events as JSON Lines")
    s.add_argument("--allow-draft", action="store_true", help="accept a contract that is not approved yet")
    s.add_argument("--json", action="store_true", help="print the report as JSON")
    _add_anchor_args(s)
    s.set_defaults(func=cmd_watch)

    s = sub.add_parser("demo", help="run the whole pipeline on the ShopApp-mini sample application")
    s.add_argument("--workdir", help="folder for the demo files (must be empty or not exist yet)")
    s.set_defaults(func=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (RegistryError, ContractError, ChainError, FileNotFoundError, NotADirectoryError, IsADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
