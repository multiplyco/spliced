"""Spliced's MCP server (spliced/mcp_server.py), spoken to the way an agent's client does: JSON-RPC lines over stdio."""
import base64, json, os, shutil, subprocess, sys, time, unittest

import support


@unittest.skipUnless(shutil.which("uv"), "needs uv")
class Mcp(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        # a stand-in for Remotion: `npx remotion render <entry> <composition> <out> ...` takes a moment and writes a video
        self.bin = os.path.join(os.path.dirname(self.root), "bin")
        os.makedirs(self.bin)
        self.npx = os.path.join(self.bin, "npx")
        with open(self.npx, "w") as f:
            f.write("#!/bin/sh\necho 'Rendering frames'\nsleep 1.5\ncp out/demo-v1.mp4 \"$5\"\necho 'Rendered'\n")
        os.chmod(self.npx, 0o755)
        os.makedirs(os.path.join(self.root, "remotion", "node_modules", "remotion"))   # as after npm install
        support.fake_npm(self.bin)
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        self.p = subprocess.Popen([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "mcp"], env={**env, "SPLICED_OFFLINE": "1"},
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.close)
        self.n = 0
        self.hello = self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def close(self):
        for f in (self.p.stdin, self.p.stdout, self.p.stderr):
            try:
                f.close()
            except OSError:
                pass
        self.p.wait(timeout=10)

    def send(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def call(self, method, params=None):
        self.n += 1
        self.send({"jsonrpc": "2.0", "id": self.n, "method": method, **({"params": params} if params is not None else {})})
        reply = json.loads(self.p.stdout.readline())
        self.assertEqual((reply["jsonrpc"], reply["id"]), ("2.0", self.n))
        return reply

    def tool(self, name, **args):
        r = self.call("tools/call", {"name": name, "arguments": args})["result"]
        return r["isError"], r["content"][0]["text"], r["content"]

    def state(self):
        with open(os.path.join(self.root, "library", "state.json")) as f:
            return json.load(f)

    # ---- the protocol
    def test_hello(self):
        r = self.hello["result"]
        self.assertEqual((r["protocolVersion"], r["serverInfo"]["name"], r["capabilities"]), ("2025-06-18", "spliced", {"tools": {}}))
        self.assertIn('the project "Fixture"', r["instructions"])
        self.assertEqual(self.call("ping")["result"], {})
        self.assertEqual(self.call("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"], "2025-11-25", "an unknown version gets our newest")

    def test_tools_are_described_well_enough_to_call(self):
        tools = self.call("tools/list")["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["project_info", "library_search", "library_scene", "board_read", "board_edit", "show_in_app", "film_status", "film_notes",
                                                     "film_note", "film_mark", "film_new", "folders", "film_sheet", "film_render", "film_voice", "reference_add", "film_kit", "import_folder", "imports", "uploads", "library_build"])
        for t in tools:
            self.assertGreater(len(t["description"]), 40, t["name"])
            self.assertEqual(t["inputSchema"]["type"], "object", t["name"])
            for req in t["inputSchema"]["required"]:
                self.assertIn(req, t["inputSchema"]["properties"], t["name"])
        edit = next(t for t in tools if t["name"] == "board_edit")
        self.assertIn("item.add", edit["description"], "the operations are spelled out for the agent")

    def test_what_is_not_a_request_gets_a_protocol_error_and_the_server_lives(self):
        self.assertEqual(self.call("frobnicate")["error"]["code"], -32601)
        self.assertEqual(self.call("tools/call", {"name": "nope", "arguments": {}})["error"]["code"], -32602)
        self.p.stdin.write("this is not json\n")
        self.p.stdin.flush()
        self.assertEqual(json.loads(self.p.stdout.readline())["error"]["code"], -32700)
        self.assertEqual(self.call("ping")["result"], {})

    # ---- the library and boards
    def test_search_and_read_a_scene_with_its_frames(self):
        err, text, _ = self.tool("library_search", query="whip")
        self.assertFalse(err, text)
        self.assertIn("demo-two/s02", text)
        err, text, _ = self.tool("library_search", tags={"role": "end-card"}, limit=5)
        self.assertIn("demo-two/s03", text)
        self.assertNotIn("demo-one/s01", text)
        err, text, content = self.tool("library_scene", scene="demo-two/s02")
        self.assertFalse(err, text)
        self.assertIn("A whip into the interface", text)
        self.assertEqual([c["type"] for c in content], ["text", "image"])
        self.assertEqual((content[1]["mimeType"], base64.b64decode(content[1]["data"])[:2]), ("image/jpeg", b"\xff\xd8"))

    def test_read_and_edit_a_board(self):
        err, text, _ = self.tool("board_read")
        self.assertIn("Fixture board", text)
        err, text, _ = self.tool("board_read", board="Fixture board")
        self.assertIn("| 1 |", text)
        self.assertIn("It exists.", text)
        err, text, _ = self.tool("board_edit", ops=[{"op": "board.create", "name": "From an agent"},
                                                    {"op": "item.add", "board": "From an agent", "id": "demo-one/s02", "beat": "demo", "copy": "Look.", "seconds": 2}])
        self.assertFalse(err, text)
        b = self.state()["boards"]["From an agent"]
        self.assertEqual([(i["id"], i["copy"], i["seconds"]) for i in b["items"]], [("demo-one/s02", "Look.", 2.0)])
        self.assertEqual(self.state()["log"][-1]["by"], "agent")

    def test_a_refused_edit_changes_nothing_and_says_why(self):
        before = self.state()
        err, text, _ = self.tool("board_edit", ops=[{"op": "board.create", "name": "Half"}, {"op": "item.add", "board": "Half", "id": "nope/s99"}])
        self.assertTrue(err)
        self.assertIn("unknown scene", text)
        self.assertEqual(self.state(), before)
        err, text, _ = self.tool("board_edit", ops="delete everything")
        self.assertTrue(err)
        self.assertIn("list of operations", text)

    def test_bad_arguments_are_said_back_plainly(self):
        for name, args, says in (("library_scene", {"scene": "../../etc/passwd"}, "scene id"), ("library_scene", {}, "`scene` is needed"),
                                 ("film_status", {"film": "--help"}, "`film` should be"), ("film_note", {"film": "demo", "action": "done", "text": "x"}, "`ids` is needed"),
                                 ("film_mark", {"film": "demo", "beat": "hook", "status": "perfect"}, "todo, wip, review"), ("imports", {"action": "explode"}, "list, next, done or cancel"),
                                 ("reference_add", {"links": []}, "`links` is needed"), ("import_folder", {}, "`folder` is needed"), ("import_folder", {"folder": "/no/such/folder"}, "there is no folder"), ("uploads", {"action": "set", "id": "f1x7u0", "analysis": "nice"}, "`analysis` is an object")):
            err, text, _ = self.tool(name, **args)
            self.assertTrue(err, name)
            self.assertIn(says, text, name)

    # ---- films
    def test_a_films_plan_and_notes(self):
        err, text, _ = self.tool("film_status")
        self.assertIn("demo", text)
        err, text, _ = self.tool("film_status", film="demo")
        self.assertFalse(err, text)
        self.assertIn("[review  ] demo", text)
        err, text, _ = self.tool("film_note", film="demo", action="add", at="0:03.00", text="The whip is too slow")
        self.assertFalse(err, text)
        err, notes, _ = self.tool("film_notes", film="demo")
        self.assertIn("The whip is too slow", notes)
        nid = notes[notes.index("[") + 1:notes.index("]")]
        err, text, _ = self.tool("film_note", film="demo", action="reply", id=nid, text="Shortened to 8 frames, render pending")
        self.assertFalse(err, text)
        err, text, _ = self.tool("film_note", film="demo", action="done", ids=[nid], text="Whip is 8 frames now")
        self.assertFalse(err, text)
        err, notes, _ = self.tool("film_notes", film="demo")
        self.assertNotIn("The whip is too slow", notes, "closed notes leave the open list")
        err, notes, _ = self.tool("film_notes", film="demo", include_closed=True)
        self.assertIn("Whip is 8 frames now", notes)
        err, text, _ = self.tool("film_mark", film="demo", beat="end-card", status="wip")
        self.assertFalse(err, text)
        with open(os.path.join(self.root, "remotion", "src", "films", "demo", "storyboard.json")) as f:
            self.assertEqual([b["status"] for b in json.load(f)["beats"]], ["approved", "changes", "wip"], "the note moved its beat to changes; we marked the last one")
        err, text, _ = self.tool("film_status", film="no-such-film")
        self.assertTrue(err)

    def test_a_film_from_a_board(self):
        err, text, _ = self.tool("film_new", film="second", board="Fixture board")
        self.assertFalse(err, text)
        with open(os.path.join(self.root, "remotion", "src", "films", "second", "storyboard.json")) as f:
            sb = json.load(f)
        self.assertEqual((sb["board"], sb["profile"], len(sb["beats"])), ("Fixture board", "soft", 3))

    def test_a_render_is_started_and_then_asked_about(self):
        err, text, _ = self.tool("film_render", film="demo", action="status")
        self.assertIn("no background render has been started", text)
        err, text, _ = self.tool("film_render", film="demo", beat="demo", note="whip shortened")
        self.assertFalse(err, text)
        self.assertIn("rendering in the background", text)
        err, text, _ = self.tool("film_render", film="demo")
        self.assertTrue(err, "one render of a film at a time")
        self.assertIn("already running", text)
        err, text, _ = self.tool("film_render", film="demo", action="status")
        self.assertIn("still rendering", text)
        for _ in range(80):
            err, text, _ = self.tool("film_render", film="demo", action="status")
            if "still rendering" not in text:
                break
            time.sleep(0.25)
        self.assertFalse(err, text)
        self.assertIn("finished", text)
        self.assertIn("remotion/out/demo-v2-demo.mp4", text, "the end of the render's own output comes back")
        out = os.path.join(self.root, "remotion", "out")
        with open(os.path.join(out, "demo-v2-demo.json")) as f:
            side = json.load(f)
        self.assertEqual((side["version"], side["beat"], side["note"]), (2, "demo", "whip shortened"))
        err, text, _ = self.tool("film_status", film="demo")
        self.assertIn("demo-v2-demo.mp4", text, "the film's plan shows the new render")

    def test_a_render_that_fails_says_so_with_its_last_words(self):
        with open(self.npx, "w") as f:
            f.write("#!/bin/sh\necho 'Error: Could not find composition with ID Demo'\nexit 1\n")
        err, text, _ = self.tool("film_render", film="demo")
        self.assertFalse(err, text)
        for _ in range(80):
            err, text, _ = self.tool("film_render", film="demo", action="status")
            if "still rendering" not in text:
                break
            time.sleep(0.25)
        self.assertTrue(err)
        self.assertIn("failed", text)
        self.assertIn("Could not find composition", text)
        err, text, _ = self.tool("film_render", film="no-such-film")
        self.assertTrue(err)
        self.assertIn("no Remotion film called no-such-film", text)

    def test_a_render_installs_remotion_first_when_it_is_missing(self):
        shutil.rmtree(os.path.join(self.root, "remotion", "node_modules"))
        with open(os.path.join(self.root, "remotion", "package.json"), "w") as f:
            f.write("{}")
        self.tool("film_render", film="demo")
        for _ in range(80):
            err, text, _ = self.tool("film_render", film="demo", action="status")
            if "still rendering" not in text:
                break
            time.sleep(0.25)
        self.assertIn("finished", text)
        self.assertIn("Installing remotion/'s packages", text)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "remotion", "node_modules", "remotion")))

    def test_a_render_whose_install_fails_says_so_and_renders_nothing(self):
        shutil.rmtree(os.path.join(self.root, "remotion", "node_modules"))
        with open(os.path.join(self.bin, "npm"), "w") as f:
            f.write("#!/bin/sh\necho 'npm ERR! network unreachable'\nexit 1\n")
        with open(os.path.join(self.root, "remotion", "package.json"), "w") as f:
            f.write("{}")
        self.tool("film_render", film="demo")
        for _ in range(80):
            err, text, _ = self.tool("film_render", film="demo", action="status")
            if "still rendering" not in text:
                break
            time.sleep(0.25)
        self.assertIn("failed", text)
        self.assertIn("network unreachable", text)
        self.assertIn("nothing was rendered", text)

    # ---- voice-over through the agent's own connector
    def test_voice_lines_for_the_agent_and_reads_filed_back(self):
        err, text, _ = self.tool("film_voice", film="demo", action="lines")
        self.assertTrue(err)
        self.assertIn("no voice lines yet", text)

    # ---- the library's upkeep
    def test_imports_uploads_and_the_build(self):
        err, text, _ = self.tool("imports", action="next")
        self.assertIn("Nothing is waiting", text)
        err, text, _ = self.tool("uploads", action="list")
        self.assertIn("f1x7u0", text)
        err, text, _ = self.tool("uploads", action="set", id="f1x7u0", analysis={"title": "A gradient, again", "world": "moon-base"})
        self.assertTrue(err, "a tag outside the taxonomy is refused: " + text)
        err, text, _ = self.tool("library_build", check_only=True)
        self.assertFalse(err, text)
        err, text, _ = self.tool("project_info")
        self.assertFalse(err, text)
        for part in ("on this machine, for Fixture", "Fixture board", "Films in production", "demo"):
            self.assertIn(part, text)

    def test_nothing_but_protocol_reaches_stdout(self):
        self.tool("library_build", check_only=True)   # the build prints as it goes
        self.tool("film_status", film="demo")
        self.assertEqual(self.call("ping")["result"], {}, "the next line on stdout is still a reply")


if __name__ == "__main__":
    unittest.main()
