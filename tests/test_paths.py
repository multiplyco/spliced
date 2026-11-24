"""spliced/paths.py and locate.py: which folder is the project, and which of its files may be handed to the app."""
import json, os, subprocess, sys, unittest
from unittest import mock

import support
import locate, paths


def tool(name, *args, cwd=None, env=None):
    """Run one of the tools as a person would; returns (exit code, output)."""
    e = {k: v for k, v in os.environ.items() if k not in ("SPLICED_PROJECT", "CUTTING_ROOM_OFFLINE")}
    e.update(env or {})
    r = subprocess.run([sys.executable, os.path.join(support.TOOLS, name), *args], cwd=cwd or support.REPO, env=e, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


class Discovery(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)

    def test_order(self):
        other = os.path.join(os.path.dirname(self.root), "other")
        os.makedirs(os.path.join(other, "deep", "er"))
        deep = os.path.join(self.root, "library", "references")
        self.assertEqual(locate.find(explicit=other, start=deep, env={"SPLICED_PROJECT": self.root}), other, "the flag wins")
        self.assertEqual(locate.find(start=os.path.join(other, "deep"), env={"SPLICED_PROJECT": self.root}), self.root, "then the environment")
        self.assertEqual(locate.find(start=deep, env={}), self.root, "then the nearest spliced.json above")
        self.assertIsNone(locate.find(start=os.path.join(other, "deep", "er"), env={}), "and otherwise there is none: Spliced never guesses")

    def test_a_named_folder_must_exist(self):
        with self.assertRaises(SystemExit):
            locate.find(explicit=os.path.join(self.root, "nope"), env={})

    def test_outside_a_project_a_tool_says_how_to_get_one(self):
        code, out = tool("board.py", "boards", cwd=os.path.dirname(self.root))
        self.assertNotEqual(code, 0)
        self.assertIn("isn't inside a project", out)
        self.assertIn("spliced init", out)

    def test_a_tool_reads_the_project_it_is_pointed_at(self):
        for how, kw in (("flag", {"args": ["--project", self.root]}), ("environment", {"env": {"SPLICED_PROJECT": self.root}}),
                        ("current folder", {"cwd": os.path.join(self.root, "library")})):
            code, out = tool("board.py", *kw.get("args", []), "boards", cwd=kw.get("cwd"), env=kw.get("env"))
            self.assertEqual(code, 0, out)
            self.assertIn("Fixture board", out, f"by {how}")
            self.assertNotIn("toolbox live", out, f"by {how}: a server for another project is not ours")

    def test_a_tool_writes_only_into_its_project(self):
        code, out = tool("board.py", "--project", self.root, "new", "Made by a test")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, "library", "state.json")) as f:
            self.assertIn("Made by a test", json.load(f)["boards"])
        with open(paths.STATE) as f:
            self.assertNotIn("Made by a test", f.read(), "no other project is touched")

    def test_boards_saved_before_the_move_are_still_found(self):
        new, old = os.path.join(self.root, "library", "state.json"), os.path.join(self.root, "library", "toolbox", "state.json")
        os.makedirs(os.path.dirname(old))
        os.rename(new, old)
        code, out = tool("board.py", "--project", self.root, "boards")
        self.assertIn("Fixture board", out, "read from where the app used to keep it")
        code, out = tool("board.py", "--project", self.root, "new", "After the move")
        self.assertEqual(code, 0, out)
        with open(new) as f:
            self.assertEqual(set(json.load(f)["boards"]), {"Fixture board", "After the move"}, "the next change lands in library/state.json, with everything")

    def test_the_project_names_its_own_profiles_and_default(self):
        code, out = tool("board.py", "--project", self.root, "new", "Plain")
        self.assertEqual(code, 0, out)
        code, out = tool("board.py", "--project", self.root, "new", "Not ours", "--profile", "acme-house")
        self.assertNotEqual(code, 0, "another project's profile is not this project's")
        with open(os.path.join(self.root, "spliced.json")) as f:
            cfg = json.load(f)
        cfg.update(profiles={"house": "Our own: slow and heavy"}, default_profile="house")
        with open(os.path.join(self.root, "spliced.json"), "w") as f:
            json.dump(cfg, f)
        code, out = tool("board.py", "--project", self.root, "new", "Ours")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, "library", "state.json")) as f:
            boards = json.load(f)["boards"]
        self.assertEqual((boards["Plain"]["profile"], boards["Ours"]["profile"]), ("soft", "house"))
        code, out = tool("board.py", "--project", self.root, "new", "Kit", "--profile", "apple")
        self.assertEqual(code, 0, "the kit's profiles stay available: " + out)

    def test_children_inherit_the_project(self):
        code, out = tool("board.py", "--project", self.root, "scene", "demo-two/s02")
        self.assertEqual(code, 0, out)
        r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import paths, os; print(os.environ['SPLICED_PROJECT'] == paths.ROOT)", support.TOOLS],
                           env={**os.environ, "SPLICED_PROJECT": self.root}, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "True")


