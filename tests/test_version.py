"""Which Spliced this is, and the list of what changed that the app shows."""
import os, re, subprocess, sys, unittest

import support

WEB = os.path.join(support.TOOLS, "web")


class Version(unittest.TestCase):
    def test_the_package_and_its_metadata_agree(self):
        with open(os.path.join(support.TOOLS, "__init__.py")) as f:
            package = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
        with open(os.path.join(support.REPO, "pyproject.toml")) as f:
            meta = re.search(r'(?m)^version\s*=\s*"([^"]+)"', f.read()).group(1)
        self.assertEqual(package, meta, "bump both: spliced/__init__.py and pyproject.toml")
        self.assertRegex(package, r"^\d+\.\d+\.\d+")

    def test_the_command_says_which_it_is_without_needing_a_project(self):
        r = subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--version"], capture_output=True, text=True, cwd="/",
                           env={k: v for k, v in os.environ.items() if not k.startswith("SPLICED_")})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.strip(), r"^spliced \d+\.\d+\.\d+( \(build [0-9a-f]{7,}\))?$")


class Changelog(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(WEB, "changelog.md"), encoding="utf-8") as f:
            text = re.sub(r"(?m)^<!-- release \d+\.\d+\.\d+ \d{4}-\d{2}-\d{2} -->\n", "", f.read())   # (where a release begins: scripts/release.py)
            self.entries = [e.split("\n") for e in re.split(r"(?m)^## ", text)[1:]]

    def test_every_entry_can_be_shown(self):
        self.assertGreaterEqual(len(self.entries), 5)
        for lines in self.entries:
            title = lines[0].strip()
            self.assertTrue(title and len(title) <= 60, title)
            self.assertRegex(lines[1], r"^\d{4}-\d{2}-\d{2}$", f"{title}: the date goes on the line under the title")
            self.assertRegex(lines[2], r"^\*[^*].+\*$", f"{title}: one line in italics says it in a sentence")
            body = "\n".join(lines[3:]).strip()
            self.assertGreater(len(body), 80, f"{title}: say what changed for the person using it")
            for alt, src in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", body):
                self.assertTrue(alt.strip(), f"{title}: a picture says what it shows")
                self.assertTrue(os.path.isfile(os.path.join(WEB, src)), f"{title}: {src} is missing")
                self.assertLess(os.path.getsize(os.path.join(WEB, src)), 250_000, f"{src} is heavy for a changelog picture")

    def test_newest_first_and_in_house_style(self):
        dates = [lines[1] for lines in self.entries]
        self.assertEqual(dates, sorted(dates, reverse=True), "the newest change goes at the top")
        text = "\n".join("\n".join(l) for l in self.entries)
        self.assertNotIn("—", text, "no em dashes")
        self.assertNotIn("/Users/", text)
        self.assertFalse([l for l in text.split("\n") if support.named(l)], "the changelog names no company or person")


sys.path.insert(0, os.path.join(support.REPO, "scripts"))
import release  # noqa: E402

LOG = """# What's new

How to write an entry.

## Newest
2026-03-02
*Something new.*

It does a thing.

![a picture](changelog/x.jpg)

## Before that
2026-03-01
*A fix.*

It was wrong and is right.

<!-- release 0.1.0 2026-02-01 -->

## The first thing
2026-01-20
*Where it began.*

It began.
"""


class Release(unittest.TestCase):
    def test_the_next_number(self):
        for have, how, want in (("0.0.1", "minor", "0.1.0"), ("0.1.3", "patch", "0.1.4"), ("0.1.3", "minor", "0.2.0"), ("0.9.9", "major", "1.0.0"), ("0.1.0", "1.0.0", "1.0.0")):
            self.assertEqual(release.bump(have, how), want)
        for have, how in (("0.2.0", "0.1.9"), ("0.2.0", "0.2.0"), ("0.2.0", "soon"), ("0.2.0", "1.0")):
            with self.assertRaises(ValueError, msg=how):
                release.bump(have, how)

    def test_what_a_release_would_contain(self):
        self.assertEqual([t for t, _ in release.unreleased(LOG)], ["Newest", "Before that"])
        self.assertEqual([(t, v) for t, v, _ in release.entries(LOG)], [("Newest", None), ("Before that", None), ("The first thing", "0.1.0")])

    def test_marking_a_release(self):
        marked = release.mark(LOG, "0.2.0", "2026-03-03")
        self.assertEqual([(t, v) for t, v, _ in release.entries(marked)], [("Newest", "0.2.0"), ("Before that", "0.2.0"), ("The first thing", "0.1.0")])
        self.assertEqual(marked.replace("<!-- release 0.2.0 2026-03-03 -->\n\n", ""), LOG, "only the mark is added")
        self.assertLess(marked.index("<!-- release 0.2.0"), marked.index("## Newest"))
        with self.assertRaises(ValueError, msg="a second release with nothing new"):
            release.mark(marked, "0.2.1", "2026-03-04")

    def test_the_notes_are_the_entries_in_words(self):
        n = release.notes(release.mark(LOG, "0.2.0", "2026-03-03"), "0.2.0")
        self.assertEqual(n, "## Newest\n\n*Something new.*\n\nIt does a thing.\n\n## Before that\n\n*A fix.*\n\nIt was wrong and is right.")

    def test_the_real_changelog_can_be_released(self):
        with open(os.path.join(WEB, "changelog.md"), encoding="utf-8") as f:
            log = f.read()
        new = release.unreleased(log)
        if new:   # (right after a release there is nothing to mark)
            marked = release.mark(log, release.bump(release.current(), "minor"), "2026-01-01")
            self.assertEqual(release.unreleased(marked), [])
            self.assertGreater(len(release.notes(marked, release.bump(release.current(), "minor"))), 200)


if __name__ == "__main__":
    unittest.main()
