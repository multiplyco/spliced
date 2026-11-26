"""A project in git with a second worktree (what a Conductor workspace is): where renders made in the worktree go,
how they are named and served, and the main checkout seeing the films being made there."""
import json, os, shutil, subprocess, sys, unittest

import support

CLI = os.path.join(support.TOOLS, "cli.py")


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)


class WorktreeCase(unittest.TestCase):
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



class Worktrees(WorktreeCase):
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


class ProfileStore(WorktreeCase):
    """One profile store per project: a worktree reads and writes the main checkout's profiles/."""
    def run_cli(self, root, *args):
        return subprocess.run([sys.executable, CLI, "--project", root, *args], capture_output=True, text=True, cwd=root,
                              env={**self.env(), "SPLICED_OFFLINE": "1"}, timeout=120)

    def local_profile(self, slug, name):
        d = os.path.join(self.wt, "profiles", slug)
        os.makedirs(d)
        with open(os.path.join(d, "profile.json"), "w") as f:
            json.dump({"name": name, "motion": {"base": "soft"}}, f)
        with open(os.path.join(d, "PROFILE.md"), "w") as f:
            f.write("made in the worktree\n")
        return d

    def test_a_profile_made_in_a_worktree_is_the_main_checkouts(self):
        self.cli(self.wt, "profile", "new", "Acme house", "--motion", "material")
        self.assertTrue(os.path.isfile(os.path.join(self.main, "profiles", "acme-house", "profile.json")))
        self.assertFalse(os.path.exists(os.path.join(self.wt, "profiles")), "nothing is written in the worktree")
        self.assertIn("acme-house", self.cli(self.main, "profile"))
        self.cli(self.main, "profile", "learn", "acme-house", "never bounce the logo")
        out = self.cli(self.wt, "profile", "show", "acme-house")
        self.assertIn("never bounce the logo", out, "an edit in the main checkout is seen at once")
        self.assertIn(os.path.join(os.path.realpath(self.main), "profiles", "acme-house"), out, "an agent is told where it really is")
        self.assertIn("Profiles live in the main checkout", self.cli(self.wt, "profile"))
        got = self.py(self.wt, "import paths, profiles; print(json.dumps([paths.profile_home(), profiles.where('acme-house'), profiles.every()[0]['local']]))")
        self.assertEqual(got, [os.path.realpath(self.main), os.path.join(os.path.realpath(self.main), "profiles", "acme-house"), False])

    def test_a_profile_a_worktree_kept_itself_is_listed_local_and_moves_home(self):
        self.local_profile("globex", "Globex")
        self.cli(self.main, "profile", "new", "Acme")
        out = self.cli(self.wt, "profile")
        self.assertIn("globex", out)
        self.assertIn("(local: this worktree only)", out)
        self.assertIn("move-home", self.cli(self.wt, "profile", "show", "globex"))
        self.cli(self.wt, "profile", "learn", "globex", "always left-aligned")   # edits stay where it is
        self.assertFalse(os.path.exists(os.path.join(self.main, "profiles", "globex")))
        self.assertNotIn("globex", self.cli(self.main, "profile"), "the main checkout doesn't see a worktree's own")
        self.cli(self.wt, "profile", "move-home", "globex")
        self.assertFalse(os.path.exists(os.path.join(self.wt, "profiles", "globex")))
        with open(os.path.join(self.main, "profiles", "globex", "profile.json")) as f:
            p = json.load(f)
        self.assertEqual(p["rules"][0]["text"], "always left-aligned")
        self.assertFalse(p["default"], "the main checkout's default stays the default")
        self.assertIn("globex", self.cli(self.main, "profile"))
        self.assertNotIn("local", self.cli(self.wt, "profile"))

    def test_moving_home_never_writes_over_a_profile_of_the_same_name(self):
        self.cli(self.main, "profile", "new", "Acme", "--about", "the main checkout's")
        mine = self.local_profile("acme", "Acme (worktree)")
        r = self.run_cli(self.wt, "profile", "move-home", "acme")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("already has a profile called 'acme'", r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(mine, "profile.json")), "the worktree's copy is kept")
        with open(os.path.join(self.main, "profiles", "acme", "profile.json")) as f:
            self.assertEqual(json.load(f)["about"], "the main checkout's")
        out = self.cli(self.wt, "profile")
        self.assertIn("profiles/acme is not used", out)
        self.assertIn("the main checkout's", self.cli(self.wt, "profile", "show", "acme"))
        self.assertNotEqual(self.run_cli(self.main, "profile", "move-home", "acme").returncode, 0, "the main checkout has nowhere to move to")

    def test_a_project_can_keep_profiles_with_the_branch(self):
        p = os.path.join(self.wt, "spliced.json")
        with open(p) as f:
            c = json.load(f)
        c["worktree_profiles"] = "worktree"
        with open(p, "w") as f:
            json.dump(c, f)
        self.cli(self.wt, "profile", "new", "Acme")
        self.assertTrue(os.path.isfile(os.path.join(self.wt, "profiles", "acme", "profile.json")))
        self.assertFalse(os.path.exists(os.path.join(self.main, "profiles")))

    def test_a_profile_job_in_a_worktree_writes_to_the_main_checkout(self):
        self.cli(self.wt, "profile", "new", "Acme")
        self.cli(self.wt, "profile", "ask", "acme", "make it warmer")
        out = self.cli(self.wt, "imports", "next")
        self.assertIn(os.path.join(os.path.realpath(self.main), "profiles", "acme", "PROFILE.md"), out)
        argv = self.py(self.wt, "import os; os.environ['SPLICED_RUNNER'] = 'claude'; import runners; print(json.dumps(runners.argv('x')))")
        self.assertIn(os.path.join(os.path.realpath(self.main), "profiles"), argv, "a headless agent may write there")


if __name__ == "__main__":
    unittest.main()
