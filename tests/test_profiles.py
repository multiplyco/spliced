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
        self.assertEqual((p["name"], p["default"], p["motion"]), ("Fixture", True, {"base": "soft"}), "the brand in spliced.json names it")
        with open(os.path.join(self.root, "profiles", "fixture", "PROFILE.md")) as f:
            self.assertIn("Always dark. Never bounce.", f.read(), "the house rules are its words")
        self.assertTrue(os.path.isfile(house), "HOUSE.md stays where it was")
        self.cli("profile", "set", "fixture", "--about", "changed by hand")
        self.cli("profile", "setup")
        self.assertEqual(self.profile("fixture")["about"], "changed by hand", "a second run changes nothing")
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "profiles"))), ["fixture"])

    def test_the_colours_house_rules_name_become_the_palette(self):
        house = os.path.join(self.root, "remotion", "docs", "HOUSE.md")
        os.makedirs(os.path.dirname(house), exist_ok=True)
        with open(house, "w") as f:
            f.write("Type on ink `#0B152B`, the stage paper (#F9F9F9), one accent: highlight `#615ff8`. Again ink #0B152B.\n")
        self.cli("profile", "setup")
        self.assertEqual(self.profile("fixture")["palette"], [{"hex": "#0B152B", "name": "ink"}, {"hex": "#F9F9F9", "name": "paper"}, {"hex": "#615FF8", "name": "highlight"}])

    def test_the_person_asks_their_ai_for_a_change(self):
        self.cli("profile", "new", "Calm")
        code, out = self.cli("profile", "ask", "calm", "make it warmer")
        self.assertEqual(code, 0, out)
        self.cli("profile", "ask", "calm", "and slower")
        code, out = self.cli("imports", "next")
        self.assertIn("Change the Spliced profile `calm`", out)
        self.assertIn("make it warmer\nand slower", out, "a second request joins the first while it waits")
        self.assertEqual(len([ln for ln in self.cli("imports", "list")[1].splitlines() if ln.strip()]), 1)

    def test_a_project_with_nothing_to_take_in_gets_none(self):
        with open(os.path.join(self.root, "spliced.json"), "w") as f:
            json.dump({"format": 1, "name": "Empty", "brand": {"name": ""}}, f)
        code, out = self.cli("profile", "setup")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "profiles")))

    def test_profiles_are_made_kept_and_chosen(self):
        self.assertEqual(self.cli("profile", "new", "Acme house")[0], 0)
        self.assertTrue(self.profile("acme-house")["default"], "the first profile is the default")
        code, out = self.cli("profile", "new", "Soft glass", "--from-film", "demo-one", "--motion", "apple")
        self.assertEqual(code, 0, out)
        g = self.profile("soft-glass")
        self.assertEqual((g["motion"]["base"], g["from_film"], g["default"]), ("apple", "demo-one", False))
        self.assertEqual(g["palette"], [{"hex": "#FFFFFF", "name": "white stage"}], "a film's palette comes with it")
        self.assertEqual(g["scenes"], ["demo-one/s01"], "and the scenes of its signature moves")
        self.cli("profile", "learn", "soft-glass", "Hold the end card two seconds", "--from", "demo note 1")
        self.cli("profile", "learn", "soft-glass", "hold the end card two seconds")
        self.assertEqual([r["text"] for r in self.profile("soft-glass")["rules"]], ["Hold the end card two seconds"], "a rule is kept once")
        code, out = self.cli("profile", "show", "soft-glass")
        for bit in ("# Profile: Soft glass", "Base: `apple`", "1. Hold the end card two seconds (from demo note 1)", "`demo-one/s01`"):
            self.assertIn(bit, out)
        self.cli("profile", "default", "soft-glass")
        self.assertEqual((self.profile("soft-glass")["default"], self.profile("acme-house")["default"]), (True, False), "one default at a time")
        self.cli("profile", "default", "none")
        self.assertFalse(self.profile("soft-glass")["default"])
        self.assertNotEqual(self.cli("profile", "new", "soft glass")[0], 0, "never two of one name")
        code, out = self.cli("profile", "motion", "soft-glass", "--base", "wobbly")
        self.assertNotEqual(code, 0)
        self.assertIn("the base is one of", out)
        code, out = self.cli("profile", "remove", "soft-glass")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "profiles", "soft-glass")))
        kept = os.path.join(self.root, ".cache", "profiles-removed")
        self.assertTrue(any(os.path.isdir(os.path.join(kept, d, "soft-glass")) for d in os.listdir(kept)), "a removed profile is kept first")

    def test_a_profile_changes_what_it_wants_of_its_base_motion(self):
        self.cli("profile", "new", "Calm")
        code, out = self.cli("profile", "motion", "calm", "--pace", "1.3", "--bounce", "0", "--transition", "blurThrough", "--text", "greyToInk")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.profile("calm")["motion"], {"base": "soft", "pace": 1.3, "bounce": 0.0, "transition": ["blur"], "text": ["grey-to-ink"]}, "old names read as their new ones")
        self.cli("profile", "motion", "calm", "--transition", "whip, blur, whip", "--text", "typewriter,grey-to-ink")
        self.assertEqual((self.profile("calm")["motion"]["transition"], self.profile("calm")["motion"]["text"]), (["whip", "blur"], ["typewriter", "grey-to-ink"]), "as many as fit, in order, each once")
        self.cli("profile", "motion", "calm", "--transition", "blur")
        code, out = self.cli("profile", "show", "calm")
        for bit in ("Base: `soft`", "- pace: 1.3", "  - blur: blur out of one scene", "  - typewriter (leads): typed letter by letter; no kit helper", "  - grey-to-ink: words land light grey", "remotion/src/profiles.ts"):
            self.assertIn(bit, out)
        self.cli("profile", "motion", "calm", "--bounce", "base", "--base", "apple")
        self.assertEqual(self.profile("calm")["motion"], {"base": "apple", "pace": 1.3, "transition": ["blur"], "text": ["typewriter", "grey-to-ink"]}, "base resets one, the rest stay")
        for bad in (("--pace", "9"), ("--transition", "teleport"), ("--stagger", "fast")):
            code, out = self.cli("profile", "motion", "calm", *bad)
            self.assertNotEqual(code, 0, bad)
        with open(os.path.join(self.root, "profiles", "calm", "profile.json"), "w") as f:
            json.dump({"name": "Calm", "motion": "material", "kind": "house"}, f)
        code, out = self.cli("profile", "show", "calm")
        self.assertIn("Base: `material`", out, "a profile written before motion had knobs still reads")

    def test_a_motion_can_be_saved_and_started_from(self):
        self.cli("profile", "new", "Calm")
        self.cli("profile", "motion", "calm", "--pace", "1.4", "--text", "greyToInk")
        code, out = self.cli("profile", "save-motion", "calm", "Slow ink")
        self.assertEqual(code, 0, out)
        code, out = self.cli("profile", "motions")
        self.assertIn("slow-ink", out)
        self.cli("profile", "new", "Other")
        self.cli("profile", "motion", "other", "--bounce", "0.3")
        self.cli("profile", "motion", "other", "--from", "slow-ink")
        self.assertEqual(self.profile("other")["motion"], {"base": "soft", "from": "slow-ink", "pace": 1.4, "text": ["grey-to-ink"]}, "starting again drops what it had")
        self.cli("profile", "motion", "other", "--from", "apple")
        self.assertEqual(self.profile("other")["motion"], {"base": "apple", "from": "apple"})
        self.assertNotEqual(self.cli("profile", "save-motion", "calm", "soft")[0], 0, "a saved motion can't take a kit motion's name")

    def test_a_profile_is_drafted_from_what_is_dropped_on_it(self):
        brief = os.path.join(os.path.dirname(self.root), "brand book.txt")
        with open(brief, "w") as f:
            f.write("Colours: #0B1B3F midnight. Never stretch the logo.\n")
        bad = os.path.join(os.path.dirname(self.root), "tool.sh")
        open(bad, "w").close()
        self.assertNotEqual(self.cli("profile", "draft", "Globex", bad)[0], 0, "only files Spliced can read")
        code, out = self.cli("profile", "draft", "Globex", brief)
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "profiles", "globex", "sources", "brand book.txt")))
        code, out = self.cli("imports", "next")
        self.assertIn("Draft the Spliced profile `globex`", out)
        self.assertIn("profiles/globex/sources/brand book.txt", out)
        jid = out.split()[1]
        code, out = self.cli("imports", "done", jid)
        self.assertNotEqual(code, 0, "not done until the agent says the profile is drafted")
        self.cli("profile", "drafted", "globex")
        code, out = self.cli("imports", "done", jid)
        self.assertEqual(code, 0, out)
        self.assertIn("What it was drafted from", self.cli("profile", "show", "globex")[1])

    def test_typefaces_say_where_they_come_from(self):
        self.cli("profile", "new", "Calm")
        self.cli("profile", "set", "calm", "--font", "Space Grotesk", "--font-source", "google", "--text-font", "Helvetica", "--text-font-source", "local")
        out = self.cli("profile", "show", "calm")[1]
        self.assertIn("headlines in Space Grotesk (Google Fonts: load it with @remotion/google-fonts)", out)
        self.assertIn("text in Helvetica (installed on this Mac)", out)
        self.assertNotEqual(self.cli("profile", "set", "calm", "--font-source", "dropbox")[0], 0)

    def test_a_board_and_its_film_are_made_in_a_profile(self):
        self.cli("profile", "new", "Acme house")
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
            raw = r.read()
            try:
                out = (r.status, json.loads(raw or b"{}"))
            except ValueError:
                out = (r.status, {})
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
        code, j = req("POST", "/api/profiles", {"op": "set", "profile": "fixture", "md": "Dark stage, one headline at a time.", "font": "Inter",
                                                "palette": [{"hex": "#111111", "name": "ink"}, {"hex": "javascript:x"}], "motion": {"pace": 1.2, "transition": "fadeThrough"}})
        f = j["profiles"][0]
        self.assertEqual((f["md"], f["font"], f["palette"], f["motion"]), ("Dark stage, one headline at a time.", "Inter", [{"hex": "#111111", "name": "ink"}],
                                                                          {"base": "soft", "pace": 1.2, "transition": ["fade"]}), "a colour that isn't one is dropped")
        self.assertEqual(req("POST", "/api/profiles", {"op": "set", "profile": "fixture", "motion": {"pace": 40}})[0], 400)
        g = req("GET", "/api/profiles")[1]
        self.assertIn("soft", g["kit"])
        self.assertEqual(g["knobs"]["transition"]["allowed"][:4], ["cut", "cut-on-beat", "match-cut", "blur"])
        self.assertEqual(req("POST", "/api/profiles", {"op": "pin", "profile": "fixture", "scene": "../../etc"})[0], 400)
        self.assertEqual(req("POST", "/api/profiles", {"op": "set", "profile": "../x", "about": "x"})[0], 400, "a profile is a name, never a path")
        self.assertEqual(req("POST", "/api/profiles", {"op": "learn", "profile": "fixture", "text": "x"}, headers={"Origin": "http://evil.test"})[0], 403)
        fonts = req("GET", "/api/fonts")[1]
        self.assertIsInstance(fonts["installed"], list)
        self.assertIs(fonts["google"], True)
        code, j = req("POST", "/api/profiles", {"op": "motion-save", "profile": "fixture", "name": "House glide"})
        self.assertIn("house-glide", [m["slug"] for m in j["motions"]])
        self.assertEqual(req("POST", "/api/profiles", {"op": "motion-remove", "motion": "house-glide"})[0], 200)

        def upload(name, data, slug="fixture"):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("POST", f"/api/profiles/{slug}/sources", body=data, headers={"Host": f"localhost:{port}", "X-Filename": name})
            r = c.getresponse(); out = (r.status, json.loads(r.read() or b"{}")); c.close()
            return out
        code, j = upload("..%2F..%2Fbrand.pdf", b"%PDF-1.4")
        self.assertEqual((code, j["file"]), (200, "profiles/fixture/sources/brand.pdf"), "a file's name is only ever its own, inside sources/")
        self.assertEqual(upload("run.sh", b"#!/bin/sh")[0], 400)
        self.assertEqual(upload("x.pdf", b"x", slug="nope")[0], 400)
        self.assertEqual(req("GET", "/project/profiles/fixture/profile.json")[0], 404, "a profile's JSON is never served")


if __name__ == "__main__":
    unittest.main()
