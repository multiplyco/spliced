"""spliced update: whether a newer Spliced is out, asked rarely, of a stand-in here, and never when told not to."""
import json, os, shutil, subprocess, sys, unittest

import support


class Update(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.latest = os.path.join(os.path.dirname(self.root), "latest.json")   # what the registry would answer
        self.say("99.1.0")

    def say(self, version):
        with open(self.latest, "w") as f:
            json.dump({"name": "spliced-app", "version": version}, f)

    def update(self, *args, **env):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "update", *args],
                           env={**e, "SPLICED_UPDATE_URL": "file://" + self.latest, **env}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_a_newer_one_is_said_with_the_command_that_gets_it(self):
        u = json.loads(self.update("--json"))
        self.assertEqual((u["latest"], u["newer"], u["off"]), ("99.1.0", True, False))
        self.assertTrue(u["command"] or u["how"])
        text = self.update()
        self.assertIn("Spliced 99.1.0 is out", text)
        self.assertIn("setup` brings this project's skills and film kit up to date", text)

    def test_it_asks_once_a_day_not_every_time(self):
        self.update()
        self.say("99.2.0")
        self.assertEqual(json.loads(self.update("--known", "--json"))["latest"], "99.1.0", "--known never asks")
        with open(os.path.join(self.root, ".cache", "update.json")) as f:
            kept = json.load(f)
        self.assertEqual(kept["latest"], "99.1.0")
        sys.path.insert(0, support.TOOLS)
        import updates
        self.assertTrue(updates.newer("0.10.0", "0.9.9") and not updates.newer("0.9.9", "0.9.9") and not updates.newer("soon", "0.1.0"))

    def test_the_same_or_an_older_one_is_not_news(self):
        self.say("0.0.0")
        u = json.loads(self.update("--json"))
        self.assertEqual((u["newer"], u["latest"]), (False, "0.0.0"))
        self.assertIn("is the newest", self.update("--known"))

    def test_until_it_is_published_nothing_is_asked_and_no_install_command_is_shown(self):
        # without the stand-in address, the real registry would be asked: before publishing, it never is
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "update", "--json"], env=e, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        u = json.loads(r.stdout)
        sys.path.insert(0, support.TOOLS)
        import updates
        if not updates.PUBLISHED:
            self.assertEqual((u["off"], u["published"], u["command"], u["latest"]), (True, False, "", None))
            self.assertFalse(os.path.exists(os.path.join(self.root, ".cache", "update.json")), "nothing was asked")
            self.assertNotIn("spliced-app", r.stdout, "no command that names a package that isn't ours yet")

    def test_it_can_be_turned_off_and_an_unreachable_registry_is_no_error(self):
        u = json.loads(self.update("--json", SPLICED_NO_UPDATE_CHECK="1"))
        self.assertEqual((u["off"], u["latest"]), (True, None))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".cache", "update.json")), "turned off: nothing was asked")
        u = json.loads(self.update("--json", SPLICED_UPDATE_URL="file:///nonexistent/spliced-latest.json"))
        self.assertEqual((u["newer"], u["latest"]), (False, None))
        self.assertIn("Couldn't tell", self.update("--known", SPLICED_UPDATE_URL="file:///nonexistent/spliced-latest.json"))
        cfg = os.path.join(self.root, "spliced.json")
        with open(cfg) as f:
            c = json.load(f)
        c["updates"] = False
        with open(cfg, "w") as f:
            json.dump(c, f)
        self.assertTrue(json.loads(self.update("--json"))["off"], 'spliced.json "updates": false')


if __name__ == "__main__":
    unittest.main()
