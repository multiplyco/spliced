"""The library build (spliced/build_library.py) on a throwaway copy of the fixture. Runs through uv, as a person runs it."""
import json, os, shutil, subprocess, unittest

import support


@unittest.skipUnless(shutil.which("uv"), "needs uv")
class Build(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.bd = os.path.join(self.root, "library", "references", "demo-one", "breakdown.json")

    def build(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SPLICED_")}
        r = subprocess.run(["uv", "run", "-q", os.path.join(support.TOOLS, "build_library.py"), *args], env={**env, "SPLICED_PROJECT": self.root},
                           capture_output=True, text=True, cwd=support.REPO)
        return r.returncode, r.stdout + r.stderr

    def change(self, fn):
        with open(self.bd) as f:
            b = json.load(f)
        fn(b)
        with open(self.bd, "w") as f:
            json.dump(b, f, indent=1)

    def index(self):
        with open(os.path.join(self.root, ".cache", "library.json")) as f:
            return json.load(f)

    def test_the_fixture_is_a_valid_library(self):
        code, out = self.build("--check")
        self.assertEqual(code, 0, out)

    def test_index_only_writes_the_index_and_nothing_else(self):
        md = os.path.join(self.root, "library", "references", "demo-one", "breakdown.md")
        before = os.path.getmtime(md)
        code, out = self.build("--index-only")
        self.assertEqual(code, 0, out)
        lib = self.index()
        self.assertEqual([f["slug"] for f in lib["films"]], ["demo-one", "demo-two"])
        self.assertEqual((lib["films"][0]["fps"], lib["films"][0]["takeaways"][0]), (24.0, "Lead with the news."))
        self.assertIn("whip", lib["tags"]["transition_in"])
        self.assertEqual([s["kind"] for s in lib["styles"]["sections"]], ["looks", "table", "prose"])
        self.assertEqual(os.path.getmtime(md), before, "no .md file is rewritten")

    def test_a_full_build_writes_the_pages(self):
        code, out = self.build()
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, "library", "references", "demo-one", "breakdown.md")) as f:
            md = f.read()
        self.assertIn("## Takeaways for Fixture", md, "the heading names the project's brand")
        with open(os.path.join(self.root, "library", "INDEX.md")) as f:
            self.assertIn("demo-two/s02", f.read())

    def test_the_fields_old_name_is_still_read(self):
        self.change(lambda b: b.update(takeaways_for_acme=b.pop("takeaways")))
        code, out = self.build("--index-only")
        self.assertEqual(code, 0, out)
        film = self.index()["films"][0]
        self.assertEqual(film["takeaways"], ["Lead with the news.", "One idea per scene."])
        self.assertNotIn("takeaways_for_acme", film)

    def test_problems_are_named_and_the_film_is_left_out(self):
        for what, fn, says in (("a tag that isn't in the taxonomy", lambda b: b["scenes"][0].update(world="moon-base"), "world 'moon-base' is not in TAXONOMY.md"),
                               ("a gap between scenes", lambda b: b["scenes"][1].update(start=2.6), "gap/overlap"),
                               ("a move in a scene that doesn't exist", lambda b: b["signature_moves"][0].update(scenes=["s09"]), "unknown scene s09")):
            with self.subTest(what):
                shutil.copy(os.path.join(support.FIXTURE, "library", "references", "demo-one", "breakdown.json"), self.bd)
                self.change(fn)
                code, out = self.build("--check")
                self.assertEqual(code, 1, out)
                self.assertIn(says, out)
        code, out = self.build("--index-only")
        self.assertEqual(code, 1)
        self.assertEqual([f["slug"] for f in self.index()["films"]], ["demo-two"], "the film with the problem is left out, the rest still load")

    def test_a_broken_reference_in_the_docs_fails_the_check(self):
        with open(os.path.join(self.root, "library", "STYLES.md"), "a") as f:
            f.write("\nSee [a scene that is gone](references/demo-one/breakdown.md#s07).\n")
        code, out = self.build("--links")
        self.assertEqual(code, 1, out)
        self.assertIn("broken reference demo-one/s07", out)


if __name__ == "__main__":
    unittest.main()
