"""Tripwires: things that must not creep back into the tool."""
import json, os, re, subprocess, unittest

import support

TEXT = (".py", ".js", ".css", ".html", ".md", ".json", ".toml", ".tsv", ".webmanifest")


def files(root):
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git")]
        for n in names:
            if n.endswith(TEXT):
                yield os.path.join(d, n)


# Where the publisher is named on purpose: who holds the copyright and answers for it, and where the project lives.
# Everything else in the repo is checked. A new line here is a decision, not a convenience.
PUBLISHER = {
    "NOTICE": "the copyright line and the disclaimer",
    "README.md": "the repository's address, and who makes Spliced (Your responsibility)",
    "CONTRIBUTING.md": "the repository's address",
    "package.json": "the repository's address",
    "mac/Resources/Info.plist": "the app's identifier, and where its releases are",
    "mac/Sources/Spliced/AppDelegate.swift": "the Help link",
    "mac/Sources/Spliced/Debug.swift": "notification names under the app's identifier",
    "mac/scripts/snap.swift": "notification names under the app's identifier",
}


def tracked():
    """Every text file git tracks, as paths from the repo's root (a checkout without git: every text file there is)."""
    try:
        out = subprocess.run(["git", "-C", support.REPO, "ls-files"], capture_output=True, text=True, timeout=30)
        names = out.stdout.split("\n") if out.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        names = []
    names = [n for n in names if n] or [os.path.relpath(p, support.REPO) for p in files(support.REPO)]
    return [n for n in names if n.endswith(TEXT + (".swift", ".plist", ".yml", ".sh", ".tsx", ".ts", ".tsv")) or "." not in os.path.basename(n)]


class Guard(unittest.TestCase):
    def test_no_company_or_person_is_written_into_the_repo(self):
        # the tool, the film kit, the example film, the tests and the docs: nothing names a company, a person or a
        # private path, so anyone can run their own. The names are hashes in support.UNNAMED.
        hits = []
        for rel in tracked():
            p = os.path.join(support.REPO, rel)
            if rel in PUBLISHER or not os.path.isfile(p):
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if support.named(line) or ("/Users/" in line and not rel.startswith("tests/")):
                            hits.append(f"{rel}:{i}: {line.strip()[:100]}")
            except UnicodeDecodeError:
                continue
        self.assertEqual(hits, [], "a brand, a person or a private path in the repo: it belongs in a project's spliced.json")

    def test_the_publisher_is_named_only_where_it_must_be(self):
        for rel in PUBLISHER:
            with open(os.path.join(support.REPO, rel), encoding="utf-8") as f:
                self.assertTrue(any(support.named(l) for l in f), f"{rel} no longer names the publisher: take it off the list")

    def test_nothing_that_ships_links_into_someones_account(self):
        # a generated sound or picture is recorded with its prompt and model, never with a link to the account that made it
        link = re.compile(r"https?://[^\s\"')]*(/app/flows?/|/app/projects?/|/design/|/file/d/|/workspace/)[^\s\"')]*", re.I)
        hits = []
        for rel in tracked():
            if rel.startswith(("spliced/", "starter/")) and os.path.isfile(os.path.join(support.REPO, rel)):
                with open(os.path.join(support.REPO, rel), encoding="utf-8", errors="replace") as f:
                    hits += [f"{rel}:{i}" for i, line in enumerate(f, 1) if link.search(line)]
        self.assertEqual(hits, [])

    def test_the_tool_never_works_out_a_project_from_where_it_is_installed(self):
        for p in files(support.TOOLS):
            if p.endswith(".py"):
                with open(p) as f:
                    self.assertNotIn("dirname(os.path.dirname(os.path.abspath(__file__)))", f.read(), os.path.relpath(p, support.REPO))

    def test_the_app_builds_no_url_or_command_by_hand(self):
        for p in files(os.path.join(support.TOOLS, "web")):
            if p.endswith(".js") and not p.endswith("core.js"):
                with open(p) as f:
                    s = f.read()
                self.assertNotRegex(s, r'["`]\.\./', os.path.relpath(p, support.REPO) + " climbs out of the app folder")
                self.assertNotRegex(s, r"uv run |python3 [a-z_/]+\.py", os.path.relpath(p, support.REPO) + " writes a command by hand: use SP.cmd")

    def test_no_user_data_sits_in_the_package(self):
        for name in ("state.json", "data.js", "library.json", "uploads.json"):
            for d, _, names in os.walk(support.TOOLS):
                self.assertNotIn(name, names, os.path.relpath(d, support.REPO))


class NothingGoesPublic(unittest.TestCase):
    """Until the owner releases Spliced, no merge, tag or release may publish it anywhere. Releasing means
    removing these locks on purpose, in the release's own pull request."""

    def test_the_packages_refuse_to_be_published(self):
        with open(os.path.join(support.REPO, "package.json")) as f:
            self.assertIs(json.load(f).get("private"), True, "package.json: npm publish refuses a private package")
        with open(os.path.join(support.REPO, "pyproject.toml")) as f:
            self.assertIn('"Private :: Do Not Upload"', f.read(), "pyproject.toml: PyPI refuses this classifier")

    def test_no_workflow_publishes_or_runs_on_its_own_with_write_access(self):
        publish = re.compile(r"npm publish|pnpm publish|yarn publish|uv publish|twine upload|gh-action-pypi-publish|"
                             r"gh repo edit|--visibility|deploy-pages|upload-pages-artifact|wrangler|vercel|netlify|docker push", re.I)
        wf = os.path.join(support.REPO, ".github", "workflows")
        for n in sorted(os.listdir(wf)):
            with open(os.path.join(wf, n)) as f:
                text = f.read()
            self.assertIsNone(publish.search(text), f"{n} publishes something: {publish.search(text) and publish.search(text).group(0)}")
            on = text[text.index("\non:"):text.index("\njobs:")] if "\non:" in text else ""
            if re.search(r"contents:\s*write|id-token:\s*write|packages:\s*write|pages:\s*write", text):
                self.assertNotRegex(on, r"\b(push|release|pull_request|schedule|workflow_run)\b", f"{n} can write and starts on its own: only by hand (workflow_dispatch)")


if __name__ == "__main__":
    unittest.main()