class Media(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        p = mock.patch.object(paths, "ROOT", self.root)
        p.start()
        self.addCleanup(p.stop)

    def test_media_files_are_given(self):
        for ok in ("reference/demo-one.mp4", "reference/Demo two [abc123].mp4", "library/references/demo-one/scenes/s01.jpg",
                   "library/uploads/fixture-look-f1x7u0.png", "remotion/out/demo-v1.mp4", "/reference/demo-one.mp4"):
            self.assertEqual(paths.media(ok), os.path.join(self.root, ok.lstrip("/")), ok)

    def test_everything_else_is_not(self):
        os.makedirs(os.path.join(self.root, ".cache", "imports"))
        os.makedirs(os.path.join(self.root, ".cache", "sound", "k"))
        for rel in (".cache/imports/job.mp4", ".cache/sound/k/vocals.wav", ".hidden.png", "library/.secret.jpg"):
            open(os.path.join(self.root, rel), "w").close()
        outside = os.path.join(os.path.dirname(self.root), "outside.mp4")
        open(outside, "w").close()
        os.symlink(outside, os.path.join(self.root, "reference", "link-out.mp4"))
        for no in (".env", "", "/", "spliced.json", "library/state.json", "library/TAXONOMY.md", "reference", "reference/missing.mp4",
                   "../outside.mp4", "reference/../../outside.mp4", outside, "reference/link-out.mp4", ".cache/imports/job.mp4",
                   ".hidden.png", "library/.secret.jpg", ".cache/sound/../imports/job.mp4", "library\\..\\.env"):
            self.assertIsNone(paths.media(no), no)
        self.assertTrue(paths.media(".cache/sound/k/vocals.wav"), "the separated stems are the one dot folder the app may read")

    def test_resolve_stays_inside(self):
        self.assertEqual(paths.resolve("library"), os.path.join(self.root, "library"))
        self.assertEqual(paths.resolve(""), self.root)
        for no in ("..", "../x", "/etc/hosts", "library/../../x"):
            with self.assertRaises(ValueError, msg=no):
                paths.resolve(no)

    def test_rel(self):
        self.assertEqual(paths.rel(os.path.join(self.root, "library", "uploads", "a b.png")), "library/uploads/a b.png")


class Layout(unittest.TestCase):
    def test_every_place_is_inside_the_project(self):
        for name in ("LIB", "REFS", "REFS_TSV", "UPLOADS", "UPLOADS_INDEX", "TAXONOMY", "STYLES", "INDEX_MD", "STATE", "REFERENCE", "REMOTION",
                     "FILMS", "OUT", "PUBLIC", "PUBLIC_FILMS", "VIDEOS", "MUSIC", "CACHE", "FRAMES_CACHE", "SOUND_CACHE", "UPLOADS_CACHE", "JOBS", "WATCH", "ENV"):
            self.assertTrue(getattr(paths, name).startswith(paths.ROOT + os.sep), name)

    def test_the_code_is_found_without_the_project(self):
        self.assertEqual(paths.tool("sound"), os.path.join(support.TOOLS, "sound.py"))
        self.assertEqual(paths.tool("film.py"), os.path.join(support.TOOLS, "film.py"))
        self.assertTrue(os.path.isfile(os.path.join(paths.WEB, "index.html")))

    def test_no_tool_works_out_the_root_by_itself(self):
        for f in sorted(os.listdir(support.TOOLS)):
            if f.endswith(".py") and f != "paths.py":
                with open(os.path.join(support.TOOLS, f)) as fh:
                    self.assertNotIn("dirname(os.path.dirname(os.path.abspath(__file__)))", fh.read(), f"{f} should ask paths.py")


if __name__ == "__main__":
    unittest.main()
