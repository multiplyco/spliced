"""A project in git with a second worktree (what a Conductor workspace is): where renders made in the worktree go,
how they are named and served, and the main checkout seeing the films being made there."""
import json, os, shutil, subprocess, sys, unittest

import support

CLI = os.path.join(support.TOOLS, "cli.py")


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)


class Worktrees(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("no git")
        self.main = support.project(self)
        git(self.main, "init", "-q", "-b", "main")
        git(self.main, "-c", "user.email=t@example.com", "-c", "user.name=t", "add", "-A")
        git(self.main, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "fixture")
        self.wt = os.path.join(os.path.dirname(self.main), "lisbon")
        git(self.main, "worktree", "add", "-q", "-b", "new-film", self.wt)

    def env(self):
        return {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}

    def cli(self, root, *args):
        r = subprocess.run([sys.executable, CLI, "--project", root, *args], capture_output=True, text=True, cwd=root, env=self.env(), timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def py(self, root, code):
        r = subprocess.run([sys.executable, "-c", f"import sys, json; sys.path.insert(0, {support.TOOLS!r}); {code}"],
                           capture_output=True, text=True, env={**self.env(), "SPLICED_PROJECT": root}, cwd=root, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def render_in_main(self, name):
        """What `spliced film render` run in the worktree leaves: the render in the main checkout's remotion/out."""
        out = os.path.join(self.main, "remotion", "out")
        shutil.copy(os.path.join(out, "demo-v1.mp4"), os.path.join(out, name))

    def test_a_render_made_in_a_worktree_goes_to_the_main_checkout(self):
        here = self.py(self.wt, "import paths, film; print(json.dumps([paths.render_home(), film.production('demo')['renders_dir']]))")
        self.assertEqual(here, [os.path.realpath(self.main), "@main/remotion/out"])
        self.cli(self.wt, "film", "new", "second", "--board", "Fixture board")
        self.render_in_main("second-v1.mp4")
        files = self.py(self.wt, "import film; print(json.dumps([r['file'] for r in film.production('second')['renders']]))")
        self.assertEqual(files, ["@main/remotion/out/second-v1.mp4"])

    def test_the_worktree_serves_a_render_from_the_main_checkout_and_nothing_else_there(self):
        self.render_in_main("demo-v9.mp4")
        with open(os.path.join(self.main, ".env"), "w") as f:
            f.write("KEY=x\n")
        got = self.py(self.wt, "import paths; print(json.dumps([bool(paths.media(p)) for p in ("
                               "'@main/remotion/out/demo-v9.mp4', '@main/.env', '@main/spliced.json', '@main/../x.mp4', '@main//etc/x.mp4')]))")
        self.assertEqual(got, [True, False, False, False, False])
        # and in a project that is no worktree, @main means nothing
        self.assertEqual(self.py(self.main, "import paths; print(json.dumps(bool(paths.media('@main/remotion/out/demo-v9.mp4'))))"), False)

    def test_the_main_checkout_lists_films_being_made_in_its_worktrees(self):
        self.cli(self.wt, "film", "new", "second", "--board", "Fixture board")
        self.render_in_main("second-v1.mp4")
        films = self.py(self.main, "import film; print(json.dumps([(p['slug'], p.get('workspace', {}).get('branch'), p.get('workspace', {}).get('name'), (p['latest'] or {}).get('file')) for p in film.summaries()]))")
        self.assertIn(["demo", None, None, "remotion/out/demo-v1.mp4"], films)
        self.assertIn(["second", "new-film", "lisbon", "remotion/out/second-v1.mp4"], films)
        # the worktree itself lists its own films, not other worktrees'
        self.assertEqual([f[0] for f in self.py(self.wt, "import film; print(json.dumps([(p['slug'],) for p in film.summaries()]))")], ["demo", "second"])

    def test_a_project_can_keep_renders_with_the_branch(self):
        p = os.path.join(self.wt, "spliced.json")
        with open(p) as f:
            c = json.load(f)
        c["worktree_renders"] = "worktree"
        with open(p, "w") as f:
            json.dump(c, f)
        here = self.py(self.wt, "import paths, film; print(json.dumps([paths.render_home(), film.production('demo')['renders_dir']]))")
        self.assertEqual(here, [os.path.realpath(self.wt), "remotion/out"])


if __name__ == "__main__":
    unittest.main()
