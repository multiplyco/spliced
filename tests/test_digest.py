"""A profile's sources digested (spliced/digest.py): a PDF's text, pages and pictures, every picture measured, logos
cleaned, and what JSON and HTML hold, so an agent never opens the sources. Made-up sources, drawn in the test."""
import json, os, shutil, subprocess, sys, unittest

import support

DEPS = ["--with", "pymupdf", "--with", "pillow", "--with", "numpy"]

# The sources, drawn with PyMuPDF and Pillow in uv's environment: a two-page brand book (a product on white on both
# pages, a picture with a soft mask, a blurred backdrop), a device with a dark screen at a known place, on alpha.
DRAW = r'''
import io, sys, pymupdf
from PIL import Image, ImageDraw, ImageFilter
out = sys.argv[1]
def png(im):
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()
jar = Image.new("RGB", (300, 400), "white")
ImageDraw.Draw(jar).rectangle((110, 250, 190, 380), fill=(200, 40, 40))           # the subject sits low
masked = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
ImageDraw.Draw(masked).ellipse((40, 40, 200, 200), fill=(20, 90, 200, 255))
g = Image.linear_gradient("L").resize((320, 320))
back = Image.merge("RGB", [g.point(lambda v: 180 + v // 4), g.point(lambda v: 140 + v // 5), g.point(lambda v: 110)]).filter(ImageFilter.GaussianBlur(30))
doc = pymupdf.open()
p1 = doc.new_page(width=800, height=450)
p1.insert_text((40, 60), "Acme brand book", fontsize=28)
p1.insert_image(pymupdf.Rect(420, 40, 720, 440), stream=png(jar))
p1.insert_image(pymupdf.Rect(40, 120, 360, 440), stream=png(back))
p2 = doc.new_page(width=800, height=450)
p2.insert_text((40, 60), "Our colours: deep teal and amber", fontsize=20)
p2.insert_image(pymupdf.Rect(420, 40, 720, 440), stream=png(jar))
p2.insert_image(pymupdf.Rect(40, 120, 280, 360), stream=png(masked))
doc.save(out + "/Acme brand book.pdf")
dev = Image.new("RGBA", (300, 520), (0, 0, 0, 0))
d = ImageDraw.Draw(dev)
d.rounded_rectangle((20, 10, 280, 510), radius=30, fill=(235, 235, 240, 255))
d.rectangle((50, 60, 249, 439), fill=(24, 26, 30, 255))                            # the screen: x 50, y 60, 200 x 380
dev.save(out + "/terminal.png")
'''

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 20" onload="alert(1)"><script>alert(2)</script>'
       '<foreignObject><div>x</div></foreignObject><a href="https://example.com/x"><rect width="100" height="20" fill="#0E3B43"/></a></svg>')


def have_deps():
    if not shutil.which("uv"):
        return False
    r = subprocess.run(["uv", "run", "-q", "--no-project", *DEPS, "python", "-c", "import pymupdf, PIL, numpy"], capture_output=True, text=True, timeout=600)
    return r.returncode == 0


