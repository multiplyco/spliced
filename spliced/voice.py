# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "librosa", "soundfile", "requests"]
# ///
"""A film's voice-over, line by line: record only what changed, keep every take, fit the film to the read.

The script is the storyboard: each beat's `vo` (the Build view's Script tab). The film's voice lines are cues.json
`film.voLines` (one clip each, placed on its beat) plus the bridge's `film.vo`. A line whose script text differs from what
was recorded is "changed"; `record` reads only those (or the ids you name), each with the line before it as context:
Kai reads the previous line first and it is cut away, so the new line keeps the script's tone and pace and never starts
soft. Every take is levelled to the same loudness, saved under audio/vo/<line>/, and added to takes.json, where the
Spliced's Sound panel (or `spliced film take-use`) picks one. `fit` then times the film to the chosen reads: on-screen
word timings follow the voice, the bridge's moments follow its phrases, and a line that no longer fits its beat is flagged.

  spliced voice status <slug>                     # every line: script vs recorded, takes, fits its beat?
  spliced voice record <slug> [line ...] [--takes 2] [--direction "crisp, clear"] [--dry-run]
  spliced voice record <slug> [line ...] --agent [--json]
                                                  # no key needed: the prompts, voice and model for your AI's own
                                                  # ElevenLabs connector, and the command that files each read
  spliced voice file <slug> <line> <audio> [<audio> ...] [--direction ..] [--plain] [--source <service | recording>]
                                                  # reads made that way: lead-in cut away, levelled, filed as takes
                                                  # (--plain: the file is the line alone, no lead-in)
  spliced voice fit <slug>                        # retime to the chosen takes, rebuild sound.json
  spliced voice take <slug> <line> <file>@<a>-<b> [<file>@<a>-<b> ...] --text ".." [--gap 0.42] [--use] [--note ..]
                                                          # a take from pieces of any recordings (a session read, the
                                                          # connector's files, a re-read of one sentence), joined with
                                                          # natural pauses, levelled and filed like a recorded take

`record` reads through ElevenLabs with ELEVENLABS_API_KEY in the project's .env; without a key, `record --agent` hands
the same prompts to your AI's ElevenLabs connector and `file` takes its reads in. Voice and model: cues.json `film.voice`
(default Kai, eleven_v4). Takes are recorded in the film's assets.json with their prompt and characters.

Any other voice works the same way from `file` on: another voice service your AI is connected to (spliced.json "voice":
{"provider": "<its name>", "name": "<the voice>"}), or a person reading into a microphone. Spliced doesn't call those
itself: `record --agent` lists the lines, your AI (or you) makes one audio file a line, and
`file <slug> <line> <audio> --plain [--source <where it came from>]` levels it and files it as a take. A film needs no
voice at all: with no "voice" set, its words are the ones on screen.
"""
import json, os, re, shutil, subprocess, sys, tempfile

import numpy as np, librosa, soundfile as sf

import paths

ROOT = paths.ROOT
REM = paths.REMOTION; PUB = paths.PUBLIC
SR = 44100
# The project's voice: spliced.json "voice": {"voice_id", "name", "model_id", "tone"}. A film's cues.json `film.voice` overrides any of it.
VOICE = dict(paths.CONFIG.get("voice") or {})
LUFS = -19.0


def film_paths(slug):
    d = os.path.join(REM, "src", "films", slug)
    if not os.path.isdir(d): sys.exit(f"no film {slug} in remotion/src/films")
    return d, os.path.join(d, "cues.json"), os.path.join(d, "storyboard.json"), os.path.join(d, "takes.json"), os.path.join(d, "assets.json")


def load(p, default=None):
    try: return json.load(open(p))
    except (OSError, ValueError): return default


def save(p, doc):
    json.dump(doc, open(p, "w"), indent=2, ensure_ascii=False); open(p, "a").write("\n")


def syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w: return 1
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1: n -= 1
    return max(1, n)


def speech_spans(path, thresh_db=-34, gap=0.12):
    """(start, end) of speech in a file, joined across pauses shorter than `gap`."""
    y, _ = librosa.load(path, sr=SR, mono=True)
    hop = 256; rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    on = 20 * np.log10(rms + 1e-9) > thresh_db
    t = librosa.frames_to_time(np.arange(len(on)), sr=SR, hop_length=hop)
    spans, s = [], None
    for i, v in enumerate(on):
        if v and s is None: s = t[i]
        if not v and s is not None: spans.append([s, t[i]]); s = None
    if s is not None: spans.append([s, t[-1]])
    out = []
    for a, b in spans:
        if out and a - out[-1][1] < gap: out[-1][1] = b
        else: out.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in out if b - a > 0.05]


