"""The shared state engine (spliced/toolbox_state.py): every operation, and the promises around them."""
import copy, json, os, tempfile, unittest

import support  # noqa: F401  (puts the package on the path)
import toolbox_state as ts

KNOWN = {"demo-one/s01", "demo-one/s02", "demo-two/s01", "demo-two/s02", "demo-two/s03", "uploads/f1x7u0"}


def fixture_state():
    return ts.load(os.path.join(support.FIXTURE, "library", "state.json"))


class Ops(unittest.TestCase):
    def setUp(self):
        self.s = fixture_state()

    def run_ops(self, *ops, **kw):
        new, results, summary = ts.apply(self.s, list(ops), by=kw.get("by", "test"), known=kw.get("known", KNOWN))
        return new, results, summary

    def refuses(self, *ops, known=KNOWN):
        before = copy.deepcopy(self.s)
        with self.assertRaises((ts.OpError, KeyError, TypeError, ValueError)):
            ts.apply(self.s, list(ops), known=known)
        self.assertEqual(self.s, before, "a refused batch must leave the state untouched")

    # ---- reviews
    def test_review_set_and_clear(self):
        new, _, _ = self.run_ops({"op": "review.set", "key": "demo-two/s03", "patch": {"fav": True, "verdict": "maybe", "note": "hm"}})
        self.assertEqual(new["reviews"]["demo-two/s03"], {"fav": True, "verdict": "maybe", "note": "hm"})
        new, _, _ = ts.apply(new, [{"op": "review.set", "key": "demo-two/s03", "patch": {"fav": False, "verdict": "", "note": None}}], known=KNOWN)
        self.assertNotIn("demo-two/s03", new["reviews"], "a review with nothing left in it is removed")

    def test_review_refuses_bad_input(self):
        self.refuses({"op": "review.set", "key": "nope/s01", "patch": {"fav": True}})
        self.refuses({"op": "review.set", "key": "demo-one/s01", "patch": {"verdict": "love"}})
        self.refuses({"op": "review.set", "key": "demo-one/s01", "patch": {"stars": 5}})

    # ---- boards
    def test_board_create(self):
        new, results, _ = self.run_ops({"op": "board.create", "name": " New ", "profile": "apple", "brief": {"news": "x"},
                                        "items": [{"id": "demo-one/s02", "seconds": "0:03.5"}]})
        b = new["boards"]["New"]
        self.assertEqual(results, [{"board": "New"}])
        self.assertEqual((b["profile"], b["brief"], b["items"][0]["seconds"]), ("apple", {"news": "x"}, 3.5))
        self.assertTrue(b["items"][0]["uid"])

    def test_board_create_refuses(self):
        self.refuses({"op": "board.create", "name": "  "})
        self.refuses({"op": "board.create", "name": "Fixture board"})
        self.refuses({"op": "board.create", "name": "X", "profile": "no-such-profile"})
        self.refuses({"op": "board.create", "name": "X", "brief": {"budget": 1}})
        self.refuses({"op": "board.create", "name": "X", "items": [{"id": "demo-one/s01", "colour": "red"}]})

    def test_board_rename_keeps_order(self):
        s, _, _ = self.run_ops({"op": "board.create", "name": "Second"})
        new, _, _ = ts.apply(s, [{"op": "board.rename", "name": "Fixture board", "to": "Renamed"}], known=KNOWN)
        self.assertEqual(list(new["boards"]), ["Renamed", "Second"])
        with self.assertRaises(ts.OpError):
            ts.apply(new, [{"op": "board.rename", "name": "Renamed", "to": "Second"}], known=KNOWN)

    def test_board_delete(self):
        new, _, _ = self.run_ops({"op": "board.delete", "name": "Fixture board"})
        self.assertEqual(new["boards"], {})
        self.refuses({"op": "board.delete", "name": "No such board"})

    def test_board_set(self):
        new, _, _ = self.run_ops({"op": "board.set", "name": "Fixture board", "profile": "material", "brief": {"length": 12, "audience": ""}})
        b = new["boards"]["Fixture board"]
        self.assertEqual(b["profile"], "material")
        self.assertEqual(b["brief"], {"news": "The fixture exists.", "aspect": "16:9", "length": 12}, "an empty value clears a brief field, the rest merge")
        self.refuses({"op": "board.set", "name": "Fixture board", "profile": "nope"})
        self.refuses({"op": "board.set", "name": "Fixture board", "brief": {"budget": 1}})

    # ---- items
    def test_item_add_positions(self):
        new, results, _ = self.run_ops({"op": "item.add", "board": "Fixture board", "id": "demo-one/s02", "at": 1, "t": "0:02.5"},
                                       {"op": "item.add", "board": "Fixture board", "id": "demo-two/s03"})
        items = new["boards"]["Fixture board"]["items"]
        self.assertEqual([i["id"] for i in items], ["demo-one/s02", "demo-one/s01", "demo-two/s02", "uploads/f1x7u0", "demo-two/s03"])
        self.assertEqual((results[0]["n"], results[1]["n"], items[0]["t"]), (1, 5, 2.5))

    def test_item_add_refuses(self):
        self.refuses({"op": "item.add", "board": "Fixture board"})
        self.refuses({"op": "item.add", "board": "Fixture board", "id": "nope/s09"})
        self.refuses({"op": "item.add", "board": "Fixture board", "id": "demo-one/s01", "uid": "aaa111"})
        self.refuses({"op": "item.add", "board": "Fixture board", "id": "demo-one/s01", "mood": "warm"})
        self.refuses({"op": "item.add", "board": "Fixture board", "id": "demo-one/s01", "seconds": -1})

    def test_item_update_by_uid_and_n(self):
        new, _, _ = self.run_ops({"op": "item.update", "board": "Fixture board", "uid": "bbb222", "patch": {"copy": "New words", "t": "", "seconds": ""}},
                                 {"op": "item.update", "board": "Fixture board", "n": 1, "patch": {"note": "first"}})
        a, b = new["boards"]["Fixture board"]["items"][:2]
        self.assertEqual((a["note"], b["copy"]), ("first", "New words"))
        self.assertNotIn("t", b)
        self.assertNotIn("seconds", b, "an empty string clears a time")
        self.refuses({"op": "item.update", "board": "Fixture board", "uid": "zzz999", "patch": {"note": "x"}})
        self.refuses({"op": "item.update", "board": "Fixture board", "n": 9, "patch": {"note": "x"}})
        self.refuses({"op": "item.update", "board": "Fixture board", "n": 1, "patch": {"uid": "new"}})

    def test_item_remove_and_move(self):
        new, _, _ = self.run_ops({"op": "item.move", "board": "Fixture board", "uid": "ccc333", "to": 1},
                                 {"op": "item.remove", "board": "Fixture board", "n": 2})
        self.assertEqual([i["uid"] for i in new["boards"]["Fixture board"]["items"]], ["ccc333", "bbb222"])
        new, _, _ = self.run_ops({"op": "item.move", "board": "Fixture board", "n": 1, "to": 99})
        self.assertEqual(new["boards"]["Fixture board"]["items"][-1]["uid"], "aaa111", "a position past the end means the end")

    # ---- moments
    def test_moments(self):
        new, results, _ = self.run_ops({"op": "moment.add", "key": "demo-one/s02", "t": "0:03.25", "note": "push-in lands"})
        uid = results[0]["uid"]
        m = next(x for x in new["moments"] if x["uid"] == uid)
        self.assertEqual((m["t"], m["by"], m["note"]), (3.25, "test", "push-in lands"))
        new, _, _ = ts.apply(new, [{"op": "moment.update", "uid": uid, "patch": {"note": "", "t": 3.5}}], known=KNOWN)
        self.assertEqual([(x["note"], x["t"]) for x in new["moments"] if x["uid"] == uid], [("", 3.5)])
        new, _, _ = ts.apply(new, [{"op": "moment.remove", "uid": uid}], known=KNOWN)
        self.assertEqual([x["uid"] for x in new["moments"]], ["m0m3n7"])

    def test_moments_refuse(self):
        self.refuses({"op": "moment.add", "key": "demo-one/s02"})
        self.refuses({"op": "moment.add", "key": "nope/s01", "t": 1})
        self.refuses({"op": "moment.add", "key": "demo-one/s02", "t": 1, "uid": "m0m3n7"})
        self.refuses({"op": "moment.add", "key": "demo-one/s02", "t": 1, "colour": "red"})
        self.refuses({"op": "moment.update", "uid": "nope", "patch": {"note": "x"}})
        self.refuses({"op": "moment.update", "uid": "m0m3n7", "patch": {"key": "demo-one/s01"}})
        self.refuses({"op": "moment.remove", "uid": "nope"})

    # ---- the promises around every batch
    def test_unknown_op(self):
        self.refuses({"op": "board.explode", "name": "Fixture board"})

    def test_a_failing_batch_changes_nothing(self):
        self.refuses({"op": "board.create", "name": "Made first"}, {"op": "item.remove", "board": "Fixture board", "n": 42})

    def test_input_state_is_never_mutated(self):
        before = copy.deepcopy(self.s)
        self.run_ops({"op": "board.delete", "name": "Fixture board"})
        self.assertEqual(self.s, before)

    def test_rev_and_log(self):
        new, _, summary = self.run_ops({"op": "review.set", "key": "demo-one/s02", "patch": {"fav": True}}, by="someone")
        self.assertEqual(new["rev"], self.s["rev"] + 1)
        self.assertEqual((new["log"][-1]["rev"], new["log"][-1]["by"], new["log"][-1]["summary"]), (new["rev"], "someone", summary))
        same, _, summary = self.run_ops()
        self.assertEqual((same["rev"], summary), (self.s["rev"], ""), "no ops, no new revision")

    def test_log_keeps_the_last_fifty(self):
        s = self.s
        for i in range(60):
            s, _, _ = ts.apply(s, [{"op": "review.set", "key": "demo-one/s02", "patch": {"note": str(i)}}], known=KNOWN)
        self.assertEqual(len(s["log"]), 50)
        self.assertEqual(s["log"][-1]["rev"], s["rev"])

    def test_without_a_known_set_any_scene_is_taken(self):
        new, _, _ = self.run_ops({"op": "item.add", "board": "Fixture board", "id": "anything/s99"}, known=None)
        self.assertEqual(new["boards"]["Fixture board"]["items"][-1]["id"], "anything/s99")


