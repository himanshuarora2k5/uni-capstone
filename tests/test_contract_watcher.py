import unittest

from leastpriv.contract import Contract, ContractError, dump, generate, load
from leastpriv.engine import Normaliser
from leastpriv.integrity import read_entries
from leastpriv.observe import observations
from leastpriv.pipeline import build_registry, ingest
from leastpriv.watcher import check_entries

from .helpers import SHOP, TmpCase

NOW = "2026-01-01T00:00:00Z"


def records(*raws):
    norm = Normaliser(build_registry())
    return [norm.normalise(r) for r in raws]


PROXY = "2026-01-01T00:00:01Z shopapp-mini CONNECT {host}:443 recorded"
CT = '{{"eventTime":"2026-01-01T00:00:01Z","eventSource":"{svc}.amazonaws.com","eventName":"{op}"}}'


class Observations(unittest.TestCase):
    def test_domain_and_action_are_extracted_and_normalised(self):
        r = records(PROXY.format(host="Images.ShopApp.Example."))[0]
        self.assertEqual(observations(r), [("domain", "images.shopapp.example")])
        r = records(CT.format(svc="S3", op="GetObject"))[0]
        self.assertEqual(observations(r), [("cloud_action", "s3:GetObject")])

    def test_events_without_either_give_nothing(self):
        self.assertEqual(observations(records("just text")[0]), [])


class Generation(unittest.TestCase):
    def setUp(self):
        self.recs = records(
            PROXY.format(host="payments.shopapp.example"),
            PROXY.format(host="images.shopapp.example"),
            PROXY.format(host="images.shopapp.example"),
            CT.format(svc="s3", op="GetObject"),
            "unrelated line",
        )

    def test_merge_dedupe_sort_and_count(self):
        c = generate(self.recs, "shopapp-mini", log_head="abc", now=NOW)
        self.assertEqual(c.allowed_domains, ["images.shopapp.example", "payments.shopapp.example"])
        self.assertEqual(c.allowed_actions, ["s3:GetObject"])
        self.assertEqual(c.evidence["domains"], {"images.shopapp.example": 2, "payments.shopapp.example": 1})
        self.assertEqual(c.source, {"log_head": "abc", "events": 5})
        self.assertEqual((c.status, c.generated_at), ("draft", NOW))

    def test_generation_is_deterministic_and_order_independent(self):
        a = generate(self.recs, "x", now=NOW).to_dict()
        b = generate(list(reversed(self.recs)), "x", now=NOW).to_dict()
        self.assertEqual(a, b)

    def test_empty_input_gives_an_empty_contract(self):
        c = generate([], "x", now=NOW)
        self.assertEqual((c.allowed_domains, c.allowed_actions), ([], []))


class ContractFile(TmpCase):
    def make(self):
        return generate(records(PROXY.format(host="images.shopapp.example"), CT.format(svc="s3", op="GetObject")),
                        "shopapp-mini", log_head="h", now=NOW)

    def test_roundtrip_and_review_header(self):
        p = self.tmp / "c.yaml"
        dump(self.make(), p)
        self.assertTrue(p.read_text().startswith("# Least-privilege contract, drafted from a recorded run"))
        self.assertEqual(load(p).to_dict(), self.make().to_dict())

    def test_approve_sets_reviewer_and_time(self):
        c = self.make()
        c.approve("  A. Reviewer ", now=NOW)
        self.assertEqual((c.status, c.approved_by, c.approved_at), ("approved", "A. Reviewer", NOW))
        p = self.tmp / "c.yaml"
        dump(c, p)
        self.assertEqual(load(p).status, "approved")

    def test_approval_needs_a_name(self):
        with self.assertRaises(ContractError):
            self.make().approve("   ")

    def test_patterns(self):
        c = Contract("a", allowed_domains=["*.cdn.example", "api.example"], allowed_actions=["s3:Get*", "sqs:SendMessage"])
        self.assertTrue(c.allows_domain("img.cdn.example"))
        self.assertTrue(c.allows_domain("API.example."))
        self.assertFalse(c.allows_domain("cdn.example"))
        self.assertFalse(c.allows_domain("evil.example"))
        self.assertTrue(c.allows_action("s3:GetObject"))
        self.assertFalse(c.allows_action("s3:PutObject"))
        self.assertTrue(c.allows_action("sqs:SendMessage"))

    def bad(self, text, fragment):
        p = self.write("bad.yaml", text)
        with self.assertRaises(ContractError) as cm:
            load(p)
        self.assertIn(fragment, str(cm.exception))

    def test_validation(self):
        self.bad("- just a list\n", "mapping")
        self.bad("version: 99\napplication: a\n", "unsupported contract version")
        self.bad("version: 1\n", "'application' is required")
        self.bad("version: 1\napplication: a\nstatus: maybe\n", "status must be")
        self.bad("version: 1\napplication: a\nallowed_domains: images.example\n", "list of non-empty strings")
        self.bad("version: 1\napplication: a\nallowed_domains: ['*']\n", "matches everything")
        self.bad("version: 1\napplication: a\nallowed_actions: ['*:*']\n", "matches everything")
        self.bad("version: 1\napplication: a\nstatus: approved\n", "must name who approved")
        self.bad("version: 1\napplication: [unclosed\n", "not valid YAML")


class Watcher(TmpCase):
    def test_drift_is_found_with_type_value_and_position(self):
        sandbox = self.tmp / "s.jsonl"
        ingest([SHOP / "sandbox_proxy.log", SHOP / "sandbox_cloudtrail.json"], build_registry(), sandbox)
        contract = generate((e["record"] for e in read_entries(sandbox)), "shopapp-mini", now=NOW)
        prod = self.tmp / "p.jsonl"
        ingest([SHOP / "prod_proxy.log", SHOP / "prod_cloudtrail.json"], build_registry(), prod)
        report = check_entries(contract, read_entries(prod))
        self.assertEqual(report.entries_checked, 6)
        self.assertEqual(report.counts(), {"domain": 2, "cloud_action": 1})
        self.assertEqual(report.unique(), [("cloud_action", "s3:PutObject", 1),
                                           ("domain", "analytics.shopapp.example", 1),
                                           ("domain", "notifications.shopapp.example", 1)])
        d = report.drift[0]
        self.assertEqual((d.type, d.value, d.index), ("domain", "analytics.shopapp.example", 2))
        self.assertIn("analytics.shopapp.example", d.raw)

    def test_no_drift_when_everything_is_covered(self):
        log = self.tmp / "s.jsonl"
        ingest([SHOP / "sandbox_proxy.log", SHOP / "sandbox_cloudtrail.json"], build_registry(), log)
        contract = generate((e["record"] for e in read_entries(log)), "x", now=NOW)
        report = check_entries(contract, read_entries(log))
        self.assertFalse(report.has_drift)
        self.assertEqual(report.entries_checked, 4)

    def test_wildcard_contract_covers_subdomains(self):
        log = self.tmp / "p.jsonl"
        ingest([SHOP / "prod_proxy.log"], build_registry(), log)
        c = Contract("x", allowed_domains=["*.shopapp.example"])
        self.assertFalse(check_entries(c, read_entries(log)).has_drift)


if __name__ == "__main__":
    unittest.main()
