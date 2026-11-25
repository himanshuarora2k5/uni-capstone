import json
import unittest

from leastpriv.engine import Normaliser, RegistryError, default_registry_dir, iter_raw_events, load_registry
from leastpriv.pipeline import build_registry, ingest
from leastpriv.integrity import read_entries

from .helpers import SAMPLES, TmpCase


class ShippedFormats(unittest.TestCase):
    def setUp(self):
        self.norm = Normaliser(load_registry(default_registry_dir()))

    def test_shipped_formats_load_in_order(self):
        reg = load_registry(default_registry_dir())
        self.assertTrue({"egress_proxy", "cloudtrail", "syslog_bsd", "apache_error"} <= set(reg.names()))
        orders = [f.order for f in reg.formats]
        self.assertEqual(orders, sorted(orders))

    def test_syslog_with_pid(self):
        rec = self.norm.normalise("Jun 14 15:16:01 combo sshd(pam_unix)[19939]: authentication failure; uid=0")
        self.assertEqual(rec["format"], "syslog_bsd")
        self.assertEqual(rec["event"], {
            "metadata": {"original_time": "Jun 14 15:16:01"},
            "device": {"hostname": "combo"},
            "actor": {"process": {"name": "sshd(pam_unix)", "pid": 19939}},
            "message": "authentication failure; uid=0",
        })

    def test_syslog_single_digit_day_and_no_pid(self):
        rec = self.norm.normalise("Jun  9 06:07:04 combo cron: job done")
        self.assertEqual(rec["format"], "syslog_bsd")
        self.assertEqual(rec["event"]["metadata"]["original_time"], "Jun 9 06:07:04")
        self.assertNotIn("pid", rec["event"]["actor"]["process"])

    def test_syslog_process_tag_may_contain_a_space(self):
        rec = self.norm.normalise("Jun  9 06:07:04 combo syslogd 1.4.1: restart.")
        self.assertEqual(rec["format"], "syslog_bsd")
        self.assertEqual(rec["event"]["actor"]["process"]["name"], "syslogd 1.4.1")
        self.assertEqual(rec["event"]["message"], "restart.")

    def test_apache_error(self):
        rec = self.norm.normalise("[Thu Jun 09 06:07:04 2005] [notice] LDAP: Built with OpenLDAP LDAP SDK")
        self.assertEqual(rec["format"], "apache_error")
        self.assertEqual(rec["event"]["severity"], "notice")
        self.assertEqual(rec["event"]["metadata"]["original_time"], "Thu Jun 09 06:07:04 2005")
        self.assertEqual(rec["event"]["message"], "LDAP: Built with OpenLDAP LDAP SDK")

    def test_proxy_line(self):
        rec = self.norm.normalise("2026-01-01T00:00:01.120Z shopapp-mini CONNECT images.shopapp.example:443 recorded")
        self.assertEqual(rec["format"], "egress_proxy")
        self.assertEqual(rec["event"]["dst_endpoint"], {"hostname": "images.shopapp.example", "port": 443})
        self.assertEqual(rec["event"]["actor"]["process"]["name"], "shopapp-mini")

    def test_proxy_line_without_port_keeps_event_and_drops_only_the_port(self):
        rec = self.norm.normalise("2026-01-01T00:00:01Z app CONNECT host.example:- recorded")
        self.assertEqual(rec["format"], "egress_proxy")
        self.assertEqual(rec["event"]["dst_endpoint"], {"hostname": "host.example"})

    def test_cloudtrail_record(self):
        raw = json.dumps({"eventTime": "2026-01-01T00:00:01Z", "eventSource": "s3.amazonaws.com",
                          "eventName": "GetObject", "awsRegion": "ap-south-1",
                          "userIdentity": {"arn": "arn:aws:sts::000000000000:assumed-role/x/y"}})
        rec = self.norm.normalise(raw)
        self.assertEqual(rec["format"], "cloudtrail")
        self.assertEqual(rec["event"]["api"], {"service": {"name": "s3"}, "operation": "GetObject"})
        self.assertEqual(rec["event"]["actor"]["user"]["uid"], "arn:aws:sts::000000000000:assumed-role/x/y")

    def test_json_without_required_keys_falls_back(self):
        rec = self.norm.normalise('{"hello": "world"}')
        self.assertEqual(rec["format"], "fallback")

    def test_fallback_keeps_raw_and_sets_message(self):
        rec = self.norm.normalise("this matches nothing\r\n")
        self.assertEqual(rec, {"format": "fallback", "event": {"message": "this matches nothing"},
                               "raw": "this matches nothing"})


