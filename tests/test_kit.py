"""spliced kit: the film kit copied into a project, kept current, and never written over a person's own changes."""
import hashlib, json, os, re, shutil, subprocess, sys, unittest

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


# deriveProfile (derive.ts) run in Node on a tween base and a spring base: seconds scaled by pace, bounce on UI and
# emphasis only, the first scene change and word style the kit draws, stagger and idle as given.
DERIVE_CHECK = r"""
import {deriveProfile} from './derive.ts';
const tw = (s) => ({kind: 'tween', curve: 'land', seconds: s, source: 'x'});
const sp = (omega, zeta) => ({kind: 'spring', spring: {omega, zeta}, source: 'x'});
const soft = {name: 'soft', feel: 'f', stagger: 0.1, idle: 1, viewChange: {kind: 'cut', seconds: 0},
  roles: {enter: tw(0.6), exit: tw(0.3), move: tw(0.75), ui: tw(0.45), emphasis: tw(0.5), camera: tw(1), textReveal: tw(0.5)}};
const apple = {name: 'apple', feel: 'f', stagger: 0.06, idle: 0.6, viewChange: {kind: 'sharedAxisX', seconds: 0.6},
  roles: {enter: sp(10, 1), exit: tw(0.3), move: sp(8, 1), ui: sp(12, 0.85), emphasis: sp(10, 0.7), camera: sp(6, 1), textReveal: sp(12, 1)}};
const a = deriveProfile(soft, {base: 'soft', pace: 1.25, bounce: 0.2, stagger: 0.12, transition: ['whip', 'blur'], text: ['typewriter', 'grey-to-ink'], idle: 0.7}, 'acme');
const b = deriveProfile(apple, {base: 'apple', pace: 2, bounce: 0}, 'globex');
const c = deriveProfile(apple, {base: 'apple'}, 'same');
console.log(JSON.stringify({a, b, c}));
"""


