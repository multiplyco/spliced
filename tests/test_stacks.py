"""Stacks: the frames of one render are one thing to a person and still every file to an agent (film.py stack_assets)."""
import json, os, shutil, subprocess, sys, unittest

import support
import film


def img(file, **kw):
    return {"file": file, "type": "image", "size": 10, "mtime": 1.0, **kw}


class Grouping(unittest.TestCase):
    def test_numbered_frames_in_one_folder_are_a_stack(self):
        items = [img(f"shots/spin/f_{n:04d}.png", film="demo", source="blender", used=n == 3) for n in (1, 2, 3, 10)] + [img("shots/plate.png"), img("shots/a_1.png"), img("shots/a_2.png")]
        stacks = film.stack_assets(items)
        self.assertEqual(len(stacks), 1)
        s = stacks[0]
        self.assertEqual((s["id"], s["pattern"], s["name"], s["count"], s["first"], s["last"]), ("shots/spin/f_#.png", "shots/spin/f_####.png", "spin", 4, 1, 10))
        self.assertEqual((s["cover"], s["size"], s["used"], s["film"], s["source"]), ("shots/spin/f_0003.png", 40, True, "demo", "blender"))
        self.assertEqual([(a.get("stack"), a.get("frame")) for a in items[:4]], [("shots/spin/f_#.png", n) for n in (1, 2, 3, 10)], "every frame is still there, and knows its place")
        self.assertTrue(all("stack" not in a for a in items[4:]), "one picture, or a pair, is not a stack")

    def test_what_is_and_is_not_one_set(self):
        items = ([img(f"a/sunrise-{n:02d}.jpg") for n in range(3)] + [img(f"b/sunrise-{n:02d}.jpg") for n in range(3)]       # the same name in two folders: two stacks
                 + [img(f"a/sunrise-{n:02d}.png") for n in range(3)]                                                      # another format: its own
                 + [{"file": f"a/take-{n}.mp4", "type": "video"} for n in range(4)] + [{"file": f"a/hit-{n}.wav", "type": "audio"} for n in range(4)])   # clips and sounds are never stacked
        stacks = film.stack_assets(items)
        self.assertEqual(sorted(s["id"] for s in stacks), ["a/sunrise-#.jpg", "a/sunrise-#.png", "b/sunrise-#.jpg"])
        self.assertEqual({s["name"] for s in stacks}, {"sunrise"}, "a prefix that is a word names the stack; a bare f_ takes the folder's name")
        self.assertTrue(all("stack" not in a for a in items if a["type"] != "image"))

    def test_used_and_label(self):
        frames = [img(f"x/f_{n:03d}.png", uses=[], label="The spin") for n in range(4)]
        s = film.stack_assets(frames)[0]
        self.assertEqual((s["used"], s["label"]), (False, "The spin"))
        self.assertIsNone(film.stack_assets([img(f"y/f_{n:03d}.png", used=None) for n in range(3)])[0]["used"])


@unittest.skipUnless(shutil.which("uv"), "needs uv")
class OnAProject(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args], env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_the_command_line_shows_a_stack_as_one_line_and_every_frame_on_request(self):
        code, out = self.cli("film", "assets", "demo")
        self.assertEqual(code, 0, out)
        lines = [l for l in out.splitlines() if "films/demo/" in l]
        self.assertEqual(len(lines), 2, out)
        self.assertTrue(any("films/demo/shots/spin/f_[0001..0006].png" in l and "6 frames" in l for l in lines), out)
        self.assertIn("--frames", out, "it says how to see each frame")
        code, out = self.cli("film", "assets", "demo", "--frames")
        self.assertEqual(len([l for l in out.splitlines() if "films/demo/" in l]), 7, out)
        self.assertIn("films/demo/shots/spin/f_0004.png", out)

    def test_the_library_lists_every_frame_and_the_stack(self):
        r = subprocess.run([sys.executable, "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import film; d = film.library_assets(); print(json.dumps({'n': len([a for a in d['assets'] if a['type'] == 'image']), 'stacks': d['stacks'], 'frames': sorted(a['frame'] for a in d['assets'] if a.get('stack'))}))", support.TOOLS],
                           env={**os.environ, "SPLICED_PROJECT": self.root}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual((d["n"], d["frames"], len(d["stacks"])), (7, [1, 2, 3, 4, 5, 6], 1))
        s = d["stacks"][0]
        self.assertEqual((s["id"], s["name"], s["count"], s["film"]), ("remotion/public/films/demo/shots/spin/f_#.png", "spin", 6, "demo"))


if __name__ == "__main__":
    unittest.main()
