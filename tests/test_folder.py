"""A folder of things already collected comes into the library once, sorted (folder.py, and its job in importer.py)."""
import json, os, shutil, subprocess, sys, tempfile, unittest

import support



def png(path, rgb, size=16):
    """A small picture of one colour (two colours: two different pictures)."""
    import struct, zlib
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


# Run inside a throwaway project (the tools take their project from the environment when they are imported).
SCRIPT = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import folder, importer, uploads, paths
stuff, out = sys.argv[2], {}
out["look"] = folder.look(stuff)
for bad in (os.path.join(stuff, "nope"), paths.LIB, os.path.join(paths.LIB, "uploads"), ""):
    try: folder.look(bad); out.setdefault("refused", []).append(False)
    except ValueError as e: out.setdefault("refused", []).append(str(e))
before = len(uploads.items())
said = []
r = folder.bring(stuff, say=said.append)
out["first"] = r
out["added"] = [{k: x.get(k) for k in ("title", "kind", "source", "by")} for x in uploads.items()[before:]]
out["files_exist"] = all(os.path.exists(os.path.join(paths.ROOT, x["file"])) for x in uploads.items()[before:])
out["said"] = said[:1]
out["summary"] = folder.summary(r)
out["films_exist"] = [os.path.exists(os.path.join(paths.ROOT, f["file"])) for f in r["films"]]
out["second"] = folder.bring(stuff)
out["second_summary"] = folder.summary(out["second"])
out["count"] = len(uploads.items()) - before
if "--job" in sys.argv:
    importer.ensure_worker = lambda: None          # no worker in a test: the job is run here, the ones it queues are only looked at
    os.remove(os.path.join(paths.ROOT, r["films"][0]["file"])) if r["films"] else None
    for x in uploads.items()[before:]: uploads.remove(x["id"])
    j = importer.add_folder(folder.resolve(stuff), reading=True)
    importer.work(j)
    out["jobs"] = [{k: x.get(k) for k in ("type", "status", "slug", "from", "activity", "breakdown")} | {"src": os.path.basename(x["src"])} for x in importer.jobs()]
    other = os.path.join(os.path.dirname(stuff), "Other refs")                        # another folder, another film of the same name, while the first still waits:
    j2 = importer.add_folder(folder.resolve(other), reading=False); importer.work(j2)   # it must not ask for the name the first one holds
    out["again"] = [[x["slug"], os.path.basename(x["src"]), x["breakdown"]] for x in importer.jobs() if x.get("slug")]
    out["uploads_jobs"] = len([x for x in importer.jobs() if x.get("type") == "uploads"])
