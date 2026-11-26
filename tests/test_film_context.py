"""`spliced film context <slug>`: a new session's brief of a film, short enough to start from instead of the code (film.py)."""
import json, os, subprocess, sys, unittest

import support


class FilmContext(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.film = os.path.join(self.root, "remotion", "src", "films", "demo")

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args],
                           env={**env, "SPLICED_OFFLINE": "1"}, capture_output=True, text=True, cwd=support.REPO)
        return r.returncode, r.stdout + r.stderr

    def write(self, name, text):
        with open(os.path.join(self.film, name), "w") as f:
            f.write(text if isinstance(text, str) else json.dumps(text, indent=1))

    def test_a_new_session_can_pick_up_a_note_from_the_brief_alone(self):
        self.write("Scenes.tsx", "// The three beats of the Acme demo, each from its cue.\nimport React from 'react';\n"
                                 "const Hook = () => null;\nexport const Demo = () => null;\nexport function EndCard() { return null; }\n"
                                 "export {Hook as HookBeat};\n")
        self.write("BRIEF.md", "# Acme demo\n\nWhat the film says.\n")
        with open(os.path.join(self.film, "cues.json")) as f:
            cues = json.load(f)
        cues["beat"] = {"demo": {"cursor": 0.4, "click": 1.25, "panel": {"in": 0.2}}}
        self.write("cues.json", cues)
        self.write("sound.json", {"tracks": [{"id": "music", "lane": "music", "file": "remotion/public/audio/bed.wav", "start": 0},
                                             {"id": "sfx-1", "lane": "sfx", "file": "remotion/public/audio/kit/tap.wav", "start": 2.4},
                                             {"id": "sfx-2", "lane": "sfx", "file": "remotion/public/audio/kit/tap.wav", "start": 3.1}]})
        code, out = self.cli("film", "note", "demo", "0:02.50", "The click lands late", "--by", "chat")
        self.assertEqual(code, 0, out)
        nid = out.split(" note ")[1].split()[0]
        code, text = self.cli("film", "context", "demo")
        self.assertEqual(code, 0, text)
        self.assertLess(len(text), 12000, "about 3k tokens at most")
        for want in ("# Demo film (demo)", "Message: The fixture exists.", "320x180, 24 fps", "Motion profile: soft", "Latest render: ",
                     "Beats (1 open note", "Sound: music bed.wav, 2 effects", "Files (remotion/src/films/demo/):", "Assets in ", "Next:"):
            self.assertIn(want, text)
        lines = text.splitlines()
        beat = next(i for i, x in enumerate(lines) if x.strip().startswith("2. demo"))
        follow = "\n".join(lines[beat + 1:beat + 5])
        self.assertIn("cues beat.demo: cursor 0.4, click 1.25, panel.in 0.2", follow, "the beat's inner cue times, flattened")
        self.assertIn("NOTE [", follow, "the open note sits under the beat it is on")
        self.assertIn("The click lands late", follow)
        self.assertIn(f"[{nid}]", follow, "with its id, so it can be closed")
        self.assertIn("Scenes.tsx  6 lines  The three beats of the Acme demo, each from its cue.", text, "each file: lines and its header's first line")
        self.assertIn("exports: Demo, EndCard, HookBeat", text, "exported names, found without a TypeScript parser")
        self.assertIn("also defines: Hook", text)
        self.assertIn("BRIEF.md  3 lines  Acme demo", text)
        self.assertIn("unused (", text, "assets nothing uses are named")
        self.assertIn("film done demo <ids>", text)
        self.assertIn("--beat demo", text, "the next render is the beat with the open note")

    def test_a_big_film_is_cut_with_a_pointer_to_the_rest(self):
        with open(os.path.join(self.film, "storyboard.json")) as f:
            sb = json.load(f)
        beats, scenes = [], {}
        for i in range(120):
            beats.append({"id": f"b{i}", "title": f"Beat {i}", "copy": "Words on screen " * 20, "status": "review"})
            scenes[f"b{i}"] = [i * 2.0, i * 2.0 + 2.0]
        sb["beats"] = beats
        self.write("storyboard.json", sb)
        self.write("cues.json", {"fps": 24, "duration": 240.0, "scenes": scenes, "beat": {f"b{i}": {f"t{k}": k / 10 for k in range(40)} for i in range(120)}})
        code, text = self.cli("film", "context", "demo")
        self.assertEqual(code, 0, text)
        self.assertLess(len(text), 12400)
        self.assertIn("... cut at about 3000 tokens. The rest: ", text)
        self.assertIn("film status demo", text.splitlines()[-1])

    def test_only_the_films_own_files_are_read(self):
        with open(os.path.join(self.root, ".env"), "a") as f:
            f.write("# ACME_KEY=sk-live-not-for-an-agent\n")
        os.symlink(os.path.join(self.root, ".env"), os.path.join(self.film, "envlink.txt"))   # a link a shared project could ship
        os.mkfifo(os.path.join(self.film, "pipe.txt"))   # never finishes reading
        self.write("big.txt", "// big\n" + "x" * (400 * 1024))
        code, text = self.cli("film", "context", "demo")
        self.assertEqual(code, 0, text)
        self.assertNotIn("sk-live", text)
        self.assertNotIn("envlink", text)
        self.assertNotIn("pipe.txt", text)
        self.assertIn("big.txt  400 KB", text, "a big file is named with its size, not read")

    def test_no_such_film(self):
        code, out = self.cli("film", "context", "nope")
        self.assertNotEqual(code, 0)
        self.assertIn("no film called nope", out)


if __name__ == "__main__":
    unittest.main()
