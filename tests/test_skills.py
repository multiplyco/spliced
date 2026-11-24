"""Spliced's skills in a project: kept current, and never written over a person's own changes (skillset.py)."""
import os, shutil, sys, unittest

import support

sys.path.insert(0, support.TOOLS)
import skillset  # noqa: E402


class Skills(unittest.TestCase):
    def setUp(self):
        self.root = support.project(self)
        self.ours = os.path.join(os.path.dirname(self.root), "skills")   # a stand-in for the skills Spliced ships
        os.makedirs(os.path.join(self.ours, "make-film"))
        self.write(os.path.join(self.ours, "make-film", "SKILL.md"), "version one\n")
        self.write(os.path.join(self.ours, "make-film", "NOTES.md"), "notes one\n")
        self.real, skillset.SKILLS = skillset.SKILLS, self.ours
        self.addCleanup(setattr, skillset, "SKILLS", self.real)
        self.mine = os.path.join(self.root, ".claude", "skills", "make-film")

    def write(self, p, text):
        with open(p, "w") as f:
            f.write(text)

    def read(self, p):
        with open(p) as f:
            return f.read()

    def test_a_new_version_replaces_what_is_untouched_and_leaves_what_was_changed(self):
        skillset.install(self.root)
        self.assertEqual(skillset.status(self.root), {"make-film": "current"})
        self.write(os.path.join(self.mine, "NOTES.md"), "my own notes\n")          # the person changes one file
        self.write(os.path.join(self.mine, "EXTRA.md"), "a file of my own\n")       # and adds one
        self.assertEqual(skillset.status(self.root), {"make-film": "edited"})
        self.write(os.path.join(self.ours, "make-film", "SKILL.md"), "version two\n")   # Spliced is updated
        self.write(os.path.join(self.ours, "make-film", "NOTES.md"), "notes two\n")
        self.assertEqual(skillset.status(self.root), {"make-film": "older"})
        done, saved = skillset.install(self.root, asked=False)                    # the quiet refresh when the app starts
        self.assertEqual((dict(done), saved), ({"make-film/SKILL.md": "updated", "make-film/NOTES.md": "kept"}, None))
        self.assertEqual(self.read(os.path.join(self.mine, "SKILL.md")), "version two\n")
        self.assertEqual(self.read(os.path.join(self.mine, "NOTES.md")), "my own notes\n")
        self.assertEqual(self.read(os.path.join(self.mine, "EXTRA.md")), "a file of my own\n")
        self.assertEqual(skillset.status(self.root), {"make-film": "edited"})
        done, saved = skillset.install(self.root, force=True)                      # --force: replaced, and the old one kept
        self.assertEqual(dict(done)["make-film/NOTES.md"], "replaced")
        self.assertEqual(self.read(os.path.join(self.root, saved, "make-film", "NOTES.md")), "my own notes\n")
        self.assertEqual(self.read(os.path.join(self.mine, "NOTES.md")), "notes two\n")
        self.assertEqual(self.read(os.path.join(self.mine, "EXTRA.md")), "a file of my own\n", "a file the person added is never touched")

    def test_nothing_is_put_where_nobody_asked(self):
        self.assertEqual(skillset.install(self.root, asked=False), ([], None))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".claude", "skills")), "a project without the skills gets none on its own")

    def test_a_copy_from_before_there_was_a_record(self):
        shutil.copytree(os.path.join(self.ours, "make-film"), self.mine)           # put there by an older Spliced: no record
        self.write(os.path.join(self.mine, "SKILL.md"), "an older version, or my edit: nobody can tell\n")
        self.assertEqual(skillset.status(self.root), {"make-film": "unknown"})
        done, saved = skillset.install(self.root, asked=False)
        self.assertEqual((dict(done)["make-film/SKILL.md"], saved), ("left", None), "not touched unless asked")
        done, saved = skillset.install(self.root)
        self.assertEqual(dict(done)["make-film/SKILL.md"], "replaced")
        self.assertIn("nobody can tell", self.read(os.path.join(self.root, saved, "make-film", "SKILL.md")))
        self.assertEqual(skillset.status(self.root), {"make-film": "current"})

    def test_a_file_spliced_no_longer_ships_goes_unless_it_was_changed(self):
        skillset.install(self.root)
        os.remove(os.path.join(self.ours, "make-film", "NOTES.md"))
        skillset.install(self.root)
        self.assertFalse(os.path.exists(os.path.join(self.mine, "NOTES.md")))


if __name__ == "__main__":
    unittest.main()
