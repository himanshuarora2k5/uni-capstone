import hashlib
import json
import unittest

from leastpriv.integrity import (GENESIS, ChainedLog, ChainError, canonical_json, dump_entry, link_hash, read_anchor,
                                 read_entries, verify, write_anchor)

from .helpers import TmpCase, read_lines, write_lines


def build(path, n=10):
    with ChainedLog(path) as log:
        for i in range(n):
            log.append({"n": i, "event": {"message": f"record {i}"}})
        return log.head


def recompute(entries, start):
    prev = entries[start - 1]["hash"] if start else GENESIS
    for k in range(start, len(entries)):
        entries[k].update(i=k, prev=prev, hash=link_hash(prev, entries[k]["record"]))
        prev = entries[k]["hash"]


class Hashing(unittest.TestCase):
    def test_canonical_json_ignores_key_order_and_spaces(self):
        self.assertEqual(canonical_json({"b": 1, "a": [1, 2]}), '{"a":[1,2],"b":1}')
        self.assertEqual(canonical_json({"a": 1, "b": 2}), canonical_json({"b": 2, "a": 1}))

    def test_canonical_json_keeps_unicode(self):
        self.assertEqual(canonical_json({"k": "é"}), '{"k":"é"}')

    def test_hash_formula_is_sha256_of_previous_hash_then_canonical_json(self):
        rec = {"x": 1}
        expect = hashlib.sha256((GENESIS + '{"x":1}').encode()).hexdigest()
        self.assertEqual(link_hash(GENESIS, rec), expect)


class Writer(TmpCase):
    def test_entries_carry_position_link_and_hash(self):
        p = self.tmp / "log.jsonl"
        build(p, 3)
        e = list(read_entries(p))
        self.assertEqual([x["i"] for x in e], [0, 1, 2])
        self.assertEqual(e[0]["prev"], GENESIS)
        self.assertEqual(e[1]["prev"], e[0]["hash"])
        self.assertEqual(e[2]["hash"], link_hash(e[2]["prev"], e[2]["record"]))

    def test_reopen_continues_the_chain(self):
        p = self.tmp / "log.jsonl"
        build(p, 3)
        with ChainedLog(p) as log:
            self.assertEqual(len(log), 3)
            log.append({"n": 3})
            head = log.head
        res = verify(p, anchor=head)
        self.assertTrue(res.ok)
        self.assertEqual(res.entries, 4)

    def test_unchained_mode_has_no_hash_fields(self):
        p = self.tmp / "plain.jsonl"
        with ChainedLog(p, chained=False) as log:
            log.append({"a": 1})
        self.assertEqual(json.loads(read_lines(p)[0]), {"i": 0, "record": {"a": 1}})

    def test_reopen_of_unchained_file_as_chained_is_refused(self):
        p = self.tmp / "plain.jsonl"
        with ChainedLog(p, chained=False) as log:
            log.append({"a": 1})
        with self.assertRaises(ChainError):
            ChainedLog(p)

    def test_anchor_file_roundtrip(self):
        p = self.tmp / "a.anchor"
        write_anchor(p, "abc123")
        self.assertEqual(read_anchor(p), "abc123")


