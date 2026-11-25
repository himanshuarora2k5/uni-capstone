"""`leastpriv demo`: the whole pipeline on ShopApp-mini, using only the library functions.

  sandbox run  -> recorder -> log engine -> hash-chained log -> draft contract -> approval
  production   -> log engine -> hash-chained log -> drift watcher
  tampering    -> verifier (edit, then truncation with and without the anchor)

The CloudTrail records are written by this script as stand-ins for what CloudTrail would deliver
for a real sandbox identity (account id 000000000000 is fake). Nothing here touches AWS.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Callable

from ..contract import dump, generate, load
from ..integrity import read_anchor, read_entries, verify
from ..pipeline import build_registry, ingest
from ..recorder import AuditRecorder
from ..watcher import check_entries
from . import traffic
from .shopapp_mini import ShopApp

APP = "shopapp-mini"
_ROLE = "arn:aws:sts::000000000000:assumed-role/shopapp-sandbox/session"


def _cloudtrail(path: Path, actions: list[tuple[str, str]]) -> None:
    records = [{"eventTime": f"2026-01-01T00:00:{i:02d}Z", "eventSource": f"{svc}.amazonaws.com",
                "eventName": op, "awsRegion": "ap-south-1", "userIdentity": {"arn": _ROLE}}
               for i, (svc, op) in enumerate(actions)]
    path.write_text(json.dumps({"Records": records}, indent=2), encoding="utf-8")


def _prepare(workdir: str | Path | None) -> Path:
    if workdir is None:
        return Path(tempfile.mkdtemp(prefix="leastpriv-demo-"))
    wd = Path(workdir)
    if wd.exists() and any(wd.iterdir()):
        raise FileExistsError(f"{wd} is not empty; pick a new folder")
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def run_demo(workdir: str | Path | None = None, say: Callable[[str], None] = print) -> dict:
    wd = _prepare(workdir)
    (wd / "anchors").mkdir()            # stands for a place OUTSIDE the log store
    reg = build_registry()
    out: dict = {"workdir": str(wd)}

    say(f"Working folder: {wd}\n")

    # 1. sandbox run -------------------------------------------------------
    say("1. SANDBOX RUN  - ShopApp-mini gets test traffic (its own tests + a crawler)")
    proxy_log = wd / "sandbox_proxy.log"
    with ShopApp() as app, AuditRecorder(APP, proxy_log) as rec:
        traffic.run_tests(app.base_url)
        crawled = traffic.crawl(app.base_url)
    say(f"   crawler visited: {', '.join(crawled)}")
    say(f"   recorder saw {len(rec.domains_seen())} outbound destinations: {', '.join(sorted(rec.domains_seen()))}")
    ct_log = wd / "sandbox_cloudtrail.json"
    _cloudtrail(ct_log, [("s3", "GetObject")])
    say("   cloud actions (synthetic CloudTrail stand-in): s3:GetObject\n")

    # 2. log engine + chain -------------------------------------------------
    say("2. LOG ENGINE - normalise to OCSF-shaped events, store in a hash-chained log")
    sandbox_chain = wd / "sandbox.chain.jsonl"
    stats = ingest([proxy_log, ct_log], reg, sandbox_chain, anchor_out=wd / "anchors" / "sandbox.anchor")
    say(f"   {stats.events} events: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.per_format.items())))
    say(f"   {verify(sandbox_chain, anchor=read_anchor(wd / 'anchors' / 'sandbox.anchor'))}\n")

    # 3. contract -----------------------------------------------------------
    say("3. CONTRACT - draft from the verified log, a person reviews and approves")
    res = verify(sandbox_chain)
    contract = generate((e["record"] for e in read_entries(sandbox_chain)), APP, log_head=res.head)
    cpath = wd / "contract.yaml"
    dump(contract, cpath)
    say(f"   allowed domains: {contract.allowed_domains}")
    say(f"   allowed actions: {contract.allowed_actions}")
    say("   (the two routes no page links to were never visited, so analytics and notifications are NOT in the draft)")
    contract.approve("demo reviewer")
    dump(contract, cpath)
    say(f"   approved by '{contract.approved_by}'\n")

    # 4. production + watcher ----------------------------------------------
    say("4. PRODUCTION - the same app now also receives real-user traffic; the watcher compares with the contract")
    prod_proxy = wd / "prod_proxy.log"
    with ShopApp() as app, AuditRecorder(APP, prod_proxy):
        traffic.run_tests(app.base_url)
        traffic.crawl(app.base_url)
        traffic.user_added(app.base_url)
    prod_ct = wd / "prod_cloudtrail.json"
    _cloudtrail(prod_ct, [("s3", "GetObject"), ("s3", "PutObject")])
    prod_chain = wd / "prod.chain.jsonl"
    ingest([prod_proxy, prod_ct], reg, prod_chain, anchor_out=wd / "anchors" / "prod.anchor")
    report = check_entries(load(cpath), read_entries(prod_chain))
    say(f"   checked {report.entries_checked} events -> {len(report.drift)} drift event(s)")
    for kind, value, n in report.unique():
        say(f"   DRIFT  {kind:<13} {value}   x{n}")
    out["drift"] = [(k, v) for k, v, _ in report.unique()]
    say("")

    # 5. tampering ---------------------------------------------------------
    say("5. TAMPERING - an attacker with write access to the log store tries to hide the drift")
    anchor = read_anchor(wd / "anchors" / "prod.anchor")
    lines = prod_chain.read_text(encoding="utf-8").splitlines()
    edited = list(lines)
    for i, ln in enumerate(edited):
        if "analytics.shopapp.example" in ln:
            edited[i] = ln.replace("analytics.shopapp.example", "images.shopapp.example")
            break
    p_edit = wd / "prod.edited.jsonl"
    p_edit.write_text("\n".join(edited) + "\n", encoding="utf-8")
    r1 = verify(p_edit)
    say(f"   (a) renamed the analytics destination in the log:   {r1}")
    p_cut = wd / "prod.truncated.jsonl"
    p_cut.write_text("\n".join(lines[:-2]) + "\n", encoding="utf-8")
    r2, r3 = verify(p_cut), verify(p_cut, anchor=anchor)
    say(f"   (b) cut off the last 2 entries, no anchor:           {r2}   <- NOT detected by the chain alone")
    say(f"   (c) same truncation, with the anchor from outside:   {r3}")
    out.update(edit_detected=not r1.ok, truncation_without_anchor_detected=not r2.ok,
               truncation_with_anchor_detected=not r3.ok)
    say("\nDone. Files are in the working folder; try:  python -m leastpriv contract show "
        f"{cpath}")
    return out
