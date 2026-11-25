"""The experiment runners must keep reproducing the behaviour the paper reports (Tables 3 and 5)."""
import unittest

from experiments import e3_integrity, e6_pilot


class E3(unittest.TestCase):
    def test_detection_table_matches_the_paper(self):
        rows = {(r["attacker"], r["anchor"]): r for r in e3_integrity.detection(records=100)}
        self.assertEqual(rows[("edit-only", False)]["detected"], 4)
        self.assertEqual(rows[("edit-only", True)]["detected"], 5)
        self.assertEqual(rows[("rewriting", False)]["detected"], 0)
        self.assertEqual(rows[("rewriting", True)]["detected"], 5)
        self.assertEqual(rows[("edit-only", False)]["position_correct"], 4)
        self.assertEqual(rows[("edit-only", True)]["position_correct"], 4)
        self.assertEqual(rows[("rewriting", True)]["position_correct"], 0)
        # truncation is the one change an edit-only attacker gets away with when there is no anchor
        pc = rows[("edit-only", False)]["per_change"]
        self.assertEqual([k for k, v in pc.items() if not v["detected"]], ["truncate"])

    def test_truncation_cuts_exactly_ten_records(self):
        recs = e3_integrity.make_records(50)
        import tempfile, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.jsonl"
            e3_integrity.build_chain(p, recs)
            entries = [json.loads(x) for x in p.read_text().splitlines()]
        self.assertEqual(len(e3_integrity.tamper(entries, "truncate", 25, rewriting=False)), 40)

    def test_timing_runner_returns_every_measure(self):
        t = e3_integrity.timing(runs=1, write_n=300, sizes=(50, 100))
        for key in ("events_per_second_chained", "events_per_second_plain", "verify_seconds_50", "verify_seconds_100"):
            self.assertEqual(len(t[key]), 1)
            self.assertGreater(t[key][0], 0)


class E6(unittest.TestCase):
    def test_coverage_matches_the_paper_pilot(self):
        rows = e6_pilot.run()
        self.assertEqual([round(r["coverage_percent"]) for r in rows], [25, 50, 50, 100])
        self.assertEqual([(r["found"], r["expected"]) for r in rows], [(1, 4), (2, 4), (2, 4), (4, 4)])

    def test_coverage_formula(self):
        self.assertEqual(e6_pilot.coverage({"a", "x"}, {"a", "b", "c", "d"}), 25.0)


if __name__ == "__main__":
    unittest.main()
