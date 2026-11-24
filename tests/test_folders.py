"""The project's folders (spliced/folders.py, film.py, toolbox_state.py): sorting films, boards and assets, on a
throwaway copy of the fixture, through the `spliced` command as a person or an agent would."""
import json, os, shutil, subprocess, sys, unittest

import support

CLI = os.path.join(support.TOOLS, "cli.py")
HF_INDEX = ('<div data-composition-id="main" data-duration="4">'
            '<div data-composition-id="a" data-composition-src="compositions/a.html" data-start="0" data-duration="2"></div>'
            '<div data-composition-id="b" data-composition-src="compositions/b.html" data-start="2" data-duration="2"></div></div>')


class Folders(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)

    def run_cli(self, *args, cwd=None, ok=True, env=None):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, CLI, "--project", self.root, *args], capture_output=True, text=True,
                           cwd=cwd or self.root, env={**e, **(env or {})}, timeout=120)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def config(self):
        with open(os.path.join(self.root, "spliced.json")) as f:
            return json.load(f)

    def film(self, slug):
        out = self.run_cli("film", "list").stdout
        return next((line for line in out.splitlines() if line.startswith(slug + " ")), "")

    def py(self, code):
        """Run code with the tools imported, on this project; returns what it printed, parsed as JSON."""
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, "-c", f"import sys, json; sys.path.insert(0, {support.TOOLS!r}); {code}"],
                           capture_output=True, text=True, env={**e, "SPLICED_PROJECT": self.root}, cwd=self.root, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_a_folder_is_added_to_spliced_json_as_it_was_written(self):
        before = self.config()
        self.run_cli("folders", "add", "branding-videos")
        self.run_cli("folders", "add", "clients/acme", "--name", "Acme Inc")
        c = self.config()
        self.assertEqual(c["folders"], ["branding-videos", {"folder": "clients/acme", "name": "Acme Inc"}])
        self.assertEqual({k: v for k, v in c.items() if k != "folders"}, before)   # nothing else changed
        self.assertTrue(os.path.isdir(os.path.join(self.root, "clients", "acme")))
        out = self.run_cli("folders").stdout
        self.assertIn("Branding videos  (branding-videos/)", out)
        self.assertIn("Acme Inc  (clients/acme/)", out)
        self.run_cli("folders", "remove", "branding-videos")
        self.assertEqual(self.config()["folders"], [{"folder": "clients/acme", "name": "Acme Inc"}])
        self.assertTrue(os.path.isdir(os.path.join(self.root, "branding-videos")))   # removing it from the list deletes nothing

    def test_spliced_s_own_folders_and_paths_out_of_the_project_cannot_be_folders(self):
        for bad in ("library", "remotion", "reference", "../elsewhere", ".hidden", "/tmp"):
            r = self.run_cli("folders", "add", bad, ok=False)
            self.assertNotEqual(r.returncode, 0, bad)
        self.assertNotIn("folders", self.config())

    def test_a_remotion_film_moves_with_its_renders_and_renders_into_its_folder(self):
        self.run_cli("folders", "add", "branding-videos")
        out_dir = os.path.join(self.root, "remotion", "out")
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "demo-v1.mp4")))
        self.run_cli("film", "move", "demo", "branding-videos")
        moved = os.path.join(self.root, "branding-videos", "renders")
        self.assertEqual(sorted(os.listdir(moved)), ["demo-v1.json", "demo-v1.mp4"])
        self.assertFalse(os.path.exists(os.path.join(out_dir, "demo-v1.mp4")))
        with open(os.path.join(self.root, "remotion", "src", "films", "demo", "storyboard.json")) as f:
            self.assertEqual(json.load(f)["folder"], "branding-videos")
        p = self.py("import film; p = film.production('demo'); print(json.dumps({k: p[k] for k in ('folder', 'renders_dir')} | {'renders': [r['file'] for r in p['renders']]}))")
        self.assertEqual(p, {"folder": "branding-videos", "renders_dir": "branding-videos/renders", "renders": ["branding-videos/renders/demo-v1.mp4"]})
        self.assertIn("branding-videos", self.film("demo"))
        self.run_cli("film", "move", "demo", "-")   # and back out: the renders come back to remotion/out
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "demo-v1.mp4")))
        self.assertEqual(os.listdir(moved), [])
        with open(os.path.join(self.root, "remotion", "src", "films", "demo", "storyboard.json")) as f:
            self.assertNotIn("folder", json.load(f))

    def test_a_film_cannot_go_into_a_folder_the_project_does_not_have(self):
        r = self.run_cli("film", "move", "demo", "nowhere", ok=False)
        self.assertIn("no folder called", r.stderr)

    def test_a_hyperframes_film_lives_in_its_folder(self):
        d = os.path.join(self.root, "videos", "teaser")
        os.makedirs(os.path.join(d, "renders"))
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(HF_INDEX)
        shutil.copy(os.path.join(self.root, "remotion", "out", "demo-v1.mp4"), os.path.join(d, "renders", "teaser-v1.mp4"))
        self.run_cli("folders", "add", "explainer-videos")
        self.run_cli("film", "move", "teaser", "explainer-videos")
        self.assertFalse(os.path.exists(d))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "explainer-videos", "teaser", "index.html")))
        p = self.py("import film; p = film.production('teaser'); print(json.dumps([p['dir'], p['folder'], [r['file'] for r in p['renders']]]))")
        self.assertEqual(p, ["explainer-videos/teaser", "explainer-videos", ["explainer-videos/teaser/renders/teaser-v1.mp4"]])
        self.run_cli("film", "status", "teaser")

    def test_a_board_and_a_film_started_from_it_share_its_folder(self):
        self.run_cli("folders", "add", "clients/acme")
        self.run_cli("board", "folder", "Fixture board", "clients/acme")
        with open(os.path.join(self.root, "library", "state.json")) as f:
            self.assertEqual(json.load(f)["boards"]["Fixture board"]["folder"], "clients/acme")
        self.run_cli("film", "new", "second", "--board", "Fixture board")
        self.assertIn("clients/acme", self.film("second"))
        r = self.run_cli("board", "folder", "Fixture board", "nowhere", ok=False)
        self.assertIn("no folder called", r.stdout + r.stderr)
        self.run_cli("board", "folder", "Fixture board", "-")
        with open(os.path.join(self.root, "library", "state.json")) as f:
            self.assertNotIn("folder", json.load(f)["boards"]["Fixture board"])

    def test_work_started_inside_a_folder_goes_there(self):
        self.run_cli("folders", "add", "branding-videos")
        inside = os.path.join(self.root, "branding-videos")
        self.run_cli("board", "new", "Launch", cwd=inside)
        with open(os.path.join(self.root, "library", "state.json")) as f:
            self.assertEqual(json.load(f)["boards"]["Launch"].get("folder"), "branding-videos")
        self.run_cli("board", "add", "Launch", "demo-one/s01")
        self.run_cli("film", "new", "launch", "--board", "Launch", "--folder", "branding-videos")
        self.assertIn("branding-videos", self.film("launch"))

    def test_a_folders_own_files_show_under_it_in_assets(self):
        self.run_cli("folders", "add", "clients/acme")
        logos = os.path.join(self.root, "clients", "acme", "logos")
        os.makedirs(logos)
        src = next(os.path.join(self.root, "library", "uploads", f) for f in os.listdir(os.path.join(self.root, "library", "uploads")) if f.endswith(".png"))
        shutil.copy(src, os.path.join(logos, "logo.png"))
        os.makedirs(os.path.join(self.root, "clients", "acme", "renders"))   # renders are films' output, not assets
        shutil.copy(src, os.path.join(self.root, "clients", "acme", "renders", "frame.png"))
        a = self.py("import film; print(json.dumps([(x['file'], x['film'], x['folder'], x['source']) for x in film.library_assets()['assets']]))")
        mine = [x for x in a if x[0].startswith("clients/")]
        self.assertEqual(mine, [["clients/acme/logos/logo.png", "", "clients/acme", "upload"]])
        self.assertTrue(all(x[2] == "" for x in a if not x[0].startswith("clients/")))   # the films' assets: in no folder yet


if __name__ == "__main__":
    unittest.main()
