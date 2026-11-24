"""The assets list is kept between requests and made again the moment anything it reads changes (film.py library_assets)."""
import json, os, subprocess, sys, unittest

import support

SCRIPT = r'''
import json, os, shutil, sys, time
sys.path.insert(0, sys.argv[1])
import film, paths
pub, src = os.path.join(paths.PUBLIC_FILMS, "demo"), os.path.join(film.FILMS_DIR, "demo")
used = lambda d, name: next(a for a in d["assets"] if a["name"] == name)["used"]
out = {}
a = film.library_assets(); b = film.library_assets()
out["kept"] = a is b
shutil.copy(os.path.join(pub, "plate.png"), os.path.join(pub, "second.png"))                  # a new file
c = film.library_assets()
out["new_file"] = [len(a["assets"]), len(c["assets"]), c is not a]
out["before"] = used(c, "second.png")
with open(os.path.join(src, "Scene.tsx"), "w") as f: f.write('staticFile("films/demo/second.png")')   # the film's code now names it
d = film.library_assets()
out["after"] = used(d, "second.png")
with open(os.path.join(src, "assets.json"), "w") as f: json.dump({"films/demo/second.png": {"label": "The second plate", "source": "higgsfield"}}, f)   # what made it, written down
e = film.library_assets()
out["label"] = next(x for x in e["assets"] if x["name"] == "second.png")["label"]
os.remove(os.path.join(pub, "second.png"))                                                   # and gone again
out["removed"] = len(film.library_assets()["assets"])
os.makedirs(os.path.join(paths.PUBLIC_FILMS, "other")); shutil.copy(os.path.join(pub, "plate.png"), os.path.join(paths.PUBLIC_FILMS, "other", "plate.png"))   # another film
out["films"] = sorted(x["slug"] for x in film.library_assets()["films"])
out["kept_again"] = film.library_assets() is film.library_assets()
print(json.dumps(out))
'''


class Kept(unittest.TestCase):
    def test_the_answer_is_kept_until_something_it_reads_changes(self):
        root = support.project(self)
        r = subprocess.run([sys.executable, "-c", SCRIPT, support.TOOLS], env={**os.environ, "SPLICED_PROJECT": root}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertTrue(d["kept"], "asked twice with nothing changed: the same answer, not made again")
        self.assertEqual(d["new_file"], [7, 8, True], "a new file is in the next answer")
        self.assertEqual((d["before"], d["after"]), (False, True), "the film's code naming a file changes whether it is used")
        self.assertEqual(d["label"], "The second plate", "so does what assets.json says about it")
        self.assertEqual(d["removed"], 7)
        self.assertEqual(d["films"], ["demo", "other"], "and so does a new film")
        self.assertTrue(d["kept_again"])


if __name__ == "__main__":
    unittest.main()