class Verifier(TmpCase):
    def setUp(self):
        super().setUp()
        self.p = self.tmp / "log.jsonl"
        self.head = build(self.p, 10)
        self.lines = read_lines(self.p)
        self.entries = [json.loads(x) for x in self.lines]

    def save(self, entries):
        write_lines(self.p, [dump_entry(e) for e in entries])

    def test_untouched_chain_verifies_with_and_without_anchor(self):
        self.assertTrue(verify(self.p).ok)
        r = verify(self.p, anchor=self.head)
        self.assertTrue(r.ok)
        self.assertEqual((r.entries, r.head), (10, self.head))

    def test_empty_log(self):
        e = self.tmp / "empty.jsonl"
        e.write_text("")
        self.assertTrue(verify(e).ok)
        self.assertTrue(verify(e, anchor=GENESIS).ok)
        self.assertFalse(verify(e, anchor=self.head).ok)

    # ---- edit-only attacker: stored hashes left as they were ------------------------------
    def test_edit_is_detected_at_its_position(self):
        self.entries[4]["record"]["event"]["message"] = "changed"
        self.save(self.entries)
        r = verify(self.p)
        self.assertFalse(r.ok)
        self.assertEqual(r.bad_index, 4)
        self.assertIn("hash", r.reason)

    def test_delete_is_detected_at_its_position(self):
        del self.entries[4]
        self.save(self.entries)
        r = verify(self.p)
        self.assertEqual((r.ok, r.bad_index), (False, 4))

    def test_swap_is_detected_at_its_position(self):
        self.entries[4], self.entries[5] = self.entries[5], self.entries[4]
        self.save(self.entries)
        r = verify(self.p)
        self.assertEqual((r.ok, r.bad_index), (False, 4))

    def test_insert_is_detected_at_its_position(self):
        forged = {"i": 4, "prev": self.entries[3]["hash"], "record": {"forged": True}, "hash": self.entries[4]["hash"]}
        self.entries.insert(4, forged)
        self.save(self.entries)
        r = verify(self.p)
        self.assertEqual((r.ok, r.bad_index), (False, 4))

    def test_truncation_is_NOT_detected_without_anchor_but_is_with_one(self):
        write_lines(self.p, self.lines[:-3])
        self.assertTrue(verify(self.p).ok)                      # a prefix of a valid chain is valid
        r = verify(self.p, anchor=self.head)
        self.assertFalse(r.ok)
        self.assertIsNone(r.bad_index)
        self.assertIn("anchor", r.reason)

    # ---- rewriting attacker: recomputes everything after the change -----------------------
    def test_rewriting_attacker_is_NOT_detected_without_anchor_but_is_with_one(self):
        self.entries[4]["record"]["event"]["message"] = "changed"
        recompute(self.entries, 4)
        self.save(self.entries)
        self.assertTrue(verify(self.p).ok)
        r = verify(self.p, anchor=self.head)
        self.assertFalse(r.ok)
        self.assertIsNone(r.bad_index)          # only the head mismatch is reported, not where

    def test_self_consistent_entry_with_a_foreign_link_is_detected(self):
        # position and hash are both valid for this entry, but it does not continue the chain
        prev = "f" * 64
        self.entries[4] = {"i": 4, "prev": prev, "record": {"x": 1}, "hash": link_hash(prev, {"x": 1})}
        self.save(self.entries)
        r = verify(self.p)
        self.assertEqual((r.ok, r.bad_index), (False, 4))
        self.assertIn("link", r.reason)

    # ---- malformed content -------------------------------------------------------------------
    def test_garbage_line_is_reported_with_position(self):
        self.lines[6] = "{not json"
        write_lines(self.p, self.lines)
        r = verify(self.p)
        self.assertEqual((r.ok, r.bad_index), (False, 6))

    def test_blank_line_inside_the_log_is_tampering(self):
        self.lines.insert(3, "")
        write_lines(self.p, self.lines)
        r = verify(self.p)
        self.assertEqual((r.ok, r.bad_index), (False, 3))

    def test_missing_field_is_reported(self):
        del self.entries[2]["prev"]
        self.save(self.entries)
        r = verify(self.p)
        self.assertEqual((r.ok, r.bad_index), (False, 2))
        self.assertIn("missing", r.reason)

    def test_str_of_result_is_readable(self):
        self.assertTrue(str(verify(self.p)).startswith("OK"))
        self.entries[1]["record"] = {"x": 1}
        self.save(self.entries)
        self.assertIn("FAILED at entry 1", str(verify(self.p)))


if __name__ == "__main__":
    unittest.main()
