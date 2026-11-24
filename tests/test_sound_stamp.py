"""The Build view polls a film's sound_stamp and reloads its Sound panel when the sound is written again (film.py)."""
import json, os, subprocess, sys, time, unittest

import support

SCRIPT = r'''
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
import film
src = os.path.join(film.FILMS_DIR, "demo")
out = {"none": film.production("demo")["sound_stamp"]}
with open(os.path.join(src, "sound.json"), "w") as f: json.dump({"tracks": []}, f)
a = film.production("demo")["sound_stamp"]
out["written"] = bool(a); out["same"] = film.production("demo")["sound_stamp"] == a
time.sleep(0.02)
with open(os.path.join(src, "sound.json"), "w") as f: json.dump({"tracks": [{"id": "x", "lane": "sfx", "file": "remotion/x.wav", "start": 1}]}, f)
out["changed"] = film.production("demo")["sound_stamp"] != a
print(json.dumps(out))
'''


class SoundStamp(unittest.TestCase):
    def test_the_stamp_changes_when_the_sound_is_written_again(self):
        root = support.project(self)
        r = subprocess.run([sys.executable, "-c", SCRIPT, support.TOOLS], env={**os.environ, "SPLICED_PROJECT": root}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["none"], "", "no sound.json yet: an empty stamp")
        self.assertTrue(d["written"] and d["same"], "a stamp once written, the same while nothing changes")
        self.assertTrue(d["changed"], "sound.json written again: a new stamp, so the open Build view reads the sound again")


if __name__ == "__main__":
    unittest.main()
