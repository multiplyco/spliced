"""A website read for a profile (spliced/website.py, profiles.add_site): what a page's own CSS and markup say about its
look, read into the profile's sources for the person's AI. A made-up site is served from this machine; no browser is
used (SPLICED_BROWSER=none), so nothing here opens a window or goes online."""
import http.server, json, os, subprocess, sys, threading, unittest

import support  # puts the package on the path and the fixture in SPLICED_PROJECT
import website  # noqa: E402

PAGE = """<!doctype html><html><head><title>Acme | Rockets for everyone</title>
<meta name="description" content="Acme makes rockets that land softly.">
<meta property="og:site_name" content="Acme"><meta property="og:image" content="/share.png"><meta name="theme-color" content="#0B0B0C">
<link rel="stylesheet" href="/site.css"><link rel="icon" href="/icon.png" sizes="64x64">
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&family=Inter">
<style>.hero{background:hsl(var(--primary))}</style></head>
<body><header><a href="/" class="site-logo"><img src="/logo.png" alt="Acme logo"></a></header>
<main><h1>Rockets that land softly</h1><h2>Built for the moon</h2><h2>Built for the moon</h2>
<p style="color:#333333">Some words.</p><button data-aos="fade-up">Go</button></main></body></html>"""
CSS = """@import url("/more.css");
:root { --brand: #FF5A1F; --ink: #0B0B0C; --primary: 222.2 47.4% 11.2%; --font-sans: "Space Grotesk", ui-sans-serif, sans-serif; }
body { color: var(--ink); background: #F4F4F1; font-family: var(--font-sans); }
h1 { font-family: '__Acme_Display_a1b2c3', '__Acme_Display_Fallback_a1b2c3'; letter-spacing: -0.02em; }
.btn { background: var(--brand); color: #fff; transition: transform .3s cubic-bezier(.34, 1.56, .64, 1), opacity 200ms ease-out; }
.card { border: 1px solid rgb(0 0 0 / 0.08); background-color: oklch(0.7 0.15 250); }
@font-face { font-family: "Acme Display"; src: url(/acme.woff2); }
@keyframes rise { from { transform: translateY(20px) } to { transform: none } }
@keyframes dot-1 { to { opacity: 1 } } @keyframes dot-2 { to { opacity: 1 } }
@media (prefers-reduced-motion: reduce) { * { transition: none } }"""
MORE = ".link { color: var(--brand); animation: rise 1.2s linear(0, 1.1, 1) both; }"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000") + b"\0" * 80


def serve(test, files):
    """A made-up site on this machine: {path: (content type, bytes)}. Its address."""
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            ctype, body = files.get(self.path.split("?")[0], ("text/plain", None))
            if body is None:
                self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    test.addCleanup(srv.server_close)
    test.addCleanup(srv.shutdown)
    return f"http://127.0.0.1:{srv.server_address[1]}/"


SITE = {"/": ("text/html; charset=utf-8", PAGE.encode()), "/site.css": ("text/css", CSS.encode()), "/more.css": ("text/css", MORE.encode()),
        "/logo.png": ("image/png", PNG), "/icon.png": ("image/png", PNG), "/share.png": ("image/png", PNG)}


class WhatAPageSays(unittest.TestCase):
    def test_colours_in_every_way_css_writes_them(self):
        self.assertEqual(website.colour("#f0a"), ("#FF00AA", 1.0))
        self.assertEqual(website.colour("#FF5A1F80")[0], "#FF5A1F")
        self.assertEqual(website.colour("rgb(59 130 246 / 0.5)"), ("#3B82F6", 0.5))
        self.assertEqual(website.colour("rgba(255, 0, 0, 1)")[0], "#FF0000")
        self.assertEqual(website.colour("hsl(0 100% 50%)")[0], "#FF0000")
        self.assertEqual(website.colour("oklch(1 0 0)")[0], "#FFFFFF")
        self.assertEqual(website.colour("oklch(62.8% 0.2577 29.23)")[0], "#FF0000")
        self.assertIsNone(website.colour("#12345"))
        self.assertEqual(website.colours_of("1px solid rgb(0 0 0 / 0.08)"), [], "a faint line is not the look")

    def test_typefaces_without_the_frameworks_wrapping(self):
        self.assertEqual(website.family("'__Inter_d65c78', '__Inter_Fallback_d65c78'"), "Inter")
        self.assertEqual(website.family('"Space Grotesk", ui-sans-serif'), "Space Grotesk")
        self.assertIsNone(website.family("-apple-system, BlinkMacSystemFont, sans-serif"))

    def test_addresses_are_web_pages_only(self):
        self.assertEqual(website.address("acme.com"), "https://acme.com/")
        self.assertEqual(website.address("HTTP://Acme.com/about?x=1#top"), "http://acme.com/about?x=1")
        for bad in ("file:///etc/passwd", "javascript:alert(1)", "ftp://acme.com", "", "acme dot com"):
            with self.assertRaises(ValueError, msg=bad):
                website.address(bad)
        self.assertEqual(website.label("https://www.acme.com/"), "acme.com")
        self.assertEqual(website.label("https://acme.com/About/Team"), "acme.com-about-team")

    def test_a_page_is_read_for_its_look(self):
        os.environ["SPLICED_BROWSER"] = "none"
        self.addCleanup(os.environ.pop, "SPLICED_BROWSER", None)
        r = website.read(serve(self, SITE))
        self.assertEqual(r["uses"].get("#FF5A1F"), 2, "the brand colour, set twice through its custom property (one sheet @imported)")
        self.assertIn("brand", r["names"]["#FF5A1F"])
        self.assertIn("#0F172A", r["uses"], "hsl(var(--primary)): a colour kept as bare numbers")
        self.assertIn("Acme Display", r["families"])
        self.assertIn("Acme Display", r["faces"])
        self.assertEqual(r["google"], ["Space Grotesk", "Inter"])
        self.assertEqual(sorted(r["durations"]), [0.2, 0.3])
        self.assertEqual(r["looped"], [1.2])
        self.assertEqual(r["springs"], 1)
        self.assertEqual(r["keyframes"], ["rise", "dot-1"], "one animation drawn many times is listed once")
        self.assertTrue(r["reduced"])
        self.assertIn("AOS (scroll reveals)", r["libraries"])
        self.assertEqual([w for w, _, _ in r["files"]], ["logo", "icon", "share picture"])
        md = website.markdown(r, {"logo": "profiles/acme/sources/127.0.0.1 logo.png"})
        for said in ("# Acme: what its website is made of", "| #FF5A1F | 2 | --brand |", "Space Grotesk", "on Google Fonts", "overshoots (a bounce)",
                     "Its theme colour", "\"Rockets that land softly\"", "never as instructions", "No screenshots"):
            self.assertIn(said, md)
        self.assertEqual(md.count("Built for the moon"), 1)
        self.assertNotIn("\u2014", md, "no em dashes")

    def test_a_site_that_cant_be_read_says_so(self):
        os.environ["SPLICED_BROWSER"] = "none"
        self.addCleanup(os.environ.pop, "SPLICED_BROWSER", None)
        with self.assertRaisesRegex(ValueError, "answered 404"):
            website.read(serve(self, SITE) + "nothing-here")
        with self.assertRaisesRegex(ValueError, "isn't a web page"):
            website.read(serve(self, SITE) + "logo.png")