class RegistryExtension(TmpCase):
    def test_new_format_needs_only_a_json_file(self):
        line = "ID=42 something happened"
        before = Normaliser(build_registry()).normalise(line)
        self.assertEqual(before["format"], "fallback")
        d = self.tmp / "extra"
        d.mkdir()
        (d / "myfmt.json").write_text(json.dumps({
            "name": "myfmt", "pattern": r"^ID=(?P<id>\d+) (?P<msg>.*)$",
            "mapping": {"actor.process.pid": {"value": "{id}", "type": "int"}, "message": "{msg}"}}))
        after = Normaliser(build_registry(d)).normalise(line)
        self.assertEqual(after["format"], "myfmt")
        self.assertEqual(after["event"], {"actor": {"process": {"pid": 42}}, "message": "something happened"})

    def test_later_location_overrides_shipped_format_by_name(self):
        f = self.write("override.json", json.dumps({
            "name": "apache_error", "pattern": r"^\[(?P<t>[^\]]+)\] \[(?P<l>[^\]]+)\] (?P<m>.*)$",
            "mapping": {"severity": "LEVEL={l}", "message": "{m}"}}))
        rec = Normaliser(build_registry(f)).normalise("[Thu Jun 09 06:07:04 2005] [notice] hi")
        self.assertEqual(rec["event"]["severity"], "LEVEL=notice")

    def test_formats_list_in_one_file(self):
        f = self.write("many.json", json.dumps({"formats": [
            {"name": "a_fmt", "pattern": "^A (?P<x>.*)$", "mapping": {"message": "{x}"}},
            {"name": "b_fmt", "pattern": "^B (?P<x>.*)$", "mapping": {"message": "{x}"}}]}))
        reg = load_registry(f)
        self.assertEqual(reg.names(), ["a_fmt", "b_fmt"])


class RegistryErrors(TmpCase):
    def check(self, obj, fragment):
        f = self.write("bad.json", obj if isinstance(obj, str) else json.dumps(obj))
        with self.assertRaises(RegistryError) as cm:
            load_registry(f)
        self.assertIn("bad.json", str(cm.exception))
        self.assertIn(fragment, str(cm.exception))

    def test_invalid_json(self):
        self.check("{not json", "not valid JSON")

    def test_pattern_does_not_compile(self):
        self.check({"name": "x", "pattern": "([", "mapping": {"message": "{m}"}}, "does not compile")

    def test_template_uses_missing_group(self):
        self.check({"name": "x", "pattern": "^(?P<a>.*)$", "mapping": {"message": "{b}"}}, "no such group")

    def test_unknown_key_is_reported(self):
        self.check({"name": "x", "pattern": "^(?P<a>.*)$", "mapping": {"message": "{a}"}, "paterns": 1}, "unknown keys")

    def test_bad_name(self):
        self.check({"name": "Bad Name", "pattern": "^(?P<a>.*)$", "mapping": {"message": "{a}"}}, "'name' is required")

    def test_prefix_conflict(self):
        self.check({"name": "x", "pattern": "^(?P<a>.*)$",
                    "mapping": {"actor": "{a}", "actor.process": "{a}"}}, "conflict")

    def test_bad_type(self):
        self.check({"name": "x", "pattern": "^(?P<a>.*)$",
                    "mapping": {"message": {"value": "{a}", "type": "float"}}}, "type must be")

    def test_json_format_needs_require(self):
        self.check({"name": "x", "type": "json", "mapping": {"message": "{a}"}}, "needs a non-empty 'require'")

    def test_duplicate_name_in_one_folder(self):
        d = self.tmp / "dup"
        d.mkdir()
        fmt = {"name": "same", "pattern": "^(?P<a>.*)$", "mapping": {"message": "{a}"}}
        (d / "one.json").write_text(json.dumps(fmt))
        (d / "two.json").write_text(json.dumps(fmt))
        with self.assertRaises(RegistryError):
            load_registry(d)

    def test_missing_location(self):
        with self.assertRaises(RegistryError):
            load_registry(self.tmp / "nope")


class Sources(TmpCase):
    def test_cloudtrail_export_expands_to_records(self):
        p = self.write_json("ct.json", {"Records": [{"eventName": "A"}, {"eventName": "B"}]})
        self.assertEqual(list(iter_raw_events(p)), ['{"eventName":"A"}', '{"eventName":"B"}'])

    def test_blank_lines_are_skipped_and_counted(self):
        p = self.write("x.log", "one\n\n  \ntwo\n")
        stats: dict = {}
        self.assertEqual(list(iter_raw_events(p, stats)), ["one", "two"])
        self.assertEqual(stats["blank"], 2)

    def test_json_file_that_is_not_an_export_is_read_as_lines(self):
        p = self.write("odd.json", "not json at all\nsecond line\n")
        self.assertEqual(list(iter_raw_events(p)), ["not json at all", "second line"])


class IngestKeepsEveryEvent(TmpCase):
    def test_no_event_is_dropped_and_raw_is_kept(self):
        src = SAMPLES / "syslog_sample.log"
        n_lines = len([ln for ln in src.read_text().splitlines() if ln.strip()])
        log = self.tmp / "out.jsonl"
        stats = ingest([src], build_registry(), log)
        self.assertEqual(stats.events, n_lines)
        self.assertEqual(sum(stats.per_format.values()), n_lines)
        recs = [e["record"] for e in read_entries(log)]
        self.assertEqual([r["raw"] for r in recs], [ln for ln in src.read_text().splitlines() if ln.strip()])
        self.assertGreaterEqual(stats.fallback, 1)

    def test_only_apache_registered_sends_syslog_lines_to_fallback(self):
        only_apache = load_registry(default_registry_dir() / "apache_error.json")
        src = SAMPLES / "syslog_sample.log"
        stats = ingest([src], only_apache, self.tmp / "o.jsonl")
        self.assertEqual(stats.fallback, stats.events)


if __name__ == "__main__":
    unittest.main()