class Digest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deps = have_deps()

    def setUp(self):
        self.root = support.project(self)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args], env={**env, "SPLICED_OFFLINE": "1"},
                           capture_output=True, text=True, timeout=600)
        return r.returncode, r.stdout + r.stderr

    def sources(self):
        d = os.path.join(self.root, "profiles", "acme", "sources")
        os.makedirs(d, exist_ok=True)
        return d

    def test_a_profile_with_sources_says_to_digest_them_first(self):
        self.cli("profile", "new", "Acme")
        with open(os.path.join(self.sources(), "notes.txt"), "w") as f:
            f.write("calm\n")
        out = self.cli("profile", "show", "acme")[1]
        self.assertIn("## Digest", out)
        self.assertIn("Not digested yet", out)
        self.assertIn("profile digest acme", out)

    def test_the_sources_are_digested_once_and_measured(self):
        if not self.deps:
            self.skipTest("uv with PyMuPDF, Pillow and numpy isn't available here")
        self.cli("profile", "new", "Acme")
        src = self.sources()
        r = subprocess.run(["uv", "run", "-q", "--no-project", *DEPS, "python", "-c", DRAW, src], capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        import base64
        site = {"theme": {"colors": {"primary": "#0e3b43", "accent": "#FFB703"}, "fontFamily": "'Acme Sans', Helvetica, sans-serif"},
                "branding": {"logo": "data:image/svg+xml;base64," + base64.b64encode(SVG.encode()).decode()},
                "products": [{"title": "Globex Jar", "price": 12.5, "image": "https://example.com/jar.jpg", "url": "https://example.com/p/jar"},
                             {"name": "No price here", "image": "https://example.com/x.png"}],
                "hero": "https://example.com/hero.webp?w=800"}
        with open(os.path.join(src, "site.json"), "w") as f:
            json.dump(site, f)
        with open(os.path.join(src, "page.html"), "w") as f:
            f.write('<style>h1 { font-family: "Globex Serif", serif; color: #AA3311 }</style><svg viewBox="0 0 10 10"><circle r="4"/></svg>')
        code, out = self.cli("profile", "digest", "acme")
        self.assertEqual(code, 0, out)
        self.assertIn("Digested 4 source(s)", out)
        dg = os.path.join(self.root, "profiles", "acme", "digest")
        with open(os.path.join(dg, "index.json")) as f:
            idx = json.load(f)

        pdf = idx["documents"][0]
        self.assertEqual((pdf["kind"], pdf["pages"]), ("pdf", 2))
        with open(os.path.join(self.root, "profiles", "acme", pdf["text"])) as f:
            self.assertIn("Our colours: deep teal and amber", f.read())
        sheet = os.path.join(self.root, "profiles", "acme", pdf["sheet"])
        self.assertLess(os.path.getsize(sheet), 250 * 1024)

        pics = {tuple(i["pages"]) if i.get("pages") else i["path"]: i for i in idx["images"]}
        jar = pics[(1, 2)]   # on both pages, taken once
        self.assertEqual((jar["w"], jar["h"], jar["kind"]), (300, 400, "cutout"))
        self.assertGreater(jar["focus"][1], 0.7, "the subject sits low in its picture")
        self.assertAlmostEqual(jar["focus"][0], 0.5, delta=0.03)
        masked = next(i for i in idx["images"] if i.get("mask"))
        self.assertTrue(masked["path"].endswith(".png") and masked["alpha"])
        self.assertEqual(masked["kind"], "cutout")
        self.assertEqual(next(i for i in idx["images"] if i.get("pages") == [1] and i["w"] == 320)["kind"], "backdrop")
        dev = pics["sources/terminal.png"]
        self.assertEqual(dev["kind"], "cutout")
        for k, v in {"x": 50, "y": 60, "w": 200, "h": 380}.items():
            self.assertAlmostEqual(dev["screen"][k], v, delta=2, msg=k)

        self.assertEqual(len(idx["logos"]), 2)
        logo = idx["logos"][0]
        self.assertEqual((logo["key"], logo["how"]), ("branding.logo", "data URI"), "the one a key calls a logo comes first")
        with open(os.path.join(self.root, "profiles", "acme", logo["path"])) as f:
            svg = f.read()
        for bad in ("script", "onload", "foreignObject", "example.com"):
            self.assertNotIn(bad, svg)
        self.assertIn("<rect", svg)

        colours = {c["hex"]: c for c in idx["colours"]}
        self.assertIn("theme.colors.primary", colours["#0E3B43"]["keys"])
        self.assertIn("primary", colours["#0E3B43"]["names"])
        self.assertIn("#AA3311", colours)
        self.assertEqual({f["family"] for f in idx["fonts"]}, {"Acme Sans", "Helvetica", "Globex Serif"})
        self.assertEqual([(p["title"], p["price"], p["image"]) for p in idx["products"]], [("Globex Jar", 12.5, "https://example.com/jar.jpg")])
        self.assertEqual({u["url"] for u in idx["image_urls"]}, {"https://example.com/jar.jpg", "https://example.com/x.png", "https://example.com/hero.webp?w=800"})
        self.assertFalse(os.path.exists(os.path.join(dg, "fetched")), "nothing is downloaded unless asked")

        with open(os.path.join(dg, "README.md")) as f:
            readme = f.read()
        self.assertRegex(readme, r"terminal\.png  300x520  cutout alpha  subject .* screen x\d+ y\d+ w\d+ h\d+px")
        self.assertIn("Globex Jar", readme)
        self.assertIn("--fetch", readme)

        code, out = self.cli("profile", "digest", "acme")
        self.assertIn("is current", out, "unchanged sources: nothing is redone")
        show = self.cli("profile", "show", "acme")[1]
        self.assertIn("digest/README.md", show)
        self.assertNotIn("Not digested yet", show)
        with open(os.path.join(src, "more.txt"), "w") as f:
            f.write("more\n")
        self.assertIn("The sources changed since", self.cli("profile", "show", "acme")[1])


if __name__ == "__main__":
    unittest.main()
