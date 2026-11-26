"""What a profile's sources can't do (digest.py, profiles._logo): a hostile SVG is cleaned, a page full of '<svg'
is scanned in one pass, --fetch never reaches this machine or the local network, and the logo copied into the film
kit is only ever one the digest cleaned. Pure Python: no PyMuPDF needed."""
import http.server, json, os, subprocess, sys, threading, time, unittest

import support
import digest  # noqa: E402  (support puts the package on the path)


class ASourceCantReachOut(unittest.TestCase):
    def test_the_svg_cleaner_leaves_a_picture_and_nothing_that_runs(self):
        hostile = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:x="http://www.w3.org/1999/xhtml" viewBox="0 0 10 10">'
                   '<style>@import url(https://acme.example/a.css); rect { fill: url(https://acme.example/p.svg) }</style>'
                   '<a href="#me"><animate attributeName="href" values="javascript:alert(1)"/>'
                   '<set attributeName="xlink:href" to="javascript:alert(2)"/><rect id="me" width="10" height="10" fill="#0E3B43"/></a>'
                   '<x:form action="javascript:alert(3)"><x:img src="https://acme.example/beacon.png"/></x:form>'
                   '<circle r="2" filter="url(https://acme.example/f.svg#f)" style="fill:url(#me)"/></svg>')
        out = digest.clean_svg(hostile)
        for gone in ("javascript", "animate", "<set", "acme.example", "@import", "form", "beacon"):
            self.assertNotIn(gone, out)
        self.assertIn("#0E3B43", out, "the picture itself stays")
        self.assertIn("url(#me)", out, "a url() to its own parts stays")
        self.assertIsNone(digest.clean_svg('<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>'))

    def test_a_page_full_of_svg_is_read_in_one_pass(self):
        t = time.time()
        self.assertEqual(digest.inline_svgs("<svg " * 200_000), [])
        self.assertLess(time.time() - t, 2, "a pattern with .*? took 15 s on this")
        self.assertEqual(digest.inline_svgs('<p><svgx></svgx><SVG viewBox="0 0 1 1"><g/></SVG><svg>b</svg>'),
                         ['<SVG viewBox="0 0 1 1"><g/></SVG>', "<svg>b</svg>"])

    def test_fetch_reaches_the_public_web_only(self):
        for host in ("127.0.0.1", "localhost", "10.0.0.8", "192.168.1.1", "169.254.169.254", "::1", "0.0.0.0"):
            self.assertFalse(digest._public(host), host)

        class H(http.server.BaseHTTPRequestHandler):
            hits = []

            def do_GET(self):
                H.hits.append(self.path)
                self.send_response(200); self.send_header("Content-Type", "image/png"); self.end_headers(); self.wfile.write(b"\x89PNG" + b"\0" * 100)

            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.assertIsNone(digest._get(f"http://127.0.0.1:{srv.server_address[1]}/api/keys", time.time() + 5))
        self.assertEqual(H.hits, [], "nothing on this machine is asked")


def bomb_pdf(path, side=7000):
    """A PDF of a few KB holding one gray picture of side x side: decoded, it would be side² bytes."""
    import zlib
    img = zlib.compress(b"\0" * (side * side), 9)
    content = b"q 500 0 0 500 0 0 cm /Im1 Do Q"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 500] /Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length %d >>stream\n" % len(content) + content + b"\nendstream",
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length %d >>stream\n"
            % (side, side, len(img)) + img + b"\nendstream"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    with open(path, "wb") as f:
        f.write(out)


@unittest.skipUnless(__import__("shutil").which("uv"), "needs uv")
class AHostilePdf(unittest.TestCase):
    def test_a_huge_picture_in_a_small_pdf_is_named_not_decoded(self):
        root = support.project(self)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        run = lambda *a: subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", root, *a],
                                        env={**env, "SPLICED_OFFLINE": "1"}, capture_output=True, text=True, timeout=600)
        run("profile", "new", "Acme")
        src = os.path.join(root, "profiles", "acme", "sources")
        os.makedirs(src, exist_ok=True)
        bomb_pdf(os.path.join(src, "brand.pdf"))
        self.assertLess(os.path.getsize(os.path.join(src, "brand.pdf")), 200_000)
        r = run("profile", "digest", "acme")
        if "No module named" in r.stdout + r.stderr or "Failed to" in r.stderr:
            self.skipTest("the digest's packages can't be installed here")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("7000 x 7000 picture, too big to take out", r.stdout)


class TheLogoInTheFilmKit(unittest.TestCase):
    def test_only_a_logo_the_digest_cleaned_is_copied(self):
        root = support.project(self)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        run = lambda *a: subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", root, *a],
                                        env={**env, "SPLICED_OFFLINE": "1"}, capture_output=True, text=True)
        run("profile", "new", "Acme")
        os.makedirs(os.path.join(root, "remotion", "public"), exist_ok=True)
        dig = os.path.join(root, "profiles", "acme", "digest")
        os.makedirs(os.path.join(dig, "logos"))
        public = os.path.join(root, "remotion", "public", "profiles", "acme")
        for path in ("../../.env", os.path.join(root, ".env"), "digest/logos/../../../../.env"):   # what an agent could write into index.json
            with open(os.path.join(dig, "index.json"), "w") as f:
                json.dump({"logos": [{"path": path}]}, f)
            run("profile", "set", "acme", "--about", "x")
            self.assertFalse(os.path.isdir(public) and os.listdir(public), f"{path} was copied into the film kit")
        with open(os.path.join(dig, "logos", "mark.svg"), "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>')
        with open(os.path.join(dig, "index.json"), "w") as f:
            json.dump({"logos": [{"path": "digest/logos/mark.svg"}]}, f)
        run("profile", "set", "acme", "--about", "y")
        self.assertEqual(os.listdir(public), ["logo.svg"], "the digest's own logo is still copied")


if __name__ == "__main__":
    unittest.main()
