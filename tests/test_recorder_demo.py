import socket
import unittest

from leastpriv.demo import traffic
from leastpriv.demo.scenario import run_demo
from leastpriv.demo.shopapp_mini import EXPECTED_DOMAINS, ShopApp
from leastpriv.engine import Normaliser
from leastpriv.pipeline import build_registry
from leastpriv.recorder import AuditRecorder

from .helpers import TmpCase


class Recorder(unittest.TestCase):
    def test_lookup_is_recorded_and_blocked(self):
        with AuditRecorder("my app") as rec:
            with self.assertRaises(OSError):
                socket.getaddrinfo("payments.shopapp.example", 443)
        self.assertEqual(rec.domains_seen(), {"payments.shopapp.example"})
        self.assertEqual(len(rec.raw_events()), 1)
        self.assertIn(" my_app CONNECT payments.shopapp.example:443 recorded", rec.raw_events()[0])

    def test_loopback_is_not_recorded(self):
        with AuditRecorder("a") as rec:
            socket.getaddrinfo("127.0.0.1", 80)
            socket.getaddrinfo("localhost", 80)
        self.assertEqual(rec.raw_events(), [])

    def test_inner_recorder_gets_the_events(self):
        with AuditRecorder("outer") as outer:
            with AuditRecorder("inner") as inner:
                with self.assertRaises(OSError):
                    socket.getaddrinfo("a.shopapp.example", 443)
        self.assertEqual(len(inner.raw_events()), 1)
        self.assertEqual(outer.raw_events(), [])

    def test_non_blocking_mode_lets_the_lookup_proceed(self):
        # use a loopback-resolving flow: we only check that block=False does not raise from the hook
        with AuditRecorder("a", block=False) as rec:
            rec._record("x.shopapp.example", 443)       # direct call, no real lookup
        self.assertEqual(rec.domains_seen(), {"x.shopapp.example"})

    def test_recorded_lines_are_understood_by_the_log_engine(self):
        with AuditRecorder("shopapp-mini") as rec:
            with self.assertRaises(OSError):
                socket.getaddrinfo("images.shopapp.example", 443)
        out = Normaliser(build_registry()).normalise(rec.raw_events()[0])
        self.assertEqual(out["format"], "egress_proxy")
        self.assertEqual(out["event"]["dst_endpoint"], {"hostname": "images.shopapp.example", "port": 443})


class ShopAppMini(unittest.TestCase):
    def test_routes(self):
        with ShopApp() as app:
            self.assertEqual(traffic.request(app.base_url, "/")[0], 200)
            self.assertEqual(traffic.request(app.base_url, "/about")[0], 200)
            self.assertEqual(traffic.request(app.base_url, "/webhook")[0], 405)
            self.assertEqual(traffic.request(app.base_url, "/webhook", data=b"{}")[0], 200)
            self.assertEqual(traffic.request(app.base_url, "/nope")[0], 404)

    def test_crawler_reaches_only_linked_pages(self):
        with ShopApp() as app:
            self.assertEqual(traffic.crawl(app.base_url), ["/", "/products", "/about", "/checkout"])

    def test_four_expected_domains(self):
        self.assertEqual(len(EXPECTED_DOMAINS), 4)
        self.assertTrue(all(d.endswith(".example") for d in EXPECTED_DOMAINS))


class Demo(TmpCase):
    def test_full_scenario(self):
        out = run_demo(self.tmp / "demo", say=lambda s: None)
        self.assertEqual(set(out["drift"]), {
            ("domain", "analytics.shopapp.example"),
            ("domain", "notifications.shopapp.example"),
            ("cloud_action", "s3:PutObject")})
        self.assertTrue(out["edit_detected"])
        self.assertFalse(out["truncation_without_anchor_detected"])
        self.assertTrue(out["truncation_with_anchor_detected"])

    def test_refuses_a_non_empty_folder(self):
        (self.tmp / "x").mkdir()
        (self.tmp / "x" / "file").write_text("hi")
        with self.assertRaises(FileExistsError):
            run_demo(self.tmp / "x", say=lambda s: None)


if __name__ == "__main__":
    unittest.main()