print(json.dumps(out))
'''


def run(test, stuff, *flags):
    root = support.project(test)
    r = subprocess.run([sys.executable, "-c", SCRIPT, support.TOOLS, stuff, *flags], env={**os.environ, "SPLICED_PROJECT": root}, capture_output=True, text=True)
    test.assertEqual(r.returncode, 0, r.stderr)
    return root, json.loads(r.stdout)


def a_folder(test):
    d = os.path.realpath(tempfile.mkdtemp(prefix="spliced-stuff-"))
    test.addCleanup(shutil.rmtree, d, ignore_errors=True)
    stuff = os.path.join(d, "My refs")
    for sub in ("posters", ".hidden", "Thing.app", "node_modules"):
        os.makedirs(os.path.join(stuff, sub))
    png(os.path.join(stuff, "posters", "Lime script.png"), (200, 240, 60))
    png(os.path.join(stuff, "posters", "dark-stage.png"), (20, 20, 24))
    png(os.path.join(stuff, "the same again.png"), (200, 240, 60))        # the first picture under another name
    for sub in (".hidden", "Thing.app", "node_modules"):                   # never looked into
        png(os.path.join(stuff, sub, "inside.png"), (1, 2, 3))
    png(os.path.join(stuff, ".hidden-file.png"), (3, 2, 1))
    with open(os.path.join(stuff, "notes.txt"), "w") as f:
        f.write("not a picture")
    return stuff


class Pictures(unittest.TestCase):
    def test_a_folder_of_pictures_comes_in_once(self):
        stuff = a_folder(self)
        root, d = run(self, stuff)
        lk = d["look"]
        self.assertEqual((lk["name"], lk["pictures"], lk["videos"], lk["other"]), ("My refs", 3, 0, 1), "hidden files, app bundles and node_modules are not looked into")
        self.assertEqual(sorted(lk["examples"]), ["posters/Lime script.png", "posters/dark-stage.png", "the same again.png"])
        self.assertEqual([bool(x) for x in d["refused"]], [True] * 4, "no such folder, the project's own library, and nothing at all are refused")
        self.assertIn("own library", d["refused"][1])
        first = d["first"]
        self.assertEqual((first["pictures"], first["clips"], first["films"], first["already"], first["left"]), (2, 0, [], 1, []), "the same picture under two names comes in once")
        self.assertEqual(sorted(x["title"] for x in d["added"]), ["Dark stage", "The same again"], "(of the twins, the one met first: the folder's own files, then its folders)")
        self.assertEqual({(x["kind"], x["by"]) for x in d["added"]}, {("image", "folder")})
        self.assertIn("folder: My refs/posters/dark-stage.png", [x["source"] for x in d["added"]], "each one says where it came from, without the path to the person's home")
        self.assertTrue(d["files_exist"])
        self.assertEqual(d["summary"], "Brought in 2 pictures; 1 was already in the library")
        self.assertEqual(d["said"], ["Looking at 1 of 3"])
        second = d["second"]
        self.assertEqual((second["pictures"], second["already"], d["count"]), (0, 3, 2), "running it again brings in nothing")
        self.assertEqual(d["second_summary"], "Nothing new to bring in; 3 were already in the library")
        self.assertEqual(sorted(os.listdir(os.path.join(stuff, "posters"))), ["Lime script.png", "dark-stage.png"], "the person's own folder is as it was")

    def test_the_command_line_looks_first(self):
        stuff = a_folder(self)
        root = support.project(self)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPLICED_", "CUTTING_ROOM_"))}
        cli = lambda *a: subprocess.run([sys.executable, os.path.join(support.TOOLS, "cli.py"), "--project", root, *a], env=env, capture_output=True, text=True)
        r = cli("import", stuff)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("3 pictures and GIFs, 0 videos", r.stdout)
        self.assertIn("Nothing has been brought in", r.stdout)
        self.assertIn("--go", r.stdout)
        self.assertEqual(json.loads(cli("import", stuff, "--json").stdout)["pictures"], 3)
        r = cli("import", os.path.join(stuff, "nope"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("there is no folder", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(root, ".cache", "imports")), "looking queues nothing")
        self.assertIn("usage", cli("import").stderr + cli("import").stdout)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class Videos(unittest.TestCase):
    def video(self, path, seconds):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=320x180:r=12:d={seconds}", "-pix_fmt", "yuv420p", path], check=True)

    def test_short_videos_are_clips_and_long_ones_films_with_a_job_each(self):
        stuff = a_folder(self)
        os.makedirs(os.path.join(stuff, "films"))
        self.video(os.path.join(stuff, "short loop.mp4"), 3)
        self.video(os.path.join(stuff, "films", "Brand film [x1].mp4"), 17)
        self.video(os.path.join(stuff, "films", "demo-one.mp4"), 16)            # a name the project's reference/ already has, for another film
        with open(os.path.join(stuff, "broken.mp4"), "w") as f:
            f.write("not a video")
        other = os.path.join(os.path.dirname(stuff), "Other refs")
        os.makedirs(other)
        self.video(os.path.join(other, "Brand film [x1].mp4"), 19)
        png(os.path.join(other, "one more.png"), (9, 9, 9))
        root, d = run(self, stuff, "--job")
        first = d["first"]
        self.assertEqual((first["pictures"], first["clips"], first["already"]), (2, 1, 1))
        self.assertEqual([(f["slug"], f["from"]) for f in first["films"]], [("brand-film", "folder: My refs/films/Brand film [x1].mp4"), ("demo-one-2", "folder: My refs/films/demo-one.mp4")],
                         "a film gets a slug from its name, and never one that is taken")
        self.assertEqual([f["file"] for f in first["films"]], ["reference/Brand film [x1].mp4", "reference/demo-one-2.mp4"], "copied into the project, beside and not over what is there")
        self.assertEqual(d["films_exist"], [True, True])
        self.assertEqual(first["left"], [["broken.mp4", "not a video this machine can read"]])
        self.assertEqual(d["summary"], "Brought in 2 pictures, 1 clip, 2 films; 1 was already in the library; 1 file left alone")
        self.assertEqual((d["second"]["films"], d["second"]["already"]), ([], 6))
        jobs = {j["type"] or j["src"]: j for j in d["jobs"]}
        self.assertEqual((jobs["folder"]["status"], jobs["folder"]["activity"]), ("done", "Brought in 2 pictures, 1 clip, 1 film; 2 were already in the library; 1 file left alone"),
                         "(the job ran after one film and the uploads were taken out again: the other film and the twin picture were still there)")
        film = next(j for j in d["jobs"] if j["slug"])
        self.assertEqual((film["status"], film["slug"], film["breakdown"]), ("queued", "brand-film", True), "each film is its own job in the queue")
        self.assertTrue(film["from"].startswith("folder: My refs/films/"))
        self.assertEqual(jobs["uploads"]["status"], "queued", "and the pictures and clips are one job to read")
        self.assertEqual(sorted(d["again"]), [["brand-film", "Brand film [x1].mp4", True], ["brand-film-2", "Brand film [x1]-2.mp4", False]],
                         "a name a waiting job holds is not given out twice, and its file is not written over")
        self.assertEqual(d["uploads_jobs"], 1, "no reading asked for the second folder: none queued for its picture")


if __name__ == "__main__":
    unittest.main()
