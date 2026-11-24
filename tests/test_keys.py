"""spliced keys: a service key is pasted by the person, kept in .env, and never shown, passed in, or opened by an agent."""
import json, os, subprocess, sys, unittest

import support


class Keys(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)

    def cli(self, *args, stdin=""):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_", "ELEVENLABS_", "PEXELS_", "PIXABAY_", "UNSPLASH_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args],
                           input=stdin, env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_the_list_names_keys_and_never_shows_one(self):
        code, out = self.cli("keys")
        self.assertEqual(code, 0, out)
        self.assertIn("✓ set", out)                       # the fixture's Unsplash key
        self.assertRegex(out, r"· not set +elevenlabs")
        self.assertNotIn(support.SENTINEL, out)

    def test_a_key_is_never_passed_in(self):
        code, out = self.cli("keys", "set", "elevenlabs", "sk_abcdefghijklmnop")
        self.assertNotEqual(code, 0)
        self.assertIn("shell's history", out)
        code, out = self.cli("keys", "set", "elevenlabs", stdin="sk_abcdefghijklmnop\n")   # an agent piping it in
        self.assertNotEqual(code, 0)
        self.assertIn("pasted by a person", out)
        with open(os.path.join(self.root, ".env")) as f:
            self.assertNotIn("ELEVENLABS", f.read())

    def test_remove(self):
        code, out = self.cli("keys", "remove", "unsplash")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, ".env")) as f:
            self.assertNotIn("UNSPLASH", f.read())
        self.assertIn("was not in", self.cli("keys", "remove", "unsplash")[1])

    def test_agents_install_fences_env_off_from_claude_code(self):
        os.makedirs(os.path.join(self.root, ".claude"), exist_ok=True)
        with open(os.path.join(self.root, ".claude", "settings.json"), "w") as f:
            json.dump({"permissions": {"allow": ["Bash(ls:*)"]}, "model": "x"}, f)
        code, out = self.cli("agents", "install")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, ".claude", "settings.json")) as f:
            st = json.load(f)
        self.assertEqual(st["model"], "x", "the project's own settings stay")
        self.assertEqual(st["permissions"]["allow"], ["Bash(ls:*)"])
        self.assertIn("Read(./.env)", st["permissions"]["deny"])
        self.cli("agents", "install")
        with open(os.path.join(self.root, ".claude", "settings.json")) as f:
            self.assertEqual(json.load(f)["permissions"]["deny"].count("Read(./.env)"), 1, "once, however often it runs")
        with open(os.path.join(self.root, "AGENTS.md")) as f:
            self.assertIn("Never open, print, copy or ask for `.env`", f.read())


if __name__ == "__main__":
    unittest.main()