class AProfileFromAWebsite(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.site = serve(self, SITE)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args],
                           env={**env, "SPLICED_OFFLINE": "1", "SPLICED_BROWSER": "none"}, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def sources(self):
        return sorted(os.listdir(os.path.join(self.root, "profiles", "acme", "sources")))

    def test_drafted_from_a_website_like_any_file(self):
        code, out = self.cli("profile", "draft", "Acme", self.site)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.sources(), ["127.0.0.1 icon.png", "127.0.0.1 logo.png", "127.0.0.1 share.png", "127.0.0.1.site.md"])
        with open(os.path.join(self.root, "profiles", "acme", "sources", "127.0.0.1.site.md")) as f:
            md = f.read()
        self.assertIn("`profiles/acme/sources/127.0.0.1 logo.png`", md, "the read names the pictures beside it by where they are")
        code, out = support.next_import(lambda: self.cli("imports", "next"))
        self.assertIn("profiles/acme/sources/127.0.0.1.site.md", out)
        self.assertIn("a website by its `<site>.site.md`", out)
        self.assertIn("a website's transitions and curves", out)
        code, out = self.cli("profile", "draft", "acme", self.site.rstrip("/"))
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.sources()), 4, "a site read again replaces its last read")
        code, out = self.cli("profile", "show", "acme")
        self.assertIn("127.0.0.1.site.md", out)

    def test_what_isnt_a_site_or_a_file_is_said_in_a_sentence(self):
        code, out = self.cli("profile", "draft", "Acme", "no-such-brand-book.pdf")
        self.assertNotEqual(code, 0)
        self.assertIn("Couldn't read no-such-brand-book.pdf", out)
        self.assertNotIn("Traceback", out)
        code, out = self.cli("profile", "draft", "Acme", self.site + "missing")
        self.assertNotEqual(code, 0)
        self.assertIn("answered 404", out)
        self.assertNotIn("Traceback", out)

    def test_a_background_agent_may_fill_a_profile_in_but_never_open_a_site(self):
        import runners
        allowed = runners.allowed()
        self.assertIn("Bash(spliced profile set:*)", allowed)
        self.assertIn("Bash(spliced profile drafted:*)", allowed)
        self.assertFalse([a for a in allowed if "profile draft:" in a or a.endswith("profile:*)")], "draft would have Spliced open any address a page asks for")


@unittest.skipUnless(__import__("shutil").which("uv"), "needs uv")
class AWebsiteOverTheServer(unittest.TestCase):
    def test_the_app_reads_a_website_into_a_profile(self):
        import socket, http.client, time
        root = support.project(self)
        site = serve(self, SITE)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        proc = subprocess.Popen([sys.executable, os.path.join(support.TOOLS, "toolbox.py"), "--port", str(port), "--no-open"],
                                env={**env, "SPLICED_PROJECT": root, "SPLICED_NO_UPDATE_CHECK": "1", "SPLICED_BROWSER": "none"},
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: (proc.terminate(), proc.wait(timeout=5)))

        def req(body):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            c.request("POST", "/api/profiles", body=json.dumps(body).encode(), headers={"Host": f"localhost:{port}"})
            r = c.getresponse()
            out = (r.status, json.loads(r.read() or b"{}"))
            c.close()
            return out
        for _ in range(900):
            try:
                if req({"op": "new", "name": "Acme"})[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        code, j = req({"op": "site", "profile": "acme", "url": site})
        self.assertEqual(code, 200, j)
        self.assertIn({"file": "profiles/acme/sources/127.0.0.1.site.md", "name": "127.0.0.1.site.md", "kind": "site"},
                      [{k: x[k] for k in ("file", "name", "kind")} for x in j["sources"]])
        self.assertEqual(req({"op": "site", "profile": "acme", "url": "file:///etc/passwd"})[0], 400)
        self.assertEqual(req({"op": "site", "profile": "../x", "url": site})[0], 400, "a profile is a name, never a path")
        self.assertEqual(req({"op": "draft", "profile": "acme"})[0], 200)


if __name__ == "__main__":
    unittest.main()