# ---------- the lines ----------
def lines(slug):
    """Every voice line: id, track id, beat (storyboard id), at, file, recorded text, script text."""
    _, cp, sp, tp, _ = film_paths(slug)
    c = load(cp, {}) or {}
    if "film" not in c:   # a film whose cues.json has no voice-over section yet (or no cues.json)
        sys.exit(f"{slug} has no voice lines yet: its cues.json has no \"film\" section with voLines (remotion/docs/SOUND.md)")
    F = c["film"]; sb = load(sp, {"beats": []}); win = c.get("scenes", {})
    beat_at = lambda t: next((k for k, v in win.items() if isinstance(v, list) and len(v) == 2 and isinstance(v[0], (int, float)) and v[0] - 0.05 <= t < v[1] - 0.05), None)
    vo = {b["id"]: b.get("vo", "") for b in sb.get("beats", [])}
    out = []
    if F.get("vo", {}).get("src"):
        br = next(b for b in F["beats"] if b.get("kind") == "bridge")
        out.append({"id": "bridge", "track": "voice", "beat": br.get("storyboard"), "at": F["vo"]["at"], "file": F["vo"]["src"],
                    "recorded": F["vo"].get("text", br.get("sub", "")), "direction": F["vo"].get("direction")})
    for l in F.get("voLines", []):
        out.append({"id": l["id"], "track": f"voice-{l['id']}", "beat": l.get("beat") or beat_at(l["at"]), "at": l["at"], "file": l["src"],
                    "recorded": l.get("text", ""), "direction": l.get("direction")})
    out.sort(key=lambda x: x["at"])
    for x in out:
        x["script"] = (vo.get(x["beat"]) or "").strip() or x["recorded"]
        x["changed"] = norm(x["script"]) != norm(x["recorded"])
    takes = load(tp, {}).get("tracks", {})
    for x in out:
        tr = takes.get(x["track"], {}); x["takes"] = tr.get("takes", []); x["chosen"] = tr.get("chosen")
    return c, out


def norm(s):
    return re.sub(r"[^a-z0-9' ]", "", s.lower().replace("’", "'")).split()


# ---------- status ----------
def status(slug):
    c, ls = lines(slug); F = c["film"]
    beats = {b.get("storyboard"): b for b in F["beats"]}
    print(f"# {slug}: {len(ls)} voice lines ({sum(x['changed'] for x in ls)} changed in the script)\n")
    for x in ls:
        f = os.path.join(PUB, x["file"]); n = librosa.get_duration(path=f) if os.path.exists(f) else 0
        sp = speech_spans(f) if n else []
        end = x["at"] + (sp[-1][1] if sp else n)
        b = beats.get(x["beat"]) or {}
        over = end - (b.get("at", 0) + b.get("dur", 1e9)) if b else 0
        flag = "CHANGED" if x["changed"] else "ok"
        print(f"{x['id']:10} {x['at']:6.2f}s  beat {str(x['beat'])[:28]:28} [{flag}]  takes {len(x['takes'])}{' (chosen ' + x['chosen'] + ')' if x['chosen'] else ''}")
        print(f"           recorded: {x['recorded']}")
        if x["changed"]: print(f"           script:   {x['script']}")
        if over > 0.05: print(f"           ! runs {over:.2f}s past its beat")


# ---------- record ----------
def api_key():
    for line in open(os.path.join(ROOT, ".env")) if os.path.exists(os.path.join(ROOT, ".env")) else []:
        m = re.match(r"\s*ELEVENLABS_API_KEY\s*=\s*['\"]?([^'\"\s]+)", line)
        if m: return m.group(1)
    return os.environ.get("ELEVENLABS_API_KEY")


def tts(text, voice, seed):
    import requests
    key = api_key() or sys.exit("ELEVENLABS_API_KEY isn't set: add it to the project's .env, or use record --agent")
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice['voice_id']}", params={"output_format": "mp3_44100_128"},
                      headers={"xi-api-key": key, "content-type": "application/json"}, timeout=180,
                      json={"text": text, "model_id": voice["model_id"], "seed": seed})
    if r.status_code != 200: sys.exit(f"ElevenLabs said {r.status_code}: {r.text[:300]}")
    return r.content, r.headers.get("x-character-count") or r.headers.get("character-cost")


