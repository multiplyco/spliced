"""spliced voice without a key: the lines handed to the person's AI, and the reads it made filed back as takes."""
import json, os, shutil, subprocess, sys, unittest

import support


@unittest.skipUnless(shutil.which("uv") and shutil.which("ffmpeg"), "needs uv and ffmpeg")
class VoiceByAgent(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        with open(os.path.join(self.root, "spliced.json")) as f:
            cfg = json.load(f)
        cfg["voice"] = {"voice_id": "v123", "name": "Test", "model_id": "eleven_v4", "tone": "calm"}
        with open(os.path.join(self.root, "spliced.json"), "w") as f:
            json.dump(cfg, f)
        self.film = os.path.join(self.root, "remotion", "src", "films", "demo")
        with open(os.path.join(self.film, "cues.json")) as f:
            cues = json.load(f)
        # "hook" matches its script; "demo" was recorded as "Here it was." and the storyboard now says "Here it is."
        cues["film"] = {"voLines": [{"id": "hook", "at": 0.1, "beat": "hook", "src": "films/demo/audio/hook.wav", "text": "Look at this."},
                                    {"id": "demo", "at": 2.1, "beat": "demo", "src": "films/demo/audio/demo.wav", "text": "Here it was."}]}
        with open(os.path.join(self.film, "cues.json"), "w") as f:
            json.dump(cues, f)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_", "ELEVENLABS_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "voice", *args],
                           env=env, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout + r.stderr

    def read(self, name, *parts):
        """A stand-in for a read: tones for speech, silence for the pauses between."""
        out = os.path.join(os.path.dirname(self.root), name)
        src = [f"sine=frequency=220:duration={d}" if kind == "say" else f"anullsrc=r=44100:cl=mono:d={d}" for kind, d in parts]
        args = ["ffmpeg", "-v", "error", "-y"] + sum((["-f", "lavfi", "-i", s] for s in src), [])
        args += ["-filter_complex", "".join(f"[{i}]" for i in range(len(src))) + f"concat=n={len(src)}:v=0:a=1", "-ar", "44100", "-ac", "1", out]
        subprocess.run(args, check=True)
        return out

    def takes(self):
        with open(os.path.join(self.film, "takes.json")) as f:
            return json.load(f)["tracks"]

    def test_without_a_key_it_points_at_the_agent_route(self):
        code, out = self.cli("record", "demo")
        self.assertEqual(code, 1, out)
        self.assertIn("record demo --agent", out)

    def test_the_hand_off_names_the_changed_line_with_its_lead_in(self):
        code, out = self.cli("record", "demo", "--agent", "--json", "--takes", "1")
        self.assertEqual(code, 0, out)
        d = json.loads(out)
        self.assertEqual((d["voice_id"], d["model_id"], d["takes"]), ("v123", "eleven_v4", 1))
        self.assertEqual([l["line"] for l in d["lines"]], ["demo"])          # only what changed in the script
        line = d["lines"][0]
        self.assertEqual(line["lead_in"], "Look at this.")
        self.assertEqual(line["prompt"], "[calm] Look at this. ... [calm] Here it is.")
        self.assertIn("voice file demo demo", line["then"])
        code, out = self.cli("record", "demo", "--agent", "hook")              # a named line after a flag is still a line
        self.assertEqual(code, 0, out)
        self.assertIn("hook: Look at this.", out)
        self.assertNotIn("demo: Here it is.", out)

    def test_a_read_is_filed_without_its_lead_in(self):
        f = self.read("read.wav", ("say", 0.9), ("pause", 0.6), ("say", 1.1))
        code, out = self.cli("file", "demo", "demo", f)
        self.assertEqual(code, 0, out)
        tr = self.takes()["voice-demo"]
        self.assertEqual(tr["chosen"], "demo-1")
        t = tr["takes"][0]
        self.assertTrue(1.0 < t["dur"] < 1.5, t)                               # the line, not the lead-in before it
        self.assertTrue(os.path.exists(os.path.join(self.root, t["file"])))
        with open(os.path.join(self.film, "assets.json")) as fh:
            a = json.load(fh)["films/demo/audio/vo/demo/demo-1.wav"]
        self.assertEqual((a["via"], a["prompt"]), ("your AI's ElevenLabs connector", "[calm] Look at this. ... [calm] Here it is."))
        g = self.read("plain.wav", ("say", 1.2))
        code, out = self.cli("file", "demo", "demo", g, "--plain")
        self.assertEqual(code, 0, out)
        self.assertEqual([t["id"] for t in self.takes()["voice-demo"]["takes"]], ["demo-1", "demo-2"])

    def test_another_voice_service_or_a_persons_own_recording_is_filed_the_same_way(self):
        with open(os.path.join(self.root, "spliced.json")) as f:
            cfg = json.load(f)
        cfg["voice"] = {"provider": "acme-voices", "name": "Ada", "tone": "warm"}   # no voice_id: that is ElevenLabs' own
        with open(os.path.join(self.root, "spliced.json"), "w") as f:
            json.dump(cfg, f)
        code, out = self.cli("record", "demo")                                 # Spliced can't call it: it says who can
        self.assertEqual(code, 1, out)
        self.assertIn("This project's voice is acme-voices", out)
        code, out = self.cli("record", "demo", "--agent", "--json")
        self.assertEqual(code, 0, out)
        d = json.loads(out)
        line = d["lines"][0]
        self.assertEqual((d["provider"], d["voice"], line["prompt"], line["lead_in"]), ("acme-voices", "Ada", "Here it is.", ""))
        self.assertIn("--plain --source acme-voices", line["then"])
        f = self.read("theirs.wav", ("say", 1.2))
        code, out = self.cli("file", "demo", "demo", f, "--plain", "--source", "acme-voices")
        self.assertEqual(code, 0, out)
        g = self.read("mine.wav", ("say", 1.1))
        code, out = self.cli("file", "demo", "demo", g, "--plain", "--source", "recording")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.film, "assets.json")) as fh:
            a = json.load(fh)
        self.assertEqual(a["films/demo/audio/vo/demo/demo-1.wav"]["via"], "your AI's acme-voices connector")
        self.assertEqual((a["films/demo/audio/vo/demo/demo-2.wav"]["source"], a["films/demo/audio/vo/demo/demo-2.wav"]["via"]), ("recording", "recorded by a person"))

    def test_a_film_without_voice_lines_says_so(self):
        with open(os.path.join(self.film, "cues.json")) as f:
            cues = json.load(f)
        del cues["film"]
        with open(os.path.join(self.film, "cues.json"), "w") as f:
            json.dump(cues, f)
        code, out = self.cli("status", "demo")
        self.assertEqual(code, 1, out)
        self.assertIn("no voice lines yet", out)
        self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()
