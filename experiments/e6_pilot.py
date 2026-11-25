"""E6 pilot: how much does each test-traffic source add to outbound-domain coverage?

ShopApp-mini serves six routes and makes four outbound calls to reserved `.example` hosts. Its
outbound lookups are recorded in-process (Python audit hook) as a stand-in for the egress proxy.
Four settings:  tests only | crawler only | tests + crawler | tests + crawler + user-added requests.

    coverage C = |S ∩ E| / |E| × 100%      S = domains seen, E = the four expected domains

We wrote both the application and the traffic sources, so this pilot only illustrates the
measurement; it does not estimate coverage in real applications.

    python -m experiments.e6_pilot
"""
from __future__ import annotations

import argparse
import json
import sys

from leastpriv.demo import traffic
from leastpriv.demo.shopapp_mini import EXPECTED_DOMAINS, ShopApp
from leastpriv.recorder import AuditRecorder

SETTINGS = (
    ("Test requests only", ("tests",)),
    ("Crawler only", ("crawl",)),
    ("Tests and crawler", ("tests", "crawl")),
    ("Tests, crawler and user-added requests", ("tests", "crawl", "user")),
)
_STEPS = {"tests": traffic.run_tests, "crawl": traffic.crawl, "user": traffic.user_added}


def run_setting(steps: tuple[str, ...]) -> set[str]:
    with ShopApp() as app, AuditRecorder("shopapp-mini") as rec:
        for s in steps:
            _STEPS[s](app.base_url)
        return rec.domains_seen()


def coverage(seen: set[str], expected=EXPECTED_DOMAINS) -> float:
    return 100.0 * len(seen & set(expected)) / len(expected)


def run() -> list[dict]:
    rows = []
    for label, steps in SETTINGS:
        seen = run_setting(steps)
        rows.append({"setting": label, "seen": sorted(seen),
                     "found": len(seen & EXPECTED_DOMAINS), "expected": len(EXPECTED_DOMAINS),
                     "coverage_percent": coverage(seen)})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rows = run()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"{'Setting':<42} {'Domains seen':<44} Coverage")
    for r in rows:
        names = ", ".join(d.split(".")[0] for d in r["seen"]) or "-"
        print(f"{r['setting']:<42} {names:<44} {r['coverage_percent']:.0f}% ({r['found']} of {r['expected']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