def prompt_for(x, prev, voice, direction):
    """The previous line (or a warm-up) first, then the line in its own direction; the lead-in is cut away after."""
    lead = re.split(r"(?<=[.?!])\s+", prev.strip())[-1] if prev else "Here's the thing."   # the last sentence is enough context
    d = direction or x.get("direction") or voice["tone"]
    return f"[{voice['tone']}] {lead} ... [{d}] {x['script']}", lead


def cut_lead(src, lead, line, out):
    """Keep only the line: drop everything up to the pause that ends the lead-in (the silence nearest where the lead's
    share of the text predicts it), trim to the speech with 40 ms before and 140 ms after, fade, level to LUFS."""
    y, _ = librosa.load(src, sr=SR, mono=True); dur = len(y) / SR
    sp = speech_spans(src, gap=0.25)
    if len(sp) < 2: sys.exit(f"couldn't find the line after the lead-in in {src}")
    expect = dur * len(lead) / (len(lead) + len(line) + 6)
    gaps = [(sp[i][1], sp[i + 1][0]) for i in range(len(sp) - 1)]
    a = min(gaps, key=lambda g: abs((g[0] + g[1]) / 2 - expect) - (g[1] - g[0]))[1]
    b = sp[-1][1]
    seg = y[int(max(0, a - 0.04) * SR): int(min(dur, b + 0.14) * SR)].copy()
    fi, fo = int(0.015 * SR), int(0.06 * SR)
    seg[:fi] *= np.linspace(0, 1, fi); seg[-fo:] *= np.linspace(1, 0, fo)
    tmp = out + ".raw.wav"; sf.write(tmp, seg, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", f"loudnorm=I={LUFS}:TP=-1.5:LRA=7", "-ar", str(SR), "-ac", "1", out], check=True)
    os.remove(tmp)
    return round(len(seg) / SR, 3)


def clarity(path):
    """Share of energy above 3 kHz: higher reads crisper. Printed per take so the person can compare."""
    y, _ = librosa.load(path, sr=SR, mono=True)
    S = np.abs(librosa.stft(y)) ** 2; f = librosa.fft_frequencies(sr=SR)
    return float(S[f > 3000].sum() / (S.sum() + 1e-9))


PROVIDERS = {"elevenlabs": "ElevenLabs"}   # the one Spliced can call itself; any other name is a service your AI reaches, or "recording"


def provider_name(voice):
    p = str(voice.get("provider") or "elevenlabs").strip()
    return PROVIDERS.get(p.lower(), p)


def _voice(c):
    voice = {**VOICE, **c["film"].get("voice", {})}
    voice["provider"] = str(voice.get("provider") or "elevenlabs").strip().lower()
    if voice["provider"] == "elevenlabs" and not voice.get("voice_id"):
        sys.exit('No voice is set: add "voice": {"voice_id": "...", "name": "...", "model_id": "..."} to spliced.json, or film.voice to this film\'s cues.json.\n'
                 'With another voice service, or your own recording: "voice": {"provider": "<its name, or recording>", "name": "<the voice>"}')
    voice.setdefault("voice_id", ""); voice.setdefault("model_id", "")
    voice.setdefault("tone", "natural"); voice.setdefault("name", voice["voice_id"] or provider_name(voice))
    return voice


def _file_read(slug, x, raw, lead, n, meta):
    """One read of line x (a file that starts with the lead-in, unless lead is None): cut the lead away, level it,
    add it to takes.json and assets.json as take n. Returns the take."""
    d, cp, sp, tp, ap = film_paths(slug)
    folder = os.path.join(PUB, "films", slug, "audio", "vo", x["id"]); os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, f"{x['id']}-{n}.wav")
    if lead is None:   # a plain read: trim to the speech and level it, like a take built from one piece
        y, _ = librosa.load(raw, sr=SR, mono=True); sp_ = speech_spans(raw) or [(0, len(y) / SR)]
        a, b = sp_[0][0], sp_[-1][1]
        seg = y[int(max(0, a - 0.04) * SR): int(min(len(y) / SR, b + 0.14) * SR)].copy()
        fi, fo = int(0.015 * SR), int(0.06 * SR); seg[:fi] *= np.linspace(0, 1, fi); seg[-fo:] *= np.linspace(1, 0, fo)
        tmp = out + ".raw.wav"; sf.write(tmp, seg, SR)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", f"loudnorm=I={LUFS}:TP=-1.5:LRA=7", "-ar", str(SR), "-ac", "1", out], check=True)
        os.remove(tmp); dur = round(len(seg) / SR, 3)
    else:
        dur = cut_lead(raw, lead, x["script"], out)
    cl = clarity(out)
    takes = load(tp, {"_note": "Alternatives for the film's sound tracks, keyed by sound.json track id; `chosen` is what plays.", "tracks": {}})
    tr = takes["tracks"].setdefault(x["track"], {"label": x["script"], "chosen": "", "takes": []})
    tid = f"{x['id']}-{n}"
    t = {"id": tid, "name": f"{x['script']} (take {n})", "file": os.path.relpath(out, ROOT), "dur": dur, "text": x["script"],
         "note": f"clarity {cl:.3f}" + (f"; read after: {lead}" if lead else "")}
    tr["takes"] = [o for o in tr["takes"] if o["id"] != tid] + [t]
    save(tp, takes)
    assets = load(ap, {}); assets[os.path.relpath(out, PUB)] = meta; save(ap, assets)
    print(f"  take {n}: {dur:.2f}s  clarity {cl:.3f}  -> {t['file']}")
    return t


