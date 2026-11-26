"""What a Claude Code session in a project loads (`spliced agents context`), and lean film sessions
(`spliced agents install --lean`), on a throwaway HOME so the person's own ~/.claude.json is never read or touched."""
import json, os, subprocess, sys, tempfile, shutil, unittest

import support

SECRET = "SECRET_TOKEN_DO_NOT_PRINT"


class Sessions(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.home = tempfile.mkdtemp(prefix="spliced-home-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        os.makedirs(os.path.join(self.home, ".claude", "skills", "acme-notes"))
        with open(os.path.join(self.home, ".claude", "skills", "acme-notes", "SKILL.md"), "w") as f:
            f.write("---\nname: acme-notes\n---\n")
        self.claude_json = os.path.join(self.home, ".claude.json")
        with open(self.claude_json, "w") as f:
            json.dump({"mcpServers": {"globex-crm": {"type": "http", "url": "https://crm.example", "headers": {"Authorization": SECRET}},
                                      "acme-images": {"command": "acme-images", "env": {"ACME_KEY": SECRET}}},
                       "claudeAiMcpEverConnected": ["claude.ai One", "claude.ai Two", "claude.ai Three"],
                       "projects": {self.root: {"mcpServers": {"initech-mail": {"command": "mail", "env": {"TOKEN": SECRET}}},
                                                "lastTotalInputTokens": 900, "lastTotalCacheReadInputTokens": 2500000, "lastTotalCacheCreationInputTokens": 120000}}}, f)
        with open(self.claude_json, "rb") as f:
            self.claude_json_bytes = f.read()
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.cli("agents", "install")
        with open(os.path.join(self.root, ".mcp.json")) as f:
            mcp = json.load(f)
        mcp["mcpServers"]["acme-stock"] = {"command": "stock"}
        with open(os.path.join(self.root, ".mcp.json"), "w") as f:
            json.dump(mcp, f)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args],
                           env={**env, "HOME": self.home, "SPLICED_OFFLINE": "1"}, capture_output=True, text=True, cwd=support.REPO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def local(self):
        p = os.path.join(self.root, ".claude", "settings.local.json")
        if not os.path.exists(p):
            return None
        with open(p) as f:
            return json.load(f)

    def tearDown(self):
        with open(self.claude_json, "rb") as f:
            self.assertEqual(f.read(), self.claude_json_bytes, "the person's ~/.claude.json is never written")

    def test_context_names_and_counts_what_a_session_loads_and_never_a_value(self):
        out = self.cli("agents", "context")
        self.assertNotIn(SECRET, out)
        self.assertIn("this project's .mcp.json: acme-stock, spliced", out)
        self.assertIn("for this folder only (~/.claude.json): initech-mail", out)
        self.assertIn("in every folder (~/.claude.json): acme-images, globex-crm", out)
        self.assertIn("claude.ai connectors: on, about 3 connected", out)
        self.assertIn("Skills: 2 in this project, 1 of yours", out)
        self.assertIn("AGENTS.md ~", out)
        self.assertIn("2,500,000 read from cache", out)
        self.assertIn("agents install --lean", out)
        self.assertIn("film context <slug>", out)
        self.assertIsNone(self.local(), "context changes nothing")

    def test_lean_leaves_spliced_and_what_is_kept_and_undoes_cleanly(self):
        with open(os.path.join(self.root, ".claude", "settings.local.json"), "w") as f:   # the person's own settings, kept throughout
            json.dump({"permissions": {"allow": ["Bash(ls:*)"]}, "deniedMcpServers": [{"serverName": "old-thing"}]}, f)
        out = self.cli("agents", "install", "--lean", "--keep", "acme-images")
        self.assertNotIn(SECRET, out)
        self.assertIn("sessions here load acme-images, spliced; 3 other servers off, claude.ai connectors off", out)
        st = self.local()
        self.assertEqual(st["permissions"], {"allow": ["Bash(ls:*)"]})
        self.assertEqual([e["serverName"] for e in st["deniedMcpServers"]], ["old-thing", "globex-crm", "initech-mail"])
        self.assertEqual(st["disabledMcpjsonServers"], ["acme-stock"])
        self.assertIs(st["disableClaudeAiConnectors"], True)
        with open(os.path.join(self.root, ".claude", "settings.json")) as f:
            self.assertIn("Read(./.env)", json.load(f)["permissions"]["deny"], "the .env fence stays in the shared settings")
        ignored = subprocess.run(["git", "-C", self.root, "check-ignore", "-q", ".claude/settings.local.json"])
        self.assertEqual(ignored.returncode, 0, "the person's own server names stay out of git")
        self.cli("agents", "install", "--lean", "--keep", "acme-images")
        self.assertEqual(self.local(), st, "safe to run twice")
        self.assertIn("off here: globex-crm", self.cli("agents", "context"))
        self.cli("agents", "install", "--lean", "--keep-connectors")   # a new choice replaces the old one
        st2 = self.local()
        self.assertEqual([e["serverName"] for e in st2["deniedMcpServers"]], ["old-thing", "acme-images", "globex-crm", "initech-mail"])
        self.assertNotIn("disableClaudeAiConnectors", st2)
        self.assertIn("off: sessions here load every MCP server", self.cli("agents", "install", "--lean", "off"))
        self.assertEqual(self.local(), {"permissions": {"allow": ["Bash(ls:*)"]}, "deniedMcpServers": [{"serverName": "old-thing"}]},
                         "off takes out what lean added and nothing the person put there")
        self.assertIn("was not on here", self.cli("agents", "install", "--lean", "off"))

    def test_lean_on_a_project_with_no_local_settings_goes_away_entirely_when_undone(self):
        self.cli("agents", "install", "--lean")
        self.assertEqual(sorted(self.local()), ["deniedMcpServers", "disableClaudeAiConnectors", "disabledMcpjsonServers"])
        self.cli("agents", "install", "--lean", "off")
        self.assertIsNone(self.local())


if __name__ == "__main__":
    unittest.main()
