"""spliced connect: this project's MCP entry in an AI app's own settings, written without losing what was there."""
import json, os, subprocess, sys, tempfile, unittest

import support


class Connect(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.home = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.home, True)
        self.claude = os.path.join(self.home, "Library", "Application Support", "Claude", "claude_desktop_config.json") if sys.platform == "darwin" \
            else os.path.join(self.home, "Claude", "claude_desktop_config.json")

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        env.update(HOME=self.home, APPDATA=self.home)
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "connect", *args], env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def config(self):
        with open(self.claude) as f:
            return json.load(f)

    def test_a_worktree_is_sent_to_its_main_checkout(self):
        # A Conductor workspace or `git worktree add` folder goes away; an app pointed at it would break then.
        git = lambda *a, cwd=self.root: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)
        git("init", "-q"); git("add", "-A")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fixture")
        wt = os.path.join(os.path.dirname(self.root), "wt")
        git("worktree", "add", "-q", wt)
        main = self.root
        self.root = wt
        code, out = self.cli("claude-desktop")
        self.assertEqual(code, 1, out)
        self.assertIn(f"cd {os.path.realpath(main)} &&", out)
        self.assertFalse(os.path.exists(self.claude), "nothing written")
        code, out = self.cli()
        self.assertIn("This folder is a git worktree", out)
        self.assertIn("This only lists them", out)
        code, out = self.cli("claude-desktop", "--here")
        self.assertEqual(code, 0, out)
        self.root = main
        code, out = self.cli()
        self.assertNotIn("git worktree", out)

    def test_it_adds_this_project_and_keeps_everything_else(self):
        os.makedirs(os.path.dirname(self.claude))
        with open(self.claude, "w") as f:
            json.dump({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}, f)
        code, out = self.cli("claude-desktop", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("would write", out)
        self.assertEqual(set(self.config()["mcpServers"]), {"other"})   # a dry run changes nothing
        code, out = self.cli("claude-desktop")
        self.assertEqual(code, 0, out)
        cfg = self.config()
        self.assertEqual(cfg["theme"], "dark")
        self.assertEqual(cfg["mcpServers"]["other"], {"command": "x"})
        e = cfg["mcpServers"]["spliced-fixture"]
        self.assertTrue(os.path.isabs(e["command"]), e)                           # an app doesn't have your shell's PATH
        self.assertEqual(e["args"][-3:], ["--project", os.path.realpath(self.root), "mcp"])
        self.assertIn("PATH", e["env"])
        self.assertTrue(os.path.exists(self.claude + ".before-spliced"))          # the original, kept once
        self.assertIn("already has", self.cli("claude-desktop")[1])
        code, out = self.cli("--json")
        apps = {a["id"]: a for a in json.loads(out)["apps"]}
        self.assertTrue(apps["claude-desktop"]["connected"])
        self.assertFalse(apps["cursor"]["connected"])
        code, out = self.cli("claude-desktop", "--remove")
        self.assertEqual(code, 0, out)
        self.assertEqual(set(self.config()["mcpServers"]), {"other"})

    def test_cursor_gets_its_own_file(self):
        code, out = self.cli("cursor")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.home, ".cursor", "mcp.json")) as f:
            self.assertIn("spliced-fixture", json.load(f)["mcpServers"])

    def test_it_never_writes_over_a_file_it_cannot_read(self):
        os.makedirs(os.path.dirname(self.claude))
        with open(self.claude, "w") as f:
            f.write("{not json")
        code, out = self.cli("claude-desktop")
        self.assertNotEqual(code, 0)
        self.assertIn("isn't valid JSON", out)
        with open(self.claude) as f:
            self.assertEqual(f.read(), "{not json")

    def test_an_unknown_app_says_which_there_are(self):
        code, out = self.cli("chatgpt")
        self.assertNotEqual(code, 0)
        self.assertIn("claude-desktop, cursor, codex", out)


if __name__ == "__main__":
    unittest.main()