def _choose(slug, x, new):
    """The crisper of the new reads plays; the person can pick another in the Sound panel."""
    d, cp, sp, tp, ap = film_paths(slug)
    takes = load(tp, {}); tr = takes["tracks"][x["track"]]
    best = max(new, key=lambda t: float(re.search(r"clarity ([\d.]+)", t["note"]).group(1)))
    tr["chosen"] = best["id"]; tr["label"] = x["script"]; save(tp, takes)
    print(f"  chosen: {best['id']} (the crisper read; pick another in the Sound panel or with {paths.CLI} film take-use)")


def _next_take(slug, x):
    d, cp, sp, tp, ap = film_paths(slug)
    tr = (load(tp, {}) or {}).get("tracks", {}).get(x["track"], {})
    return max([int(m.group(1)) for t in tr.get("takes", []) for m in [re.search(r"-(\d+)$", t["id"])] if m], default=0) + 1


def record(slug, ids, n_takes=2, direction=None, dry=False, agent=False, as_json=False):
    c, ls = lines(slug); voice = _voice(c); as_json = as_json and agent   # --json is the agent's hand-off, for the MCP tool
    todo = [x for x in ls if (x["id"] in ids if ids else x["changed"])]
    if not todo:
        if as_json: return print(json.dumps({"slug": slug, "lines": []}))
        print(f"Nothing changed in the script. Name lines to re-record them: {paths.CLI} voice record <slug> <line> ..."); return
    if voice["provider"] != "elevenlabs" and not (dry or agent):
        sys.exit(f"Spliced records through ElevenLabs itself. This project's voice is {provider_name(voice)}: list the lines with\n"
                 f"  {paths.CLI} voice record {slug}{' ' + ' '.join(ids) if ids else ''} --agent\nmake one audio file a line, and file each with {paths.CLI} voice file {slug} <line> <audio> --plain")
    if not (dry or agent or api_key()):
        sys.exit(f"ELEVENLABS_API_KEY isn't set in this project's .env.\n"
                 f"Without one, your AI can read the lines with its own ElevenLabs connector: {paths.CLI} voice record {slug}{' ' + ' '.join(ids) if ids else ''} --agent")
    jobs = []
    for x in todo:
        i = ls.index(x); prev = ls[i - 1]["script"] if i > 0 else None
        text, lead = prompt_for(x, prev, voice, direction)
        other = voice["provider"] != "elevenlabs"   # the prompt's tone tags and lead-in are ElevenLabs': another voice reads the line alone
        jobs.append({"line": x["id"], "script": x["script"], "prompt": x["script"] if other else text, "lead_in": "" if other else lead,
                     "then": f"{paths.CLI} voice file {slug} {x['id']} <audio file> [<audio file> ...]" + (f" --plain --source {voice['provider']}" if other else "")
                             + (f' --direction "{direction}"' if direction else "")})
        if as_json: continue
        print(f"\n{x['id']}: {x['script']}\n  prompt: {jobs[-1]['prompt']}")
        if agent: print(f"  then:   {jobs[-1]['then']}")
    if agent:
        if as_json:
            return print(json.dumps({"slug": slug, "provider": voice["provider"], "voice_id": voice["voice_id"], "voice": voice["name"], "model_id": voice["model_id"],
                                     "tone": voice.get("tone", ""), "takes": n_takes, "lines": jobs}, indent=1))
        if voice["provider"] != "elevenlabs":
            print(f"\nRead each line above with {provider_name(voice)} (voice: {voice['name']}; tone: {voice.get('tone', 'natural')}), the words exactly as"
                  f"\nwritten and nothing before or after them, {n_takes} take{'s' if n_takes != 1 else ''} a line. Save each read as a file, then file"
                  f"\nthe line's reads with the `then` command. After the last: {paths.CLI} voice fit {slug}")
            return
        print(f"\nRead each prompt above with your ElevenLabs connector, exactly as written (the [tone] tags direct it, and the"
              f"\nlead-in before the line is cut away when it is filed): voice {voice['name']} ({voice['voice_id']}),"
              f" model {voice['model_id']}, {n_takes} take{'s' if n_takes != 1 else ''} a line."
              f"\nDownload each read, then file the line's reads with the `then` command. After the last: {paths.CLI} voice fit {slug}")
        return
    if dry: return
    for x, job in zip(todo, jobs):
        n0 = _next_take(slug, x); new = []
        print(f"\n{x['id']}:")
        for k in range(n_takes):
            seed = 1000 + n0 + k
            audio, chars = tts(job["prompt"], voice, seed)
            folder = os.path.join(PUB, "films", slug, "audio", "vo", x["id"]); os.makedirs(folder, exist_ok=True)
            raw = os.path.join(folder, f"{x['id']}-{n0 + k}-raw.mp3"); open(raw, "wb").write(audio)
            new.append(_file_read(slug, x, raw, job["lead_in"], n0 + k, {
                "source": "elevenlabs", "model": voice["model_id"], "voice": f"{voice['name']} ({voice['voice_id']})",
                "prompt": job["prompt"], "characters": chars, "seed": seed, "note": "voice.py: lead-in cut, levelled to %.0f LUFS" % LUFS}))
        _choose(slug, x, new)
    print(f"\nNow: {paths.CLI} voice fit {slug}")


