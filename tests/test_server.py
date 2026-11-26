"""The server (spliced/toolbox.py) on a throwaway copy of the fixture: what it serves, what it refuses, and to whom."""
import http.client, json, os, socket, subprocess, sys, time, unittest

import support


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = support.project(cls)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        cls.proc = subprocess.Popen([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), "--port", str(cls.port), "--no-open"],
                                    env={**env, "SPLICED_PROJECT": cls.root}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(900):  # the first start builds the library index (uv fetches the build's packages once)
            try:
                if cls.req("GET", "/api/info")[0] == 200:
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("the server didn't start")

    @classmethod
    def addCleanup(cls, fn, *a, **kw):  # so support.project() can be used for the whole class
        cls.addClassCleanup(fn, *a, **kw)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        if os.path.exists(os.path.join(cls.root, ".cache", "server.json")):   # stopped with SIGTERM (as the Mac app does), it tidies up
            raise AssertionError("the server left .cache/server.json behind")

    @classmethod
    def req(cls, method, path, body=None, headers=None, host=None):
        """One request, exactly as written (no path clean-up): (status, headers, body)."""
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        h = {"Host": host or f"localhost:{cls.port}", **(headers or {})}
        data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        out = (r.status, {k.lower(): v for k, v in r.getheaders()}, r.read())
        c.close()
        return out

    def state(self):
        return json.loads(self.req("GET", "/api/state")[2])

    # ---- what is served
    def test_the_front_door(self):
        for path, to in (("/", "/app/"), ("/app", "/app/"), ("/library/toolbox/", "/app/"), ("/library/toolbox/hardware.html?both", "/app/hardware.html?both")):
            code, h, _ = self.req("GET", path)
            self.assertEqual((code, h.get("location")), (302, to), path)
        code, h, body = self.req("GET", "/app/")
        self.assertEqual(code, 200)
        self.assertIn(b"<title>Spliced</title>", body)
        self.assertEqual(h.get("x-content-type-options"), "nosniff")

    def test_app_files_and_the_library_data(self):
        for path, kind in (("/app/app.js", "text/javascript"), ("/app/core.js", "text/javascript"), ("/app/style.css", "text/css"),
                           ("/app/brand/splice-mark-white.svg", "image/svg+xml")):
            code, h, body = self.req("GET", path)
            self.assertEqual((code, h.get("content-type", "").split(";")[0]), (200, kind), path)
        self.assertEqual(self.req("GET", "/app/data.js")[0], 404, "the library data is no longer a file in the app folder")

    def test_the_app_is_told_about_the_project(self):
        code, h, body = self.req("GET", "/api/boot.js")
        self.assertEqual((code, h.get("content-type")), (200, "text/javascript; charset=utf-8"))
        boot = json.loads(body.decode()[len("window.SPLICED = "):].rstrip().rstrip(";"))
        self.assertEqual((boot["project"], boot["brand"], boot["default_profile"]), ("Fixture", "Fixture", "soft"))
        self.assertEqual(boot["ai"], "", "this project names no AI, so the app says 'your AI'")
        self.assertRegex(boot["version"], r"^\d+\.\d+\.\d+", "the app is told which Spliced is running")
        code, h, body = self.req("GET", "/app/changelog.md")
        self.assertEqual((code, h.get("content-type")), (200, "text/markdown; charset=utf-8"))
        self.assertIn(b"## ", body)
        self.assertEqual(sorted(boot["profiles"]), ["apple", "material", "soft", "splice"], "no project of ours leaks into another's")
        self.assertIn(boot["cli"], ("spliced", "uv run " + os.path.join(support.TOOLS, "cli.py")), "the installed command, or this checkout's own")

    def test_the_library_index(self):
        code, h, js = self.req("GET", "/api/library.js")
        self.assertEqual((code, h.get("content-type"), h.get("cache-control")), (200, "text/javascript; charset=utf-8", "no-cache"))
        self.assertTrue(js.startswith(b"window.LIBRARY = {") and js.rstrip().endswith(b";"))
        lib = json.loads(self.req("GET", "/api/library")[2])
        self.assertEqual([f["slug"] for f in lib["films"]], ["demo-one", "demo-two"], "the project's library, built by the server on its first start")
        self.assertEqual(lib["films"][1]["scenes"][1]["transition_in"], "whip")
        self.assertEqual(json.loads(js[len(b"window.LIBRARY = "):].rstrip().rstrip(b";")), lib)
        # a reload costs nothing: the same ETag comes back as 304 with no body
        code, h2, body = self.req("GET", "/api/library.js", headers={"If-None-Match": h["etag"]})
        self.assertEqual((code, body), (304, b""))
        # and it travels compressed
        import gzip
        code, hz, z = self.req("GET", "/api/library.js", headers={"Accept-Encoding": "gzip, br"})
        self.assertEqual((code, hz.get("content-encoding"), gzip.decompress(z)), (200, "gzip", js))
        self.assertNotEqual(hz["etag"], h["etag"])
        self.assertLess(len(z), len(js))
        self.assertEqual(self.req("GET", "/api/library.js", headers={"If-None-Match": hz["etag"], "Accept-Encoding": "gzip"})[0], 304)
        self.assertEqual(self.req("GET", "/api/library", headers={"Origin": "http://evil.test"})[0], 403)

    def test_the_projects_own_films_for_the_library(self):
        code, _, body = self.req("GET", "/api/own-films")
        self.assertEqual(code, 200)
        films = json.loads(body)["films"]
        self.assertEqual([f["slug"] for f in films], ["demo"], "the fixture's film, which has a render of the whole film")
        f = films[0]
        self.assertEqual((f["title"], f["file"], f["render"]), ("Demo film", "remotion/out/demo-v1.mp4", "demo-v1.mp4"))
        self.assertEqual([(x["id"], x["start"], x["end"]) for x in f["scenes"]], [("hook", 0.0, 2.0), ("demo", 2.0, 4.0), ("end-card", 4.0, 6.0)], "each beat timed in the render")
        self.assertEqual(f["scenes"][0]["on_screen"], "A headline.")
        self.assertEqual(self.req("GET", "/project/" + f["file"])[0], 200, "and its render plays")

    def test_a_projects_svg_never_runs_whatever_its_url(self):
        with open(os.path.join(self.root, "library", "mark.svg"), "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        for path in ("/project/library/mark.svg", "/project/library/mark.sv%67", "/project/library/mark.svg/"):
            code, h, _ = self.req("GET", path)
            if code == 200:
                self.assertIn("sandbox", h.get("content-security-policy", ""), path)

    def test_project_media(self):
        code, h, body = self.req("GET", "/project/reference/Demo%20two%20%5Babc123%5D.mp4", headers={"Range": "bytes=0-99"})
        self.assertEqual((code, len(body), h.get("content-type")), (206, 100, "video/mp4"))
        self.assertTrue(h.get("content-range", "").startswith("bytes 0-99/"))
        self.assertEqual(self.req("GET", "/project/library/references/demo-one/scenes/s01.jpg")[0], 200)
        self.assertEqual(self.req("HEAD", "/project/library/uploads/fixture-look-f1x7u0.png")[0], 200)
        code, h, body = self.req("GET", "/api/frame?file=reference%2Fdemo-one.mp4&t=1&w=160")
        self.assertEqual((code, h.get("content-type"), body[:2]), (200, "image/jpeg", b"\xff\xd8"))

    def test_nothing_else_on_disk_is_reachable(self):
        for path in ("/.env", "/%2eenv", "/project/.env", "/project/%2eenv", "/app/../.env", "/app/%2e%2e/.env", "/project/library/../.env", "/project/../project/.env",
                     "/project/spliced.json", "/project/library/state.json", "/app/state.json", "/project/library/TAXONOMY.md", "/project/library/references/demo-one/breakdown.json",
                     "/project/", "/project/reference/", "/app/brand/", "/reference/demo-one.mp4", "/spliced/toolbox.py", "/toolbox.py", "/library/references/demo-one/scenes/s01.jpg",
                     "/app/.nothing", "/app//app.js", "/api/frame?file=.env&t=0", "/api/frame?file=..%2F..%2Fetc%2Fhosts&t=0"):
            for method in ("GET", "HEAD"):
                code, _, body = self.req(method, path)
                self.assertEqual(code, 404, f"{method} {path}")
                self.assertNotIn(support.SENTINEL.encode(), body, path)

    # ---- where it runs (the Mac app gives each project its own port; the command line has to find it)
    def test_it_says_where_it_runs(self):
        with open(os.path.join(self.root, ".cache", "server.json")) as f:
            info = json.load(f)
        self.assertEqual((info["port"], info["pid"]), (self.port, self.proc.pid))
        self.assertEqual(os.path.realpath(info["root"]), os.path.realpath(self.root))
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        url = subprocess.run([sys.executable, "-c", "import board; print(board.URL)"], cwd=support.TOOLS, capture_output=True, text=True,
                             env={**env, "SPLICED_PROJECT": self.root}).stdout.strip()
        self.assertEqual(url, f"http://127.0.0.1:{self.port}")

    def test_a_second_start_uses_the_running_one(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            other = s.getsockname()[1]
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), "--port", str(other), "--no-open"],
                           env={**env, "SPLICED_PROJECT": self.root}, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"already running for this project at http://localhost:{self.port}/app/", r.stdout)

    def test_the_app_offers_the_other_projects_and_starts_the_one_chosen(self):
        me = json.loads(self.req("GET", "/api/projects")[2])
        self.assertEqual([(p["name"], p["here"]) for p in me["projects"] if p["here"]], [("Fixture", True)], "a running project is in its own list")
        self.assertEqual(self.req("POST", "/api/projects/open", {"root": "/etc"})[0], 404, "only a project that was opened before, never any folder")
        other = support.project(self)
        self.assertEqual(self.req("POST", "/api/projects/open", {"root": other})[0], 404, "a project nobody has opened isn't offered either")
        sys.path.insert(0, support.TOOLS)
        import projects
        projects.note(other)   # as its own `spliced open` would have
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        self.addCleanup(subprocess.run, [sys.executable, os.path.join(support.TOOLS, "toolbox.py"), "--stop"], env={**env, "SPLICED_PROJECT": other}, capture_output=True)
        status, _, body = self.req("POST", "/api/projects/open", {"root": other})
        self.assertEqual(status, 200, body)
        url = json.loads(body)["url"]
        self.assertNotIn(f":{self.port}/", url, "its own address")
        with open(os.path.join(other, ".cache", "server.json")) as f:
            self.assertEqual(json.load(f)["url"], url)
        listed = {p["root"]: p for p in json.loads(self.req("GET", "/api/projects")[2])["projects"]}
        self.assertEqual((listed[other]["url"], listed[other]["here"]), (url, False))
        self.assertEqual(json.loads(self.req("POST", "/api/projects/open", {"root": other})[2])["url"], url, "already running: the same one")

    def test_what_a_browser_cant_do_the_server_does(self):
        # a folder picker, a new project from the page, and Connect your AI: the Mac app's extras, offered to a browser
        root, tmp = support.project(self), os.path.dirname(support.project(self))
        chosen = os.path.join(tmp, "picked films")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        env.update(SPLICED_PROJECT=root, SPLICED_NO_UPDATE_CHECK="1", SPLICED_PICKER=f"echo '{chosen}/'")   # the picker: a stand-in that answers a path
        run = lambda *a, **e: subprocess.run([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), *a], env={**env, **e}, capture_output=True, text=True, timeout=120)
        self.addCleanup(run, "--stop")
        self.assertEqual(run("--background", "--no-open").returncode, 0)
        with open(os.path.join(root, ".cache", "server.json")) as f:
            port = json.load(f)["port"]

        def ask(method, path, body=None):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=150)
            c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers={"Host": f"localhost:{port}"})
            r = c.getresponse()
            out = (r.status, json.loads(r.read() or b"{}"))
            c.close()
            return out

        self.assertEqual(ask("POST", "/api/pick-folder", {"for": "project"}), (200, {"path": chosen}))
        # Connect your AI: the skills and the tools for agents that open the folder
        status, st = ask("GET", "/api/connect")
        self.assertEqual((status, st["agents"], st["project"]), (200, False, "Fixture"))
        status, st = ask("POST", "/api/connect", {"agents": True})
        self.assertEqual((status, st["ok"], st["agents"], [d["step"] for d in st["done"]]), (200, True, True, ["agents install"]))
        self.assertTrue(os.path.isfile(os.path.join(root, ".claude", "skills", "make-film", "SKILL.md")))
        self.assertEqual(ask("POST", "/api/connect", {"apps": {"no-such-app": True}})[1]["done"], [], "only an app this machine has, and only a change")
        # a new project: never in a folder that holds someone's files
        mine = os.path.join(tmp, "documents")
        os.makedirs(mine)
        with open(os.path.join(mine, "notes.txt"), "w") as f:
            f.write("mine")
        status, j = ask("POST", "/api/projects/new", {"folder": mine})
        self.assertEqual(status, 400, j)
        self.assertIn("has files in it", j["error"])
        self.assertEqual(os.listdir(mine), ["notes.txt"])
        self.assertEqual(ask("POST", "/api/projects/new", {"folder": "films"})[0], 400, "a whole path, not a name")
        status, j = ask("POST", "/api/projects/new", {"folder": chosen})
        self.assertEqual(status, 200, j)
        self.addCleanup(run, "--stop", SPLICED_PROJECT=chosen)
        self.assertEqual((j["name"], j["root"]), ("picked films", os.path.realpath(chosen)))
        for made in ("spliced.json", ".claude/skills/add-reference/SKILL.md", ".mcp.json"):
            self.assertTrue(os.path.isfile(os.path.join(chosen, made)), made)
        self.assertNotIn(f":{port}/", j["url"])
        self.assertIn(os.path.realpath(chosen), [p["root"] for p in ask("GET", "/api/projects")[1]["projects"]], "and it is in the menu from now on")

    def test_a_taken_port_is_said_plainly(self):
        root = support.project(self)   # another project, asked to use a port something else holds
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), "--port", str(self.port), "--no-open"],
                           env={**env, "SPLICED_PROJECT": root}, capture_output=True, text=True, timeout=90)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f"port {self.port} is already in use", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_with_no_port_named_it_takes_a_free_one_keeps_it_and_can_be_stopped(self):
        root = support.project(self)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        run = lambda *a: subprocess.run([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), *a], env={**env, "SPLICED_PROJECT": root, "SPLICED_NO_UPDATE_CHECK": "1"},
                                        capture_output=True, text=True, timeout=120)
        self.addCleanup(run, "--stop")
        r = run("--background", "--no-open")   # returns once the app answers: what an agent runs
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(root, ".cache", "server.json")) as f:
            info = json.load(f)
        self.assertNotEqual(info["port"], self.port, "not the port another project is on")
        self.assertIn(f"http://localhost:{info['port']}/app/", r.stdout)
        with open(os.path.join(root, ".cache", "port")) as f:
            self.assertEqual(int(f.read()), info["port"], "the project remembers its port")
        self.assertIn("already running", run("--background", "--no-open").stdout)
        r = run("--stop")
        self.assertIn("stopped", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(root, ".cache", "server.json")))
        self.assertIn("isn't running", run("--stop").stdout)

    def test_it_stops_when_the_app_that_started_it_is_gone(self):
        root = support.project(self)   # its own project: a second server on ours would just point at the first
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        app = subprocess.Popen(["sleep", "4"])   # stands in for the Mac app
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        srv = subprocess.Popen([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), "--port", str(port), "--no-open"],
                               env={**env, "SPLICED_PROJECT": root, "SPLICED_PARENT_PID": str(app.pid)}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: srv.poll() is None and srv.kill())
        app.wait()
        self.assertEqual(srv.wait(timeout=90), 0)
        self.assertFalse(os.path.exists(os.path.join(root, ".cache", "server.json")))

    # ---- who may ask
    def test_only_localhost_is_answered(self):
        for host in ("evil.test", f"evil.test:{self.port}", f"localhost:{self.port + 1}", "localhost", ""):
            for method, path in (("GET", "/api/state"), ("GET", "/app/app.js"), ("HEAD", "/app/"), ("POST", "/api/ops")):
                self.assertEqual(self.req(method, path, body={} if method == "POST" else None, host=host or " ")[0], 403, f"{method} {path} as {host!r}")
        for host in (f"localhost:{self.port}", f"127.0.0.1:{self.port}", f"LOCALHOST:{self.port}"):
            self.assertEqual(self.req("GET", "/api/info", host=host)[0], 200, host)

    def test_another_sites_page_can_change_and_read_nothing(self):
        op = {"ops": [{"op": "board.create", "name": "Made elsewhere"}]}
        own = f"http://localhost:{self.port}"
        for h in ({"Origin": "http://evil.test"}, {"Origin": "null"}, {"Origin": f"http://localhost:{self.port + 1}"}, {"Sec-Fetch-Site": "cross-site"},
                  {"Sec-Fetch-Site": "same-site"}, {"Origin": own, "Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.req("POST", "/api/ops", body=op, headers=h)[0], 403, h)
            self.assertEqual(self.req("GET", "/api/state", headers=h)[0], 403, h)
            for method, path in (("PATCH", "/api/uploads/f1x7u0"), ("DELETE", "/api/uploads/f1x7u0"), ("PUT", "/api/state"), ("POST", "/api/imports"), ("POST", "/api/stock/key"), ("POST", "/api/keys")):
                self.assertEqual(self.req(method, path, body={}, headers=h)[0], 403, f"{method} {path} {h}")
        self.assertNotIn("Made elsewhere", self.state()["boards"])
        self.assertIn("f1x7u0", self.req("GET", "/api/uploads")[2].decode())

    def test_a_key_goes_into_env_and_never_comes_back(self):
        secret = "sk_" + support.SENTINEL.lower() + "_1234567890"
        code, _, body = self.req("POST", "/api/keys", body={"id": "elevenlabs", "value": secret})
        self.assertEqual(code, 200, body)
        self.assertNotIn(secret.encode(), body)
        keys = {k["id"]: k for k in json.loads(body)["keys"]}
        self.assertTrue(keys["elevenlabs"]["set"])
        env = os.path.join(self.root, ".env")
        with open(env) as f:
            self.assertIn(f"ELEVENLABS_API_KEY={secret}", f.read())
        self.assertEqual(os.stat(env).st_mode & 0o777, 0o600, "only the person can read it")
        for path in ("/api/keys", "/api/doctor", "/api/state"):
            self.assertNotIn(secret.encode(), self.req("GET", path)[2], path)
        code, _, body = self.req("POST", "/api/keys", body={"id": "elevenlabs", "value": "not a key"})
        self.assertEqual(code, 400)
        code, _, body = self.req("POST", "/api/keys", body={"id": "elevenlabs", "remove": True})
        self.assertEqual(code, 200, body)
        with open(env) as f:
            self.assertNotIn("ELEVENLABS_API_KEY", f.read())
        with open(env) as f:
            self.assertIn("UNSPLASH_ACCESS_KEY", f.read(), "the other keys stay")
        self.assertEqual(self.req("POST", "/api/keys", body={"id": "nope", "value": secret})[0], 400)

    def test_the_apps_own_page_and_the_command_line_are_let_in(self):
        own = f"http://localhost:{self.port}"
        for i, h in enumerate(({"Origin": own, "Sec-Fetch-Site": "same-origin"}, {}, {"Sec-Fetch-Site": "none"})):
            code, _, body = self.req("POST", "/api/ops", body={"by": "test", "ops": [{"op": "board.create", "name": f"Let in {i}"}]}, headers=h)
            self.assertEqual(code, 200, body)
        boards = self.state()["boards"]
        self.assertTrue({"Let in 0", "Let in 1", "Let in 2"} <= set(boards))
        with open(os.path.join(self.root, "library", "state.json")) as f:
            self.assertIn("Let in 2", json.load(f)["boards"], "saved to the project")

    def test_a_bad_operation_is_a_clear_refusal(self):
        code, _, body = self.req("POST", "/api/ops", body={"ops": [{"op": "item.add", "board": "Fixture board", "id": "nope/s01"}]})
        self.assertEqual(code, 400)
        self.assertIn("unknown scene", json.loads(body)["error"])

    def test_a_folder_is_looked_at_before_anything_is_brought_in(self):
        demo = os.path.join(support.FIXTURE, "remotion", "public", "films", "demo")
        code, _, body = self.req("POST", "/api/folder/look", body={"folder": demo})
        d = json.loads(body)
        self.assertEqual((code, d["name"], d["pictures"], d["videos"]), (200, "demo", 7, 0))
        for bad in ("", "/no/such/folder", os.path.join(self.root, "library"), os.path.join(self.root, "library", "uploads")):
            for path in ("/api/folder/look", "/api/folder/import"):
                code, _, body = self.req("POST", path, body={"folder": bad})
                self.assertEqual(code, 400, f"{path} {bad}")
                self.assertTrue(json.loads(body)["error"])
        empty = os.path.join(self.root, "library", "..", "remotion", "src")   # a real folder with nothing a library takes: importing it queues nothing
        code, _, body = self.req("POST", "/api/folder/import", body={"folder": empty})
        self.assertEqual((code, json.loads(body).get("jobs")), (200, None))
        self.assertEqual(json.loads(self.req("GET", "/api/imports")[2])["jobs"], [])
        self.assertEqual(self.req("POST", "/api/folder/import", body={"folder": demo}, headers={"Origin": "http://evil.test"})[0], 403, "another site's page can't make the app read a folder")

    def test_a_link_to_upload_must_be_a_web_link(self):
        for url in ("file:///etc/hosts", "FILE:///etc/hosts", "ftp://example.com/a.png", "/etc/hosts", ""):
            code, _, body = self.req("POST", "/api/uploads/url", body={"url": url})
            self.assertEqual(code, 400, url)
            self.assertIn("web link", json.loads(body)["error"], url)

    def test_reveal_stays_inside_the_project(self):
        for path in ("../", "/etc/hosts", "library/../../"):
            self.assertEqual(self.req("POST", "/api/reveal", body={"path": path})[0], 404, path)

    def test_films_in_production_are_the_projects(self):
        films = json.loads(self.req("GET", "/api/productions")[2])
        self.assertEqual([f["slug"] for f in films], ["demo"])
        p = json.loads(self.req("GET", "/api/productions/demo")[2])
        self.assertEqual([b["id"] for b in p["beats"]], ["hook", "demo", "end-card"])
        self.assertEqual(self.req("GET", "/api/productions/nope")[0], 404)

    def test_the_app_makes_a_folder_and_moves_a_film_into_it(self):
        code, _, body = self.req("POST", "/api/folders", body={"name": "Branding videos"})
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["folder"], {"folder": "branding-videos", "name": "Branding videos"})
        self.assertIn(b'"folders": [{"folder": "branding-videos"', self.req("GET", "/api/boot.js")[2])
        self.assertEqual(self.req("POST", "/api/folders", body={"name": "", "folder": "../out"})[0], 400)
        try:
            code, _, body = self.req("POST", "/api/productions/demo/folder", body={"folder": "branding-videos"})
            self.assertEqual(code, 200, body)
            p = json.loads(body)
            self.assertEqual((p["folder"], p["renders_dir"]), ("branding-videos", "branding-videos/renders"))
            self.assertTrue(os.path.isfile(os.path.join(self.root, "branding-videos", "renders", "demo-v1.mp4")))
            self.assertEqual(self.req("POST", "/api/productions/demo/folder", body={"folder": "nowhere"})[0], 400)
        finally:   # the other tests share this project: put the film back
            self.req("POST", "/api/productions/demo/folder", body={"folder": ""})
        self.assertTrue(os.path.isfile(os.path.join(self.root, "remotion", "out", "demo-v1.mp4")))


if __name__ == "__main__":
    unittest.main()
