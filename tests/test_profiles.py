"""Profiles (spliced/profiles.py): the looks a project's films are made in, kept in profiles/<slug>/ and built up over time."""
import json, os, shutil, subprocess, sys, unittest

import support


class Profiles(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args], env={**env, "SPLICED_OFFLINE": "1"},
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def profile(self, slug):
        with open(os.path.join(self.root, "profiles", slug, "profile.json")) as f:
            return json.load(f)

    def test_a_project_from_before_profiles_gets_its_first_one_once(self):
        house = os.path.join(self.root, "remotion", "docs", "HOUSE.md")
        os.makedirs(os.path.dirname(house), exist_ok=True)
        with open(house, "w") as f:
            f.write("# House\n\nAlways dark. Never bounce.\n")
        code, out = self.cli("profile", "setup")
        self.assertEqual(code, 0, out)
        p = self.profile("fixture")
        self.assertEqual((p["name"], p["kind"], p["default"]), ("Fixture", "house", True), "the brand in spliced.json names it")
        with open(os.path.join(self.root, "profiles", "fixture", "PROFILE.md")) as f:
            self.assertIn("Always dark. Never bounce.", f.read(), "the house rules are its words")
        self.assertTrue(os.path.isfile(house), "HOUSE.md stays where it was")
        self.cli("profile", "set", "fixture", "--about", "changed by hand")
        self.cli("profile", "setup")
        self.assertEqual(self.profile("fixture")["about"], "changed by hand", "a second run changes nothing")
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "profiles"))), ["fixture"])

    def test_a_project_with_nothing_to_take_in_gets_none(self):
        with open(os.path.join(self.root, "spliced.json"), "w") as f:
            json.dump({"format": 1, "name": "Empty", "brand": {"name": ""}}, f)
        code, out = self.cli("profile", "setup")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "profiles")))

    def test_profiles_are_made_kept_and_chosen(self):
        self.assertEqual(self.cli("profile", "new", "Acme house", "--kind", "house")[0], 0)
        self.assertTrue(self.profile("acme-house")["default"], "the first profile is the default")
        code, out = self.cli("profile", "new", "Soft glass", "--from-film", "demo-one", "--motion", "apple")
        self.assertEqual(code, 0, out)
        g = self.profile("soft-glass")
        self.assertEqual((g["kind"], g["motion"], g["from_film"], g["default"]), ("exploration", "apple", "demo-one", False))
        self.assertEqual(g["palette"], [{"hex": "#FFFFFF", "name": "white stage"}], "a film's palette comes with it")
        self.assertEqual(g["scenes"], ["demo-one/s01"], "and the scenes of its signature moves")
        self.cli("profile", "learn", "soft-glass", "Hold the end card two seconds", "--from", "demo note 1")
        self.cli("profile", "learn", "soft-glass", "hold the end card two seconds")
        self.assertEqual([r["text"] for r in self.profile("soft-glass")["rules"]], ["Hold the end card two seconds"], "a rule is kept once")
        code, out = self.cli("profile", "show", "soft-glass")
        for bit in ("# Profile: Soft glass", "motion profile `apple`", "1. Hold the end card two seconds (from demo note 1)", "`demo-one/s01`"):
            self.assertIn(bit, out)
        self.cli("profile", "default", "soft-glass")
        self.assertEqual((self.profile("soft-glass")["default"], self.profile("acme-house")["default"]), (True, False), "one default at a time")
        self.cli("profile", "default", "none")
        self.assertFalse(self.profile("soft-glass")["default"])
        self.assertNotEqual(self.cli("profile", "new", "soft glass")[0], 0, "never two of one name")
        code, out = self.cli("profile", "set", "soft-glass", "--motion", "wobbly")
        self.assertNotEqual(code, 0)
        self.assertIn("motion is one of", out)
        code, out = self.cli("profile", "remove", "soft-glass")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "profiles", "soft-glass")))
        kept = os.path.join(self.root, ".cache", "profiles-removed")
        self.assertTrue(any(os.path.isdir(os.path.join(kept, d, "soft-glass")) for d in os.listdir(kept)), "a removed profile is kept first")

    def test_a_board_and_its_film_are_made_in_a_profile(self):
        self.cli("profile", "new", "Acme house", "--kind", "house")
        code, out = self.cli("board", "show", "Fixture board")
        self.assertIn("Profile: Acme house (acme-house), the default · motion soft", out)
        self.cli("board", "brief", "Fixture board", "--style", "none", "--motion", "apple")
        code, out = self.cli("board", "show", "Fixture board")
        self.assertIn("Profile: none (recreate the references as they are) · motion apple", out)
        self.cli("board", "brief", "Fixture board", "--style", "default")
        with open(os.path.join(self.root, "library", "state.json")) as f:
            self.assertNotIn("style", json.load(f)["boards"]["Fixture board"], "default: the board follows the project's default")
        self.cli("board", "new", "Study", "--from-film", "demo-two")
        with open(os.path.join(self.root, "library", "state.json")) as f:
            self.assertEqual(json.load(f)["boards"]["Study"]["style"], "none", "a study of one film is in its own look")
        code, out = self.cli("film", "new", "fixture-launch", "--board", "Fixture board")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, "remotion", "src", "films", "fixture-launch", "storyboard.json")) as f:
            self.assertEqual(json.load(f)["style"], "acme-house", "a film keeps the profile it was started in, even if the default changes later")
        code, out = self.cli("film", "status", "fixture-launch")
        self.assertIn("profile show acme-house", out)


@unittest.skipUnless(shutil.which("uv"), "needs uv")
class ProfilesOverTheServer(unittest.TestCase):
    def test_the_app_reads_and_changes_profiles(self):
        import socket, http.client, time
        root = support.project(self)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        proc = subprocess.Popen([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), "--port", str(port), "--no-open"],
                                env={**env, "SPLICED_PROJECT": root, "SPLICED_NO_UPDATE_CHECK": "1"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: (proc.terminate(), proc.wait(timeout=5)))

        def req(method, path, body=None, headers=None):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers={"Host": f"localhost:{port}", **(headers or {})})
            r = c.getresponse()
            out = (r.status, json.loads(r.read() or b"{}"))
            c.close()
            return out
        for _ in range(900):
            try:
                if req("GET", "/api/info")[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        self.assertEqual(req("GET", "/api/profiles")[1]["profiles"], [])
        code, j = req("POST", "/api/profiles", {"op": "house"})
        self.assertEqual((code, j["profile"], j["default"]), (200, "fixture", "fixture"))
        code, j = req("POST", "/api/profiles", {"op": "learn", "profile": "fixture", "text": "Never bounce the logo", "from": "the person"})
        self.assertEqual(j["profiles"][0]["rules"][0]["text"], "Never bounce the logo")
        code, j = req("POST", "/api/profiles", {"op": "set", "profile": "fixture", "md": "Dark stage, one headline at a time."})
        self.assertEqual(j["profiles"][0]["md"], "Dark stage, one headline at a time.")
        self.assertEqual(req("POST", "/api/profiles", {"op": "pin", "profile": "fixture", "scene": "../../etc"})[0], 400)
        self.assertEqual(req("POST", "/api/profiles", {"op": "set", "profile": "../x", "about": "x"})[0], 400, "a profile is a name, never a path")
        self.assertEqual(req("POST", "/api/profiles", {"op": "learn", "profile": "fixture", "text": "x"}, headers={"Origin": "http://evil.test"})[0], 403)


if __name__ == "__main__":
    unittest.main()