# ---------- file: reads your AI made with its own connector ----------
def file_reads(slug, line_id, files, direction=None, plain=False, source=None):
    """File reads of one line made elsewhere (your AI's ElevenLabs connector) from the prompt `record --agent` gave:
    the lead-in is cut away (unless plain: the file is the line alone), each is levelled and becomes a take."""
    c, ls = lines(slug); voice = _voice(c)
    x = next((l for l in ls if l["id"] == line_id), None) or sys.exit(f"no line {line_id} ({paths.CLI} voice status {slug})")
    i = ls.index(x); prev = ls[i - 1]["script"] if i > 0 else None
    text, lead = prompt_for(x, prev, voice, direction)
    folder = os.path.join(PUB, "films", slug, "audio", "vo", x["id"]); os.makedirs(folder, exist_ok=True)
    n0 = _next_take(slug, x); new = []
    print(f"{x['id']}: {x['script']}")
    for k, f in enumerate(files):
        if not os.path.isfile(f): sys.exit(f"no file {f}")
        raw = os.path.join(folder, f"{x['id']}-{n0 + k}-raw{os.path.splitext(f)[1] or '.mp3'}")
        if os.path.abspath(f) != raw: shutil.copyfile(f, raw)
        src = str(source or voice["provider"]).strip().lower()
        new.append(_file_read(slug, x, raw, None if plain else lead, n0 + k, {
            "source": src, "via": "recorded by a person" if src == "recording" else f"your AI's {PROVIDERS.get(src, src)} connector", "model": voice["model_id"],
            "voice": f"{voice['name']} ({voice['voice_id']})" if voice["voice_id"] else voice["name"], "prompt": x["script"] if plain else text,
            "note": "voice.py file: " + ("levelled" if plain else "lead-in cut, levelled") + " to %.0f LUFS" % LUFS}))
    _choose(slug, x, new)
    print(f"\nWhen every line is in: {paths.CLI} voice fit {slug}")


