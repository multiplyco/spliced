"""Import jobs and who does their reading (spliced/importer.py, tools/runners.py), on a throwaway copy of the fixture.
No network and no real agent: the film is already downloaded and analysed, and `claude` is a stand-in script."""
import json, os, shutil, stat, subprocess, sys, time, unittest

import support

FAKE_CLAUDE = r'''#!/usr/bin/env python3
"""A stand-in for the Claude CLI: records how it was called, does the 'work' (puts the breakdown in place), and
speaks Claude Code's stream-json."""
import json, os, shutil, sys
with open(os.environ["FAKE_CLAUDE_LOG"], "w") as f:
    json.dump(sys.argv[1:], f)
shutil.copy(os.environ["FAKE_BREAKDOWN"], os.path.join(os.getcwd(), "library", "references", "demo-one", "breakdown.json"))
for ev in ({"type": "assistant", "message": {"content": [{"type": "text", "text": "Reading the sheets."}]}},
           {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "/x/sheets/overview.jpg"}}]}},
           {"type": "result", "result": "Two scenes, one move.\nSLUG: demo-one", "total_cost_usd": 0.42}):
    print(json.dumps(ev), flush=True)
'''


@unittest.skipUnless(shutil.which("uv"), "needs uv")
class Jobs(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.tmp = os.path.dirname(self.root)
        # a film that is downloaded and analysed but not broken down: the breakdown is set aside as "the agent's work"
        self.bd = os.path.join(self.root, "library", "references", "demo-one", "breakdown.json")
        self.work = os.path.join(self.tmp, "breakdown.json")
        os.rename(self.bd, self.work)
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        fake = os.path.join(self.bin, "claude")
        with open(fake, "w") as f:
            f.write(FAKE_CLAUDE)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.tmp, "claude-argv.json")

    def env(self, **kw):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        e.update(SPLICED_PROJECT=self.root, PATH=self.bin + os.pathsep + e["PATH"], FAKE_CLAUDE_LOG=self.log, FAKE_BREAKDOWN=self.work, **kw)
        return e

    def py(self, code, **kw):
        r = subprocess.run([sys.executable, "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import importer, runners\n" + code, support.TOOLS],
                           env=self.env(**kw), capture_output=True, text=True, cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def cli(self, *args, **kw):
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "importer.py"), *args], env=self.env(**kw), capture_output=True, text=True, cwd=self.root)
        return r.returncode, (r.stdout + r.stderr).strip()

    SEED = ("j = importer.new_job('reference/demo-one.mp4')\n"
            "j.update(film='demo-one', title='Demo one'); j['steps']['download']['status'] = 'done'; j['steps']['analyse']['status'] = 'done'; importer.save(j)\n")

    def job(self, jid):
        with open(os.path.join(self.root, ".cache", "imports", f"{jid}.json")) as f:
            return json.load(f)

    # ---- who is asked
    def test_no_runner_unless_the_project_or_the_person_says_so(self):
        self.assertEqual(self.py("print(runners.name(), runners.argv('p'))"), "none None")
        self.assertEqual(self.py("print(runners.name())", SPLICED_RUNNER="claude"), "claude")
        self.assertEqual(self.py("print(runners.name())", SPLICED_RUNNER="some-other-agent"), "none", "an unknown runner starts nothing")
        with open(os.path.join(self.root, "spliced.json")) as f:
            cfg = json.load(f)
        cfg["agent"] = {"runner": "claude"}
        with open(os.path.join(self.root, "spliced.json"), "w") as f:
            json.dump(cfg, f)
        self.assertEqual(self.py("print(runners.name(), runners.bypass())"), "claude False")
        self.assertEqual(self.py("print(runners.name())", SPLICED_RUNNER="none"), "none", "the environment wins over the project")
        # what the app calls the person's AI follows from the same settings
        self.assertEqual(self.py("print(repr(runners.called()))"), "'Claude'")
        self.assertEqual(self.py("print(repr(runners.called()))", SPLICED_RUNNER="none"), "''")
        cfg["agent"] = {"name": "Codex"}
        with open(os.path.join(self.root, "spliced.json"), "w") as f:
            json.dump(cfg, f)
        self.assertEqual(self.py("print(repr(runners.called()))"), "'Codex'", "the project's own name for it wins")

    def test_a_headless_session_is_fenced_in_unless_bypass_is_asked_for(self):
        fenced = json.loads(self.py("print(json.dumps(runners.argv('the prompt')))", SPLICED_RUNNER="claude"))
        self.assertEqual(fenced[:3], ["claude", "-p", "the prompt"])
        self.assertNotIn("bypassPermissions", fenced)
        self.assertEqual(fenced[fenced.index("--permission-mode") + 1], "acceptEdits")
        allowed = fenced[fenced.index("--allowedTools") + 1].split(",")
        self.assertIn("Bash(spliced library:*)", allowed)
        self.assertIn("Bash(spliced uploads:*)", allowed)
        self.assertFalse([a for a in allowed if a in ("Bash", "Bash(*)", "WebFetch")], "no open-ended shell")
        free = json.loads(self.py("print(json.dumps(runners.argv('p')))", SPLICED_RUNNER="claude", SPLICED_PERMISSIONS="bypass"))
        self.assertEqual(free[free.index("--permission-mode") + 1], "bypassPermissions")
        self.assertNotIn("--allowedTools", free)

    # ---- no runner: the job waits for the person's own AI
    def test_without_a_runner_the_job_waits_and_your_own_ai_finishes_it(self):
        jid = self.py(self.SEED + "importer.work(j); print(j['id'])")
        j = self.job(jid)
        self.assertEqual((j["status"], j["steps"]["breakdown"]["status"], j["activity"]), ("waiting", "waiting", "Waiting for your AI"))
        self.assertIn("add-reference/SKILL.md", j["prompt"])
        self.assertIn("SLUG:", j["prompt"])
        self.assertFalse(os.path.exists(self.log), "nothing was started")

        code, out = self.cli("next")
        self.assertEqual(code, 0, out)
        self.assertIn(f"Import {jid} is waiting for you: Demo one", out)
        self.assertIn(f"done {jid}", out)
        self.assertIn("demo-one", out)

        code, out = self.cli("done", jid)
        self.assertNotEqual(code, 0, "not done until the breakdown is there")
        self.assertIn("no breakdown yet at library/references/demo-one/breakdown.json", out)
        self.assertEqual(self.job(jid)["status"], "waiting")

        shutil.copy(self.work, self.bd)  # the person's agent writes the breakdown
        code, out = self.cli("done", jid)
        self.assertEqual(code, 0, out)
        for _ in range(240):  # the worker it starts builds the library and closes the job
            if self.job(jid)["status"] in ("done", "failed"):
                break
            time.sleep(0.25)
        j = self.job(jid)
        self.assertEqual((j["status"], j["steps"]["library"]["status"], j.get("scenes")), ("done", "done", 2), j.get("error"))
        with open(os.path.join(self.root, ".cache", "library.json")) as f:
            self.assertIn("demo-one", [x["slug"] for x in json.load(f)["films"]])
        code, out = self.cli("next")
        self.assertIn("Nothing is waiting", out)

    def test_the_same_link_is_not_queued_twice_while_it_waits_and_a_wait_can_be_cancelled(self):
        jid = self.py(self.SEED + "importer.work(j); print(j['id'])")
        self.assertEqual(self.py("print(importer.new_job('reference/demo-one.mp4')['id'])"), jid)
        code, out = self.cli("cancel", jid)
        self.assertEqual((code, out), (0, "cancelled"))
        self.assertEqual(self.job(jid)["steps"]["breakdown"]["status"], "cancelled")
        code, out = self.cli("done", jid)
        self.assertNotEqual(code, 0)
        self.assertIn("isn't waiting", out)

    # ---- a runner: the same job, done in the background
    def test_with_a_runner_the_job_runs_through(self):
        jid = self.py(self.SEED + "importer.work(j); print(j['id'])", SPLICED_RUNNER="claude")
        j = self.job(jid)
        self.assertEqual((j["status"], j["film"], j.get("scenes"), j.get("cost")), ("done", "demo-one", 2, 0.42), j.get("error"))
        self.assertEqual(j["summary"], "Two scenes, one move.")
        self.assertTrue(any("Looking at overview.jpg" in l or "Read:" in l for l in j["log"]), j["log"])
        with open(self.log) as f:
            argv = json.load(f)
        self.assertEqual(argv[0], "-p")
        self.assertNotIn("bypassPermissions", argv, "bypass is never the default")

    def test_a_runner_that_fails_fails_the_job_with_its_last_words(self):
        with open(os.path.join(self.bin, "claude"), "w") as f:
            f.write("#!/bin/sh\necho '{\"type\":\"assistant\",\"message\":{\"content\":[{\"type\":\"text\",\"text\":\"I could not read the sheets.\"}]}}'\nexit 3\n")
        jid = self.py(self.SEED + "importer.work(j); print(j['id'])", SPLICED_RUNNER="claude")
        j = self.job(jid)
        self.assertEqual((j["status"], j["steps"]["breakdown"]["status"]), ("failed", "failed"))
        self.assertIn("exit 3", j["error"])
        self.assertIn("I could not read the sheets.", j["error"])


if __name__ == "__main__":
    unittest.main()
