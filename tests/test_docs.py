"""The docs (docs/*.md, docs/README.md says how they work) stay true to the tool: every page has what the site needs to
place it, every link and picture is there, and every `spliced` command a page names is one the tool has. A change that
renames or removes a command fails here until the pages that mention it are brought up to date."""
import os, re, unittest

import support
import cli   # spliced/cli.py (support puts the package on the path)

DOCS = os.path.join(support.REPO, "docs")
SECTIONS = {"start", "app", "ai", "make", "reference"}
COMMANDS = set(cli.COMMANDS) | set(cli.BUILT_IN) | set(cli.ALIASES) | {"help"}


def pages():
    return sorted(n for n in os.listdir(DOCS) if n.endswith(".md") and n != "README.md")


def read(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as f:
        return f.read()


def front(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return dict(re.findall(r"^([a-z]+):\s*(.*)$", m.group(1), re.M)) if m else None


class Docs(unittest.TestCase):
    def test_every_page_says_where_it_goes(self):
        orders = {}
        for name in pages():
            fm = front(read(name))
            self.assertIsNotNone(fm, f"docs/{name}: no front matter (title, description, section, order)")
            for k in ("title", "description", "section", "order"):
                self.assertTrue(fm.get(k), f"docs/{name}: no {k}")
            self.assertIn(fm["section"], SECTIONS, f"docs/{name}: section is one of {sorted(SECTIONS)}")
            self.assertRegex(fm["order"], r"^\d+$", f"docs/{name}: order is a whole number")
            key = (fm["section"], int(fm["order"]))
            self.assertNotIn(key, orders, f"docs/{name} and docs/{orders.get(key)} have the same section and order")
            orders[key] = name

    def test_the_welcome_page_is_there(self):
        self.assertIn("welcome.md", pages(), "docs/welcome.md is the page the site serves at /docs")

    def test_every_link_and_picture_is_there(self):
        for name in pages():
            for target in re.findall(r"\]\(([^)\s]+)\)", read(name)):
                if re.match(r"^(https?:|mailto:|#)", target):
                    continue
                path = target.split("#")[0]
                self.assertFalse(path.startswith("/"), f"docs/{name}: {target} is a site path; link a page as `page.md`")
                self.assertTrue(os.path.isfile(os.path.join(DOCS, path)), f"docs/{name}: {target} is not in docs/")
                if path.startswith("images/"):
                    self.assertLess(os.path.getsize(os.path.join(DOCS, path)), 250_000, f"docs/{path}: a picture stays below 250 KB")

    def test_every_command_a_page_names_is_one_the_tool_has(self):
        named = re.compile(r"(?<![\w./-])spliced[ \t]+([a-z][a-z-]*)")
        for name in pages():
            text = read(name)
            # a block's comments are prose ("# for a spliced command"); only what would be typed counts
            blocks = [re.sub(r"(^|\s)#.*$", "", b, flags=re.M) for b in re.findall(r"```.*?```", text, re.S)]
            code = blocks + re.findall(r"`[^`\n]+`", re.sub(r"```.*?```", "", text, flags=re.S))
            for chunk in code:
                for cmd in named.findall(chunk):
                    self.assertIn(cmd, COMMANDS, f"docs/{name}: `spliced {cmd}` is not a command (spliced/cli.py)")

    def test_no_em_dashes(self):
        for name in pages() + ["README.md"]:
            self.assertNotIn("—", read(name), f"docs/{name}: no em dashes in the docs")


if __name__ == "__main__":
    unittest.main()