# ---------- take: build one from pieces ----------
def take(slug, line_id, pieces, text, gap=0.42, use=False, note=""):
    """Join speech spans from any files into one take of `line_id` (pieces: (file, a, b) in seconds), each trimmed to
    40 ms before and 140 ms after its speech with short fades, `gap` seconds of silence between, levelled to LUFS."""
    d, cp, sp, tp, ap = film_paths(slug)
    c, ls = lines(slug); x = next((l for l in ls if l["id"] == line_id), None) or sys.exit(f"no line {line_id}")
    parts = []
    for i, (f, a, b) in enumerate(pieces):
        y, _ = librosa.load(f, sr=SR, mono=True)
        seg = y[int(max(0, a - 0.04) * SR): int(min(len(y) / SR, b + 0.14) * SR)].copy()
        fi, fo = int(0.012 * SR), int(0.05 * SR); seg[:fi] *= np.linspace(0, 1, fi); seg[-fo:] *= np.linspace(1, 0, fo)
        rms = np.sqrt(np.mean(seg ** 2)) + 1e-9; parts.append(seg / rms * 0.05)     # match the pieces to each other first
        if i < len(pieces) - 1: parts.append(np.zeros(int(max(0.0, gap - 0.18) * SR)))
    takes = load(tp, {"_note": "Alternatives for the film's sound tracks, keyed by sound.json track id; `chosen` is what plays.", "tracks": {}})
    tr = takes["tracks"].setdefault(x["track"], {"label": text, "chosen": "", "takes": []})
    k = len(tr["takes"]) + 1; tid = f"{line_id}-{k}"
    folder = os.path.join(PUB, "films", slug, "audio", "vo", line_id); os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, f"{tid}.wav"); tmp = out + ".raw.wav"; sf.write(tmp, np.concatenate(parts), SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", f"loudnorm=I={LUFS}:TP=-1.5:LRA=7", "-ar", str(SR), "-ac", "1", out], check=True)
    os.remove(tmp)
    dur = round(librosa.get_duration(path=out), 3); cl = clarity(out)
    src = ", ".join(f"{os.path.basename(f)}@{a:.2f}-{b:.2f}" for f, a, b in pieces)
    tr["takes"].append({"id": tid, "name": f"{text} (take {k})", "file": os.path.relpath(out, ROOT), "dur": dur, "text": text,
                        "note": f"clarity {cl:.3f}; from {src}" + (f"; {note}" if note else "")})
    if use or not tr.get("chosen"): tr["chosen"] = tid
    tr["label"] = text
    assets = load(ap, {}); assets[os.path.relpath(out, PUB)] = {"source": "elevenlabs", "voice": "Kai", "prompt": text, "note": f"voice.py take: {src}" + (f"; {note}" if note else "")}
    save(tp, takes); save(ap, assets)
    print(f"{tid}: {dur:.2f}s clarity {cl:.3f}{'  (chosen)' if tr['chosen'] == tid else ''}  <- {src}")
    return tid


# ---------- fit ----------
def fit(slug):
    """Point every line at its chosen take, retime what the film shows to the reads, rebuild sound.json."""
    d, cp, sp, tp, _ = film_paths(slug)
    c, ls = lines(slug); F = c["film"]; takes = load(tp, {}).get("tracks", {})
    beats = {b.get("storyboard"): b for b in F["beats"]}
    for x in ls:
        tr = takes.get(x["track"]); t = next((t for t in (tr or {}).get("takes", []) if t["id"] == (tr or {}).get("chosen")), None)
        if not t: continue
        rel = os.path.relpath(os.path.join(ROOT, t["file"]), PUB); text = t.get("text", x["script"])
        if x["id"] == "bridge": F["vo"].update(src=rel, text=text)
        else:
            l = next(l for l in F["voLines"] if l["id"] == x["id"]); l.update(src=rel, text=text); l["beat"] = x["beat"]
        x["file"], x["recorded"] = rel, text
    save(cp, c)
    # the bridge: its moments follow the read's phrases (score_sketch.py voice), "the joy of the work" its last words
    br_line = next((x for x in ls if x["id"] == "bridge"), None)
    env = {**os.environ, "FILM": slug}
    if br_line:
        subprocess.run(["uv", "run", os.path.join(REM, "scripts", "score_sketch.py"), "voice", os.path.join(PUB, br_line["file"])], check=True, env=env)
        c = load(cp); F = c["film"]; beats = {b.get("storyboard"): b for b in F["beats"]}
        br = next(b for b in F["beats"] if b.get("kind") == "bridge")
        if br.get("joyWords"):
            spans = speech_spans(os.path.join(PUB, br_line["file"]), gap=0.3)
            a, e = spans[-1]; words = br_line["recorded"].split(". ")[-1].split()
            times = word_times(words, a, e - a, F["vo"]["at"] - br["at"])
            jw = [w.strip(".,").lower() for w in words]
            k = len(jw) - 5
            if jw[k:] == ["the", "joy", "of", "the", "work"]:
                br["joyWords"] = [[w, times[k + i]] for i, w in enumerate(["the", "joy", "of", "the", "work"])]
                j = dict(zip(["the", "joy", "of", "the2", "work"], [t for _, t in br["joyWords"]]))
                if br.get("joyLine"):
                    br["joyLine"].update(soften=round(j["the"] - 0.16, 2), paint=[round(j["joy"] - 0.05, 2), br["joyLine"]["paint"][1]],
                                         rays=round(j["joy"] + 0.24, 2), cursor=round(j["work"] - 0.33, 2), ripple=round(j["work"] + 0.15, 2))
        br["sub"] = br_line["recorded"]
    # every other line: its beat's on-screen words land on the read
    for x in ls:
        if x["id"] == "bridge": continue
        b = beats.get(x["beat"]); f = os.path.join(PUB, x["file"])
        if not b or not os.path.exists(f): continue
        sp_ = speech_spans(f); a, e = sp_[0][0], sp_[-1][1]
        shown = (b.get("copyText") or b.get("line") or " ".join(b.get("copy") or [])).replace(" / ", " ").split()
        if not shown or b.get("kind") == "opening": continue
        rel_beat = "copyText" in b                       # chapter lines time words from the beat; think/ideas use film time
        base = x["at"] - (b["at"] if rel_beat else 0)
        b["wordTimes"] = word_times(shown, a, e - a, base)
        if norm(" ".join(shown)) != norm(x["recorded"]): print(f"  note: {x['beat']} shows '{' '.join(shown)}' while the voice says '{x['recorded']}'")
    save(cp, c)
    subprocess.run(["uv", "run", os.path.join(REM, "scripts", "score_sketch.py"), "sound"], check=True, env=env)
    # the script tab: what's recorded is what's planned
    sb = load(sp)
    for x in ls:
        for b in sb.get("beats", []):
            if b["id"] == x["beat"] and not b.get("vo"): b["vo"] = x["recorded"]
    save(sp, sb)
    status(slug)


def word_times(words, start, dur, base):
    """Each word's onset: the read's speech span shared out by syllables, offset into the beat (or the film)."""
    syl = [syllables(w) for w in words]; per = dur / max(1, sum(syl)); t, out = 0, []
    for s in syl: out.append(round(base + start + t * per, 3)); t += s
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    cmd, slug, rest = a[0], a[1], a[2:]
    opt = lambda k, d=None: rest[rest.index(k) + 1] if k in rest else d
    VALUED = {"--takes", "--direction", "--text", "--gap", "--note", "--source"}
    ids = [x for i, x in enumerate(rest) if not x.startswith("--") and (i == 0 or rest[i - 1] not in VALUED)]
    if cmd == "status": status(slug)
    elif cmd == "record": record(slug, ids, int(opt("--takes", 2)), opt("--direction"), "--dry-run" in rest, "--agent" in rest, "--json" in rest)
    elif cmd == "file":
        if len(ids) < 2: sys.exit(f"usage: {paths.CLI} voice file <slug> <line> <audio> [<audio> ...]")
        file_reads(slug, ids[0], [os.path.abspath(f) for f in ids[1:]], opt("--direction"), "--plain" in rest, opt("--source"))
    elif cmd == "fit": fit(slug)
    elif cmd == "take":
        ps = []
        for r in ids[1:]:
            f, rng = r.rsplit("@", 1); a, b = (float(v) for v in rng.split("-")); ps.append((os.path.abspath(f), a, b))
        take(slug, ids[0], ps, opt("--text") or sys.exit("--text is the line's words"), float(opt("--gap", 0.42)), "--use" in rest, opt("--note", ""))
    else: sys.exit(__doc__)