class Files(unittest.TestCase):
    def test_times(self):
        self.assertEqual(ts._secs("1:02.5", "t"), 62.5)
        self.assertEqual(ts._secs(42.514, "t"), 42.51)
        with self.assertRaises(ts.OpError):
            ts._secs(-0.5, "t")

    def test_normalise_fills_older_state(self):
        s = ts.normalise({"boards": {"Old": {"items": [{"id": "demo-one/s01"}]}}, "moments": [{"key": "demo-one/s01", "t": 1}]})
        it = s["boards"]["Old"]["items"][0]
        self.assertTrue(it["uid"] and s["moments"][0]["uid"])
        self.assertEqual((it["beat"], it["copy"], it["vo"], it["note"], s["rev"], s["reviews"], s["log"]), ("", "", "", "", 0, {}, []))
        self.assertIn(s["boards"]["Old"]["profile"], ts.PROFILES)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "state.json")
            self.assertEqual(ts.load(p), ts.empty(), "a missing file is an empty state")
            s = fixture_state()
            ts.save(s, p)
            self.assertEqual(ts.load(p), s)
            self.assertFalse(os.path.exists(p + ".tmp"))
            with open(p, "w") as f:
                f.write("{ not json")
            self.assertEqual(ts.load(p), ts.empty(), "a broken file is an empty state, not a crash")

    def test_fixture_state_is_already_normal(self):
        with open(os.path.join(support.FIXTURE, "library", "state.json")) as f:
            raw = json.load(f)
        self.assertEqual(ts.normalise(copy.deepcopy(raw)), raw)


if __name__ == "__main__":
    unittest.main()
