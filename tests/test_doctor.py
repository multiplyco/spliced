"""spliced doctor: what is set up, what each thing unlocks, and the next step."""
import json, os, shutil, subprocess, sys, unittest

import support


@unittest.skipUnless(shutil.which("uv"), "needs uv")
class Doctor(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        # a machine with everything on it, whatever this one has: stand-in programs that only answer --version
        self.bin = os.path.join(os.path.dirname(self.root), "bin")
        self.home = os.path.join(os.path.dirname(self.root), "home")   # an empty home: the AI apps this machine really has don't count
        os.makedirs(self.bin)
        os.makedirs(self.home)
        for name in ("uv", "ffmpeg", "ffprobe", "yt-dlp", "claude", "node"):
            with open(os.path.join(self.bin, name), "w") as f:
                f.write(f"#!/bin/sh\necho '{name} 1.2.3'\n")
            os.chmod(os.path.join(self.bin, name), 0o755)

    def doctor(self, *args, path=None, **env):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_")) and not k.endswith(("_API_KEY", "_ACCESS_KEY"))}
        e["PATH"] = (self.bin + os.pathsep + "/usr/bin" + os.pathsep + "/bin") if path is None else path
        e["HOME"] = self.home
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "doctor", *args], env={**e, **env}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def items(self, **kw):
        d = json.loads(self.doctor("--json", **kw))
        return d, {i["id"]: i for i in d["items"]}

    def test_every_item_says_what_it_unlocks_and_how_to_get_it(self):
        d, items = self.items()
        self.assertEqual([l["id"] for l in d["levels"]], ["browse", "collect", "analyse", "make", "generate"])
        for i in d["items"]:
            self.assertIn(i["state"], ("ok", "missing", "off"), i["id"])
            self.assertTrue(i["label"] and i["detail"] and i["unlocks"], i["id"])
            self.assertIn(i["level"], [l["id"] for l in d["levels"]])
            if i["state"] != "ok":
                self.assertTrue(i["fix"], f"{i['id']} is not set up and doesn't say how to")
        self.assertEqual((items["project"]["state"], items["library"]["detail"]), ("ok", "2 films broken down"))
        self.assertEqual([items[x]["state"] for x in ("uv", "ffmpeg", "yt-dlp", "agent", "node", "spliced")], ["ok"] * 6)
        self.assertNotIn("ffprobe", items, "ffprobe ships with ffmpeg: one line, not two")
        self.assertEqual((items["yt-dlp"]["detail"], items["agent"]["detail"]), ("yt-dlp 1.2.3", "Claude on this machine"))

    def test_the_fixture_before_and_after_agents_install(self):
        d, items = self.items()
        self.assertEqual((items["skills"]["state"], items["mcp"]["state"], items["runner"]["state"]), ("missing", "off", "ok"))
        self.assertEqual(d["next"], "skills")
        self.assertFalse(next(l for l in d["levels"] if l["id"] == "analyse")["ready"])
        subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "agents", "install"], check=True, capture_output=True)
        d, items = self.items()
        self.assertEqual((items["skills"]["state"], items["mcp"]["state"]), ("ok", "ok"))
        mine = os.path.join(self.root, ".claude", "skills", "add-reference", "SKILL.md")
        with open(mine, "a") as f:
            f.write("\nedited by hand\n")
        i = self.items()[1]["skills"]
        self.assertEqual((i["state"], i["detail"]), ("ok", "Installed; your changes to add-reference are kept"), "a skill the person changed is theirs, not a fault")
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "agents", "install"], check=True, capture_output=True, text=True)
        self.assertIn("your changes to SKILL.md are kept", r.stdout)
        with open(mine) as f:
            self.assertTrue(f.read().endswith("\nedited by hand\n"), "installing again never writes over it")
        # a copy from before Spliced kept a record, that differs: it can't be told from an old version, so it is flagged,
        # replaced when asked, and the old one is kept where no agent reads it
        os.remove(os.path.join(self.root, ".claude", "skills", ".spliced.json"))
        self.assertEqual(self.items()[1]["skills"]["detail"], "add-reference: older")
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "agents", "install"], check=True, capture_output=True, text=True)
        self.assertIn("what was replaced is kept in .cache/skills-kept/", r.stdout)
        kept = os.path.join(self.root, ".cache", "skills-kept")
        with open(os.path.join(kept, os.listdir(kept)[0], "add-reference", "SKILL.md")) as f:
            self.assertTrue(f.read().endswith("\nedited by hand\n"))
        self.assertEqual(self.items()[1]["skills"]["detail"], "Installed")

    def test_keys_are_named_never_shown(self):
        out = self.doctor("--json")
        self.assertNotIn(support.SENTINEL, out)
        d, items = self.items()
        self.assertIn("Unsplash connected", items["stock"]["detail"])
        with open(os.path.join(self.root, ".env"), "a") as f:
            f.write("ELEVENLABS_API_KEY=" + support.SENTINEL + "\n")
        out = self.doctor()
        self.assertNotIn(support.SENTINEL, out)
        self.assertIn('ElevenLabs key set, but no "voice" in spliced.json yet', out)

    def test_no_service_is_needed_to_make_a_film(self):
        d, items = self.items()
        self.assertEqual((items["voice"]["state"], items["voice"]["optional"], items["music"]["state"]), ("off", True, "ok"))
        self.assertIn("not needed", items["voice"]["detail"])
        self.assertTrue(next(l for l in d["levels"] if l["id"] == "generate")["ready"], "nothing in Generate holds a film back")
        cfg_path = os.path.join(self.root, "spliced.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        cfg["voice"] = {"provider": "acme-voices", "name": "Ada"}   # another voice service than the one Spliced calls itself
        with open(cfg_path, "w") as f:
            json.dump(cfg, f)
        i = self.items()[1]["voice"]
        self.assertEqual((i["state"], i["detail"]), ("ok", "Read by acme-voices, through your AI"))

    def test_other_agents_count_too(self):
        for name in ("gemini", "cursor-agent"):
            with open(os.path.join(self.bin, name), "w") as f:
                f.write("#!/bin/sh\necho 1\n")
            os.chmod(os.path.join(self.bin, name), 0o755)
        self.assertEqual(self.items()[1]["agent"]["detail"], "Claude, Gemini CLI, Cursor on this machine")
        os.remove(os.path.join(self.bin, "claude"))
        os.remove(os.path.join(self.bin, "cursor-agent"))
        i = self.items()[1]["agent"]
        self.assertEqual((i["state"], i["detail"]), ("ok", "Gemini CLI on this machine"))

    def test_ffmpeg_without_a_package_manager(self):
        # no Homebrew: the fix is one command that needs no password, and what it installs is found under its own names
        # (only the stand-in programs are looked for: a machine that has a real ffmpeg in /usr/bin would never be without one)
        os.remove(os.path.join(self.bin, "ffmpeg"))
        os.remove(os.path.join(self.bin, "ffprobe"))
        i = self.items(path=self.bin)[1]["ffmpeg"]
        self.assertEqual((i["state"], i["fix"]), ("missing", "uv tool install static-ffmpeg"))
        real = os.path.join(os.path.dirname(self.root), "static")
        os.makedirs(real)
        for name in ("ffmpeg", "ffprobe"):
            with open(os.path.join(real, name), "w") as f:
                f.write(f"#!/bin/sh\necho '{name} version 7.0 static'\n")
            os.chmod(os.path.join(real, name), 0o755)
        with open(os.path.join(self.bin, "static_ffmpeg_paths"), "w") as f:
            f.write(f"#!/bin/sh\necho 'FFMPEG={real}/ffmpeg'\necho 'FFPROBE={real}/ffprobe'\n")
        os.chmod(os.path.join(self.bin, "static_ffmpeg_paths"), 0o755)
        i = self.items(path=self.bin)[1]["ffmpeg"]
        self.assertEqual((i["state"], i["detail"]), ("ok", "ffmpeg version 7.0 static"))
        link = os.path.join(self.root, ".cache", "bin", "ffprobe")
        self.assertEqual(os.path.realpath(link), os.path.realpath(os.path.join(real, "ffprobe")), "linked under the name every tool uses")

    def test_a_newer_spliced_is_said_from_what_is_already_known(self):
        self.assertEqual(self.items()[1]["spliced"]["state"], "ok")
        os.makedirs(os.path.join(self.root, ".cache"), exist_ok=True)
        with open(os.path.join(self.root, ".cache", "update.json"), "w") as f:
            json.dump({"latest": "99.0.0", "checked": 4102444800}, f)   # (checked far in the future: never stale)
        i = self.items(SPLICED_UPDATE_URL="file:///nonexistent/doctor-never-asks")[1]["spliced"]
        self.assertEqual((i["state"], i["optional"]), ("off", True))
        self.assertIn("99.0.0 is out", i["detail"])

    def test_a_machine_with_nothing_installed_still_gets_an_answer(self):
        d, items = self.items(path="/nonexistent")
        for exe in ("uv", "ffmpeg", "yt-dlp", "agent", "node"):
            self.assertEqual(items[exe]["state"], "missing", exe)
        self.assertEqual(d["next"], "uv")
        ready = {l["id"]: l["ready"] for l in d["levels"]}
        self.assertEqual(ready, {"browse": False, "collect": False, "analyse": False, "make": False, "generate": True})
        text = self.doctor(path="/nonexistent")
        self.assertIn("✗ ffmpeg: Not found", text)
        self.assertIn("Next: uv", text)

    def test_a_runner_that_is_chosen_but_not_installed_is_a_fault(self):
        d, items = self.items(path="/nonexistent", SPLICED_RUNNER="claude")
        self.assertEqual(items["runner"]["state"], "missing")
        self.assertIn("claude isn't installed", items["runner"]["detail"])

    def test_the_apps_real_code(self):
        d, items = self.items()
        i = items["app-code"]
        self.assertEqual((i["state"], i["optional"], i["level"]), ("off", True, "make"))
        self.assertIn('"app": {"code"', i["fix"])
        cfg_path = os.path.join(self.root, "spliced.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        os.makedirs(os.path.join(self.root, "app-src"))
        for value, state, says in (("app-src", "ok", "app-src"), (["app-src", "https://github.com/acme/app"], "ok", "github.com/acme/app"),
                                   (["~/no/such/folder-for-spliced-tests", "github.com/acme/app"], "ok", "github.com/acme/app (~/no/such/folder-for-spliced-tests isn't on this machine)"),
                                   ("~/no/such/folder-for-spliced-tests", "missing", "isn't on this machine")):
            cfg["app"] = {"code": value}
            with open(cfg_path, "w") as f:
                json.dump(cfg, f)
            i = self.items()[1]["app-code"]
            self.assertEqual(i["state"], state, value)
            self.assertIn(says, i["detail"])
        self.assertFalse(i["optional"], "a folder that is named but not there is a fault, and the next thing to fix")
        subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "agents", "install"], check=True, capture_output=True)
        with open(os.path.join(self.root, "AGENTS.md")) as f:
            self.assertIn("The product's real code is at `~/no/such/folder-for-spliced-tests`", f.read(), "the agent is told where to look")

    def test_the_render_engine(self):
        d, items = self.items()
        self.assertEqual(items["engine"]["state"], "off", "the fixture has films but no Remotion project")
        with open(os.path.join(self.root, "remotion", "package.json"), "w") as f:
            f.write("{}")
        d, items = self.items()
        self.assertEqual(items["engine"]["state"], "missing", "a clone without its packages")
        self.assertIn("kit packages", items["engine"]["fix"])
        self.assertIn("kit install", self.items()[1]["kit"]["fix"])
        os.makedirs(os.path.join(self.root, "remotion", "node_modules", "remotion"))
        d, items = self.items()
        self.assertEqual((items["engine"]["state"], items["engine"]["detail"]), ("ok", "Remotion in remotion/, 1 film"))


if __name__ == "__main__":
    unittest.main()
