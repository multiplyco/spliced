"""The one entry point (spliced/spliced.py): it lists what there is, and each command is the tool it names."""
import json, os, shutil, subprocess, sys, unittest

import support


@unittest.skipUnless(shutil.which("uv"), "needs uv")
class Cli(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)

    def run_cli(self, *args, tool="cli.py", cwd=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, tool), *args], env={**env, "SPLICED_OFFLINE": "1"}, capture_output=True, text=True, cwd=cwd or support.REPO)
        return r.returncode, r.stdout + r.stderr

    def test_with_no_command_it_says_what_there_is(self):
        for args in ((), ("--help",), ("help",)):
            code, out = self.run_cli(*args)
            self.assertEqual(code, 0, out)
            for name in ("open", "doctor", "update", "board", "film", "reference", "imports", "library", "uploads", "stock", "sound", "voice", "motion", "mcp", "setup", "init", "agents"):
                self.assertRegex(out, rf"(?m)^  {name}\s+\S", name)
        code, out = self.run_cli("--project", self.root)
        self.assertIn(f"Project: {self.root}  (Fixture)", out)

    def test_every_command_names_a_tool_that_exists(self):
        sys.path.insert(0, support.TOOLS)
        import cli as spliced
        for name, (script, what) in spliced.COMMANDS.items():
            self.assertTrue(os.path.isfile(os.path.join(support.TOOLS, script)), f"{name} -> {script}")
            self.assertTrue(what.strip())
        for alias, name in spliced.ALIASES.items():
            self.assertIn(name, spliced.COMMANDS, alias)

    def test_a_command_is_the_tool_it_names(self):
        for args, tool, targs in ((("board", "boards"), "board.py", ("boards",)), (("board", "show", "Fixture board"), "board.py", ("show", "Fixture board")),
                                  (("boards", "find", "whip"), "board.py", ("find", "whip")), (("film", "list"), "film.py", ("list",)),
                                  (("library", "--check"), "build_library.py", ("--check",)), (("uploads", "list"), "uploads.py", ("list",))):
            code, out = self.run_cli("--project", self.root, *args)
            if tool == "board.py":
                code2, out2 = self.run_cli("--project", self.root, *targs, tool=tool)
            else:
                r = subprocess.run(["uv", "run", "-q", os.path.join(support.TOOLS, tool), *targs], capture_output=True, text=True,
                                   env={**{k: v for k, v in os.environ.items() if not k.startswith("SPLICED_")}, "SPLICED_PROJECT": self.root})
                code2, out2 = r.returncode, r.stdout + r.stderr
            self.assertEqual((code, out), (code2, out2), " ".join(args))
            self.assertEqual(code, 0, out)
        self.assertIn("Fixture board", self.run_cli("--project", self.root, "board", "boards")[1])

    def test_the_project_is_found_from_where_you_are(self):
        code, out = self.run_cli("board", "boards", cwd=os.path.join(self.root, "library"))
        self.assertIn("Fixture board", out)

    def test_outside_a_project_the_list_still_shows_and_a_command_says_what_to_do(self):
        nowhere = os.path.dirname(self.root)
        code, out = self.run_cli(cwd=nowhere)
        self.assertEqual(code, 0, out)
        self.assertIn("Project: none here", out)
        code, out = self.run_cli("board", "boards", cwd=nowhere)
        self.assertNotEqual(code, 0)
        self.assertIn("spliced init", out)

    def test_init_makes_a_project_that_works_empty(self):
        new = os.path.join(os.path.dirname(self.root), "my films")
        code, out = self.run_cli("init", new, cwd=os.path.dirname(self.root))
        self.assertEqual(code, 0, out)
        with open(os.path.join(new, "spliced.json")) as f:
            self.assertEqual(json.load(f), {"format": 1, "name": "my films", "brand": {"name": ""}})
        for rel in ("library/TAXONOMY.md", "library/STYLES.md", "library/README.md", "library/references.tsv", ".gitignore", "library/references", "reference"):
            self.assertTrue(os.path.exists(os.path.join(new, rel)), rel)
        code, out = self.run_cli("init", new)
        self.assertNotEqual(code, 0, "never over an existing project")
        self.assertIn("already a project", out)
        for args in (("board", "boards"), ("film", "list"), ("library", "--check"), ("library",), ("uploads", "list"), ("imports", "list"), ("reference", "status")):
            code, out = self.run_cli(*args, cwd=new)
            self.assertEqual(code, 0, f"{' '.join(args)} on an empty project: {out}")
        with open(os.path.join(new, ".cache", "library.json")) as f:
            self.assertEqual(json.load(f)["films"], [])
        code, out = self.run_cli("board", "new", "First", cwd=new)
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("board", "show", "First", cwd=new)
        self.assertIn("Profile: soft", out)

    def test_a_board_can_hold_a_whole_reference_film(self):
        code, out = self.run_cli("--project", self.root, "board", "new", "Study: Demo two", "--from-film", "demo-two")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, "library", "state.json")) as f:
            b = json.load(f)["boards"]["Study: Demo two"]
        self.assertEqual([(i["id"], i["beat"], i["seconds"]) for i in b["items"]],
                         [("demo-two/s01", "hook", 1.0), ("demo-two/s02", "demo", 1.0), ("demo-two/s03", "end-card", 1.0)], "every scene, in order, its role and length")
        self.assertEqual((b["brief"]["length"], b["brief"]["aspect"]), (3.0, "16:9"))
        code, out = self.run_cli("--project", self.root, "board", "new", "Nothing", "--from-film", "no-such-film")
        self.assertNotEqual(code, 0)
        self.assertIn("no film called no-such-film", out)

    def test_agents_install_puts_the_skills_where_an_agent_looks(self):
        code, out = self.run_cli("--project", self.root, "agents", "install")
        self.assertEqual(code, 0, out)
        for f in ("SKILL.md", "BREAKDOWN-AGENT.md", "HOW-TO-BREAK-DOWN.md"):
            self.assertTrue(os.path.isfile(os.path.join(self.root, ".claude", "skills", "add-reference", f)), f)
        with open(os.path.join(self.root, ".mcp.json")) as f:
            self.assertIn("mcp", json.load(f)["mcpServers"]["spliced"]["args"])
        with open(os.path.join(self.root, "AGENTS.md")) as f:
            first = f.read()
        self.assertIn("<!-- spliced:begin -->", first)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "CLAUDE.md")), "Claude Code is pointed at the same instructions")
        with open(os.path.join(self.root, "GEMINI.md")) as f:
            self.assertEqual(f.read(), "@./AGENTS.md\n", "and so is Gemini CLI")
        with open(os.path.join(self.root, ".gemini", "settings.json")) as f:
            self.assertIn("mcp", json.load(f)["mcpServers"]["spliced"]["args"])
        with open(os.path.join(self.root, ".geminiignore")) as f:
            self.assertIn(".env", f.read().splitlines())
        # the project's own words around the section survive, and a second run changes nothing
        with open(os.path.join(self.root, "AGENTS.md"), "w") as f:
            f.write("# Ours\n\nHouse rules.\n\n" + first + "\nMore of ours.\n")
        with open(os.path.join(self.root, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"other": {"command": "x"}}}, f)
        with open(os.path.join(self.root, ".gemini", "settings.json"), "w") as f:
            json.dump({"theme": "Dracula", "mcpServers": {"other": {"command": "x"}}}, f)
        code, out = self.run_cli("--project", self.root, "agents", "install")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, "AGENTS.md")) as f:
            again = f.read()
        self.assertTrue(again.startswith("# Ours\n\nHouse rules.") and again.rstrip().endswith("More of ours.") and again.count("spliced:begin") == 1, again[:200])
        with open(os.path.join(self.root, ".mcp.json")) as f:
            self.assertEqual(sorted(json.load(f)["mcpServers"]), ["other", "spliced"], "another server in .mcp.json is kept")
        with open(os.path.join(self.root, ".gemini", "settings.json")) as f:
            g = json.load(f)
        self.assertEqual((g["theme"], sorted(g["mcpServers"])), ("Dracula", ["other", "spliced"]), "Gemini CLI's own settings are kept")
        with open(os.path.join(self.root, ".geminiignore")) as f:
            self.assertEqual(f.read().splitlines().count(".env"), 1, "a second run adds nothing")

    def test_setup_goes_from_an_empty_folder_to_a_project_with_everything_in(self):
        tmp = os.path.dirname(self.root)
        bin_dir, new = os.path.join(tmp, "bin"), os.path.join(tmp, "my films")
        os.makedirs(bin_dir)
        support.fake_npm(bin_dir)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        env.update(PATH=bin_dir + os.pathsep + env["PATH"], SPLICED_OFFLINE="1")
        setup = lambda *a, cwd=tmp: subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "setup", *a], env=env, capture_output=True, text=True, cwd=cwd)
        r = setup(new, "--no-render", "--no-open")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for made in ("spliced.json", "library/TAXONOMY.md", ".claude/skills/make-film/SKILL.md", ".mcp.json", "AGENTS.md",
                     "remotion/node_modules/remotion", "remotion/docs/SOUND.md", "remotion/src/films/splice-explainer/storyboard.json"):
            self.assertTrue(os.path.exists(os.path.join(new, made)), f"{made}\n{r.stdout}")
        self.assertIn("Next, say this to your AI", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(new, ".cache", "server.json")), "--no-open: nothing left running")
        again = setup("--no-render", "--no-open", cwd=new)   # run again inside it: nothing is made twice
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("(already a project)", again.stdout)
        self.assertIn("This project has films already", again.stdout)
        # a folder that holds someone's files is never turned into a project by accident
        other = os.path.join(tmp, "documents")
        os.makedirs(other)
        with open(os.path.join(other, "notes.txt"), "w") as f:
            f.write("mine")
        r = setup(cwd=other)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Name a folder for the new project", r.stderr)
        self.assertEqual(os.listdir(other), ["notes.txt"])

    def test_run_through_npx_agents_are_told_the_npx_command(self):
        # under npx, npm puts a temporary `spliced` on the PATH; the launcher sets SPLICED_VIA and that is what is written
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "agents", "install"],
                           env={**env, "SPLICED_OFFLINE": "1", "SPLICED_VIA": "npx -y spliced-app"}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.root, ".mcp.json")) as f:
            self.assertEqual(json.load(f)["mcpServers"]["spliced"], {"command": "npx", "args": ["-y", "spliced-app", "mcp"]})
        with open(os.path.join(self.root, "AGENTS.md")) as f:
            self.assertIn("`npx -y spliced-app doctor`", f.read())

    def test_the_npm_package_has_the_same_version(self):
        with open(os.path.join(support.REPO, "package.json")) as f:
            pkg = json.load(f)
        with open(os.path.join(support.TOOLS, "__init__.py")) as f:
            self.assertIn(f'"{pkg["version"]}"', f.read())
        self.assertEqual(pkg["bin"], {"spliced": "bin/spliced.js"})

    def test_an_unknown_command_is_an_error_that_lists_the_real_ones(self):
        code, out = self.run_cli("frobnicate")
        self.assertEqual(code, 1)
        self.assertIn("no command called 'frobnicate'", out)
        self.assertIn("Commands:", out)

    def test_board_with_no_command_lists_its_commands(self):
        code, out = self.run_cli(tool="board.py", cwd=self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("spliced board find", out)
        self.assertIn("show-in-app", out)


if __name__ == "__main__":
    unittest.main()