class ProfilesAsCode(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.rem = os.path.join(self.root, "remotion")
        self.gen = os.path.join(self.rem, "src", "profiles.generated.ts")

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", self.root, *args],
                           env={**env, "SPLICED_OFFLINE": "1"}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def read(self):
        with open(self.gen, encoding="utf-8") as f:
            return f.read()

    def test_every_profile_is_written_as_code_and_kept_current(self):
        self.cli("kit", "install", "--no-npm")
        self.assertIn("export const GENERATED_PROFILES = {};", self.read(), "no profiles yet: an empty one, so the kit builds")
        self.cli("profile", "new", "Acme house", "--motion", "material")
        self.cli("profile", "motion", "acme-house", "--pace", "1.25", "--bounce", "0", "--transition", "cut, blur")
        self.cli("profile", "set", "acme-house", "--palette", "#0B152B ink, #F4F1EC warm paper, #C34D7A", "--font", "Acme Sans", "--font-source", "google")
        text = self.read()
        self.assertIn('"acme-house": {', text)
        self.assertIn('"motion": {"base": "material", "pace": 1.25, "bounce": 0.0, "transition": ["cut", "blur"]},', text)
        self.assertIn('"colors": {"ink": "#0B152B", "warmPaper": "#F4F1EC", "color3": "#C34D7A"},', text)
        self.assertIn('"fonts": {"headline": {"family": "Acme Sans", "source": "google"}},', text)
        show = self.cli("profile", "show", "acme-house")
        self.assertIn("motion('acme-house')", show)
        self.assertIn("profileTokens('acme-house')", show)
        self.assertNotIn("Build it as a motion profile", show)
        # a file that went missing is the kit's to put back
        os.remove(self.gen)
        self.assertIn("differ from this Spliced", self.cli("kit"))
        self.cli("kit", "update")
        self.assertIn('"acme-house"', self.read())
        self.cli("profile", "remove", "acme-house")
        self.assertNotIn("acme-house", self.read())

    def test_a_project_without_the_kit_gets_no_file(self):
        shutil.rmtree(self.rem, ignore_errors=True)
        self.cli("profile", "new", "Acme")
        self.assertFalse(os.path.exists(self.gen))

    def test_the_kit_draws_the_scene_changes_and_word_styles_spliced_says_it_has(self):
        with open(os.path.join(support.TOOLS, "kit", "managed", "src", "lib", "motion", "derive.ts"), encoding="utf-8") as f:
            ts = f.read()
        kinds = re.search(r"TRANSITION_KINDS[^{]*\{(.*?)\}", ts, re.S).group(1)
        styles = re.search(r"TEXT_STYLES[^=]*=\s*\{(.*?)\}", ts, re.S).group(1)
        with open(os.path.join(support.TOOLS, "profiles.py"), encoding="utf-8") as f:
            src = f.read()
        for name, helper in re.findall(r'"([a-z-]+)": \("[^"]*", "(viewChange [^"]*)"', src):
            self.assertRegex(kinds, rf"['\"]?{re.escape(name)}['\"]?:", name)
        for name, helper in re.findall(r'"([a-z-]+)": \("[^"]*", "(text\.style [^"]*)"', src):
            self.assertRegex(styles, rf"['\"]?{re.escape(name)}['\"]?:", name)

    def test_a_profile_is_derived_from_its_base(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        d = os.path.join(os.path.dirname(self.root), "derive")
        os.makedirs(d)
        shutil.copy(os.path.join(support.TOOLS, "kit", "managed", "src", "lib", "motion", "derive.ts"), d)
        with open(os.path.join(d, "check.mjs"), "w") as f:
            f.write(DERIVE_CHECK)
        r = subprocess.run([node, "--experimental-strip-types", "--no-warnings", "check.mjs"], cwd=d, capture_output=True, text=True, timeout=60)
        if r.returncode and ("strip-types" in r.stderr or "Unknown file extension" in r.stderr):
            self.skipTest("this Node can't run TypeScript")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        a, b, c = out["a"], out["b"], out["c"]
        self.assertEqual(a["roles"]["enter"], {"kind": "tween", "curve": "land", "seconds": 0.75, "source": "x x1.25"}, "seconds times pace")
        self.assertEqual(a["roles"]["camera"]["seconds"], 1.25)
        ui = a["roles"]["ui"]
        self.assertEqual(ui["kind"], "spring", "a bounce turns a UI tween into a spring of the same length")
        self.assertAlmostEqual(ui["spring"]["zeta"], 0.8)
        self.assertAlmostEqual(ui["spring"]["omega"], 2 * 3.141592653589793 / (0.45 * 1.25), places=6)
        self.assertEqual(a["roles"]["move"]["kind"], "tween", "the bounce is only for UI and emphasis")
        self.assertEqual(a["viewChange"], {"kind": "blurThrough", "seconds": 0.75}, "the first scene change the kit has: blur, over whip")
        self.assertEqual(a["text"], {"style": "greyToInk"})
        self.assertEqual((a["stagger"], a["idle"], a["name"]), (0.12, 0.7, "acme"))
        self.assertAlmostEqual(b["roles"]["ui"]["spring"]["omega"], 6, msg="pace 2: a spring's frequency halves (twice as long)")
        self.assertEqual(b["roles"]["emphasis"]["spring"]["zeta"], 1, "bounce 0: no overshoot")
        self.assertEqual(b["roles"]["enter"]["spring"], {"omega": 5, "zeta": 1})
        self.assertEqual(b["viewChange"], {"kind": "sharedAxisX", "seconds": 1.2})
        self.assertEqual((c["roles"]["emphasis"]["spring"], c["viewChange"], c["stagger"]), ({"omega": 10, "zeta": 0.7}, {"kind": "sharedAxisX", "seconds": 0.6}, 0.06),
                         "nothing changed: the base as it is")

    def test_the_kit_typechecks_with_a_profile_as_code(self):
        nm = os.environ.get("SPLICED_KIT_NODE_MODULES", "")
        if not os.path.isfile(os.path.join(nm, ".bin", "tsc")):
            self.skipTest("set SPLICED_KIT_NODE_MODULES to a remotion/node_modules with typescript to typecheck the kit")
        self.cli("kit", "install", "--no-npm")
        os.symlink(nm, os.path.join(self.rem, "node_modules"))
        self.cli("profile", "new", "Acme house")
        self.cli("profile", "motion", "acme-house", "--pace", "1.2", "--bounce", "0.15", "--text", "grey-to-ink")
        self.cli("profile", "set", "acme-house", "--palette", "#0B152B ink")
        os.makedirs(os.path.join(self.rem, "src", "films", "check"))
        with open(os.path.join(self.rem, "src", "films", "check", "Check.tsx"), "w") as f:
            f.write("import {motion, profileTokens} from '../../lib/motion';\n"
                    "export const ink: string | undefined = profileTokens('acme-house').colors?.ink;\n"
                    "export const enter = (t: number) => motion('acme-house').enter(t, 0);\n")
        r = subprocess.run([os.path.join(nm, ".bin", "tsc"), "--noEmit", "-p", "."], cwd=self.rem, capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
