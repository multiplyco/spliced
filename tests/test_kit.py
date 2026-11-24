"""spliced kit: the film kit copied into a project, kept current, and never written over a person's own changes."""
import hashlib, json, os, re, subprocess, sys, unittest

import support


# Films from someone's own library that an example must never cite, kept as hashes so this file doesn't name them
# either: sha256 of the lowercased slug, first 16 hex digits (as in test_guard.py).
CITED = {"0c0df7df051f01bd", "22dc02488a037639", "34f3af0033cf11d8", "da9e89e554aca6b4", "f28a4e7a54162e0d"}


def cited(line):
    """Does the line hold one of those slugs, alone or as the start of a longer one (name, name-2024, name/s03)?"""
    for word in re.findall(r"[a-z0-9][a-z0-9-]*", line.lower()):
        parts = word.split("-")
        if any(hashlib.sha256("-".join(parts[:i]).encode()).hexdigest()[:16] in CITED for i in range(1, len(parts) + 1)):
            return True
    return False


class Kit(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.rem = os.path.join(self.root, "remotion")
        self.bin = os.path.join(os.path.dirname(self.root), "bin")
        os.makedirs(self.bin)
        support.fake_npm(self.bin)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, "kit", *args],
                           env={**env, "SPLICED_OFFLINE": "1"}, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def read(self, rel):
        with open(os.path.join(self.rem, rel), encoding="utf-8") as f:
            return f.read()

    def test_install_puts_the_packages_in_too(self):
        code, out = self.cli("install")
        self.assertEqual(code, 0, out)
        self.assertIn("npm install (stand-in)", out)                       # no lock yet: install, not ci
        self.assertIn("remotion.dev/license", out)                          # the licence is said every time
        self.assertTrue(os.path.isdir(os.path.join(self.rem, "node_modules", "remotion")))
        self.assertIn("Packages (Remotion, React): installed", self.cli()[1])
        code, out = self.cli("packages")
        self.assertEqual(code, 0, out)
        self.assertNotIn("stand-in", out, "already in: nothing to do")

    def test_a_clone_without_its_packages_gets_them_with_its_lock(self):
        self.cli("install", "--no-npm")
        self.assertFalse(os.path.isdir(os.path.join(self.rem, "node_modules")))
        self.assertIn("not installed", self.cli()[1])
        with open(os.path.join(self.rem, "package-lock.json"), "w") as f:
            f.write("{}")
        code, out = self.cli("packages")
        self.assertEqual(code, 0, out)
        self.assertIn("npm ci (stand-in)", out)                             # a lock: exactly its versions
        self.assertTrue(os.path.isdir(os.path.join(self.rem, "node_modules", "remotion")))

    def test_packages_in_the_background(self):
        self.cli("install", "--no-npm")
        code, out = self.cli("packages", "--background")
        self.assertEqual(code, 0, out)
        self.assertIn("in the background", out)
        for _ in range(40):
            if os.path.isdir(os.path.join(self.rem, "node_modules", "remotion")):
                break
            __import__("time").sleep(0.1)
        self.assertIn("Packages (Remotion, React): installed", self.cli()[1])

    def test_install_update_and_a_file_changed_by_hand(self):
        code, out = self.cli("install")
        self.assertEqual(code, 0, out)
        for rel in ("src/lib/motion/profile.tsx", "src/lib/motion/spec.ts", "src/specimen/SystemMoves.tsx", "docs/CRAFT.md",
                    "public/audio/kit/kit.json", "src/Root.tsx", "src/profiles.ts", "package.json", ".gitignore"):
            self.assertTrue(os.path.isfile(os.path.join(self.rem, rel)), rel)
        self.assertNotIn("__NAME__", self.read("package.json"))
        with open(os.path.join(self.rem, ".spliced-kit.json")) as f:
            self.assertIn("src/lib/motion/profile.tsx", json.load(f)["files"])
        self.assertIn("(current)", self.cli()[1])
        # the project's own files are never touched again
        with open(os.path.join(self.rem, "src", "profiles.ts"), "a") as f:
            f.write("// ours\n")
        # a kit file changed by hand is noticed, kept, and only --force replaces it
        with open(os.path.join(self.rem, "docs", "CRAFT.md"), "a") as f:
            f.write("\nmine\n")
        self.assertIn("changed by hand", self.cli()[1])
        code, out = self.cli("update")
        self.assertNotEqual(code, 0)
        self.assertIn("docs/CRAFT.md", out)
        self.assertTrue(self.read("docs/CRAFT.md").endswith("mine\n"))
        code, out = self.cli("update", "--force")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.read("docs/CRAFT.md").endswith("mine\n"))
        self.assertTrue(self.read("src/profiles.ts").endswith("// ours\n"), "update never touches the project's own files")

    def test_a_first_install_does_not_write_over_someone_elses_files(self):
        os.makedirs(os.path.join(self.rem, "src", "lib"), exist_ok=True)
        with open(os.path.join(self.rem, "src", "lib", "sound.tsx"), "w") as f:
            f.write("// my own\n")
        code, out = self.cli("install")
        self.assertNotEqual(code, 0)
        self.assertIn("src/lib/sound.tsx", out)
        self.assertEqual(self.read("src/lib/sound.tsx"), "// my own\n")

    def test_the_starter_film_comes_in_and_is_registered(self):
        code, out = self.cli("starter")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.rem, "src", "films", "splice-explainer", "storyboard.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.rem, "public", "films", "splice-explainer", "audio", "score-deep-techno.mp3")))
        root = self.read("src/Root.tsx")
        self.assertIn('id="SpliceExplainer"', root)
        self.assertEqual(self.cli("starter")[0], 0)
        self.assertEqual(self.read("src/Root.tsx").count('id="SpliceExplainer"'), 1, "a second run adds nothing")

    def test_the_starter_shows_only_what_is_ours(self):
        # no citations of other companies' films, no review history, nothing private
        start = os.path.join(support.REPO, "starter")
        bad = []
        for d, _, names in os.walk(start):
            for n in names:
                if n.endswith((".json", ".md", ".tsx", ".ts", ".py")):
                    with open(os.path.join(d, n), encoding="utf-8") as f:
                        for i, line in enumerate(f, 1):
                            if "/Users/" in line or cited(line):
                                bad.append(f"{os.path.relpath(os.path.join(d, n), support.REPO)}:{i}")
        self.assertEqual(bad, [])
        for slug in os.listdir(os.path.join(start, "films")):
            with open(os.path.join(start, "films", slug, "src", "storyboard.json")) as f:
                sb = json.load(f)
            self.assertFalse([r for b in sb["beats"] for r in b.get("refs", []) if not r.startswith("system-moves/")], slug)
            self.assertFalse(sb.get("pins"), slug)


if __name__ == "__main__":
    unittest.main()
