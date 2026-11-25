import contextlib
import io
import json
import unittest

from leastpriv.cli import main

from .helpers import SHOP, TmpCase, read_lines, write_lines


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


class Cli(TmpCase):
    def ingest(self, name, *files, anchor=None):
        log = self.tmp / f"{name}.jsonl"
        args = ["ingest", *files, "--log", log]
        if anchor:
            args += ["--anchor-out", anchor]
        code, out, _ = run(*args)
        self.assertEqual(code, 0, out)
        return log

    def test_walking_skeleton(self):
        sandbox = self.ingest("sandbox", SHOP / "sandbox_proxy.log", SHOP / "sandbox_cloudtrail.json",
                              anchor=self.tmp / "sandbox.anchor")
        self.assertEqual(run("verify", "--log", sandbox, "--anchor-file", self.tmp / "sandbox.anchor")[0], 0)

        contract = self.tmp / "contract.yaml"
        code, out, _ = run("contract", "generate", "--log", sandbox, "--app", "shopapp-mini", "-o", contract)
        self.assertEqual(code, 0)
        self.assertIn("2 domains, 1 cloud actions", out)

        prod = self.ingest("prod", SHOP / "prod_proxy.log", SHOP / "prod_cloudtrail.json")
        # a draft contract is refused
        code, _, err = run("watch", "--contract", contract, "--log", prod)
        self.assertEqual(code, 2)
        self.assertIn("draft", err)
        # approve, then watch: drift => exit 1
        self.assertEqual(run("contract", "approve", contract, "--by", "Reviewer")[0], 0)
        drift_out = self.tmp / "drift.jsonl"
        code, out, _ = run("watch", "--contract", contract, "--log", prod, "--drift-out", drift_out)
        self.assertEqual(code, 1)
        self.assertIn("analytics.shopapp.example", out)
        self.assertEqual(len(read_lines(drift_out)), 3)
        # the sandbox log itself is clean against its own contract
        self.assertEqual(run("watch", "--contract", contract, "--log", sandbox)[0], 0)
        code, out, _ = run("contract", "show", contract)
        self.assertEqual(code, 0)
        self.assertIn("approved (by Reviewer)", out)

    def test_watch_json_output(self):
        sandbox = self.ingest("s", SHOP / "sandbox_proxy.log")
        contract = self.tmp / "c.yaml"
        run("contract", "generate", "--log", sandbox, "--app", "a", "-o", contract)
        prod = self.ingest("p", SHOP / "prod_proxy.log")
        code, out, _ = run("watch", "--contract", contract, "--log", prod, "--allow-draft", "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["counts"], {"domain": 2, "cloud_action": 0})

    def test_tampered_log_is_not_trusted(self):
        sandbox = self.ingest("s", SHOP / "sandbox_proxy.log")
        contract = self.tmp / "c.yaml"
        run("contract", "generate", "--log", sandbox, "--app", "a", "-o", contract)
        prod = self.ingest("p", SHOP / "prod_proxy.log")
        lines = read_lines(prod)
        lines[2] = lines[2].replace("analytics.shopapp.example", "images.shopapp.example")
        write_lines(prod, lines)
        code, out, _ = run("verify", "--log", prod)
        self.assertEqual(code, 1)
        self.assertIn("FAILED at entry 2", out)
        code, _, err = run("watch", "--contract", contract, "--log", prod, "--allow-draft")
        self.assertEqual(code, 2)
        self.assertIn("integrity check failed", err)

    def test_contract_is_not_built_from_a_broken_log(self):
        log = self.ingest("s", SHOP / "sandbox_proxy.log")
        lines = read_lines(log)
        write_lines(log, lines[:1] + ["{garbage"] + lines[2:])
        code, _, err = run("contract", "generate", "--log", log, "--app", "a", "-o", self.tmp / "c.yaml")
        self.assertEqual(code, 2)
        self.assertIn("fails verification", err)

    def test_anchor_catches_truncation_through_the_cli(self):
        log = self.ingest("s", SHOP / "prod_proxy.log", anchor=self.tmp / "s.anchor")
        write_lines(log, read_lines(log)[:-1])
        self.assertEqual(run("verify", "--log", log)[0], 0)
        self.assertEqual(run("verify", "--log", log, "--anchor-file", self.tmp / "s.anchor")[0], 1)

    def test_extra_registry_and_formats_command(self):
        extra = self.write("extra/myfmt.json", json.dumps(
            {"name": "myfmt", "pattern": "^X (?P<m>.*)$", "mapping": {"message": "{m}"}}))
        code, out, _ = run("formats", "--registry", extra.parent)
        self.assertEqual(code, 0)
        for name in ("egress_proxy", "cloudtrail", "syslog_bsd", "apache_error", "myfmt"):
            self.assertIn(name, out)

    def test_bad_input_gives_exit_2_not_a_traceback(self):
        code, _, err = run("ingest", self.tmp / "missing.log", "--log", self.tmp / "o.jsonl")
        self.assertEqual(code, 2)
        self.assertIn("error:", err)
        code, _, err = run("formats", "--registry", self.tmp / "nope")
        self.assertEqual(code, 2)

    def test_demo_command(self):
        code, out, _ = run("demo", "--workdir", self.tmp / "d")
        self.assertEqual(code, 0)
        self.assertIn("TAMPERING", out)


if __name__ == "__main__":
    unittest.main()
