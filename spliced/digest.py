# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf", "pillow", "numpy"]
# ///
"""A profile's sources, digested once so an agent never has to open them: profiles/<slug>/digest/.

A brand book read as page images costs an agent tens of thousands of tokens, and the work it then does by hand
(pulling the pictures out, merging their masks, measuring where a product sits in its photo, finding a device's
screen, reading colours out of a JSON file) is the same every time. This does it, deterministically:

  a PDF        pages/<name>.md, the text of every page; sheets/<name>.jpg, every page on one small contact sheet
               (numbered); images/<name>-pNN-K.*, every picture in it above a size, taken once (the same picture
               on ten pages is one file), a soft mask merged into an alpha PNG
  an image     (from a PDF, or a source itself) its pixel size; a crude kind: cutout (alpha, or a subject on near
               white), photo, or backdrop (a heavily blurred picture, very little detail); the subject's box inside
               it as fractions and its centre (to frame it: object-position, zoom); for a device on a cut-out, the
               rectangle of a uniform screen when one is found; its main colours
  SVG          an .svg source, and every SVG data URI or inline <svg> in a JSON or HTML source, written to logos/
               with scripts, foreign objects, event handlers and outside links taken out
  JSON / HTML  any shape, no vendor format assumed: hex colours with the keys that hold them, font families,
               objects that look like products (a title or name, a price and an image URL), image URLs
  a film       sheets/<name>.jpg, twelve frames on one sheet (when ffmpeg is here)

index.json is all of it for a program; README.md the short version for an agent. Paths in both are relative to the
profile's folder. It is rebuilt only when the sources change (their content hash).

Nothing is downloaded unless asked: --fetch fetches the image URLs the JSON and HTML sources list, once each, into
fetched/ (and measures them like any picture). That is the one time this goes online.

usage:
  spliced profile digest <profile> [--fetch] [--force]
"""
import base64, hashlib, io, json, os, re, shutil, subprocess, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import profiles

VERSION = 1
MIN_SIDE, MIN_AREA = 96, 160 * 160          # a picture smaller than this is a bullet, a rule or an icon: left out
SHEET_MAX = 240 * 1024                       # a contact sheet stays under this
FETCH_MAX, FETCH_BYTES = 80, 15 * 1024 * 1024
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm")
GENERIC_FONTS = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace",
                 "ui-rounded", "-apple-system", "blinkmacsystemfont", "emoji", "math", "fangsong", "inherit", "initial", "unset", "none",
                 "apple color emoji", "segoe ui emoji", "segoe ui symbol", "noto color emoji"}
SVG_NS, XLINK_NS = "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _safe(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")[:60] or "source"


def source_files(folder):
    d = os.path.join(folder, "sources")
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, n) for n in sorted(os.listdir(d)) if not n.startswith(".") and os.path.isfile(os.path.join(d, n))]


stamp = profiles.digest_stamp   # names, sizes, times: whether a digest looks current, without reading the files


def content_hash(files):
    h = hashlib.sha256(f"v{VERSION}".encode())
    for f in files:
        h.update(os.path.basename(f).encode() + b"\0")
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()[:24]


# ---------- pictures ----------
def look(im):
    """What a picture is: size, kind, the subject's box and centre, a device's screen, its main colours."""
    import numpy as np
    from PIL import Image
    w, h = im.size
    rgba = im.convert("RGBA")
    k = min(1.0, 400 / max(w, h))
    small = rgba.resize((max(1, round(w * k)), max(1, round(h * k))), Image.BILINEAR) if k < 1 else rgba
    s = np.asarray(small).astype(np.int16)
    alpha, rgb = s[..., 3], s[..., :3]
    sh, sw = alpha.shape
    clear = alpha < 250
    has_alpha = bool(clear.mean() > 0.02)
    b = max(1, round(min(sh, sw) * 0.03))
    ring = np.zeros_like(clear)
    ring[:b, :], ring[-b:, :], ring[:, :b], ring[:, -b:] = True, True, True, True
    white = (rgb.min(axis=2) > 235) | (alpha < 16)
    on_white = bool(white[ring].mean() > 0.9)
    subject = None
    if has_alpha and (alpha[ring] < 16).mean() > 0.5:
        subject = alpha > 16
    elif on_white:
        subject = (rgb.min(axis=2) < 228) & (alpha >= 16)
    # detail: how much neighbouring pixels differ, on a 256-pixel copy (a blurred backdrop has almost none)
    g = np.asarray(rgba.convert("L").resize((max(1, round(w * 256 / max(w, h))), max(1, round(h * 256 / max(w, h)))), Image.BILINEAR)).astype(np.float32)
    detail = float((np.abs(np.diff(g, axis=1)).mean() + np.abs(np.diff(g, axis=0)).mean()) / 2) if g.size > 4 else 0.0
    out = {"w": w, "h": h, "alpha": has_alpha, "detail": round(detail, 2)}
    box = _box(subject) if subject is not None else None
    if box and 0.01 < box[2] * box[3] < 0.95:
        out["kind"] = "cutout"
        out["subject"] = [round(v, 3) for v in box]
        out["focus"] = [round(box[0] + box[2] / 2, 3), round(box[1] + box[3] / 2, 3)]
        scr = screen(rgba, box)
        if scr:
            out["screen"] = scr
    elif detail < 2.2:
        out["kind"] = "backdrop"
    else:
        out["kind"] = "photo"
    out["colours"] = colours(small, subject if out["kind"] == "cutout" else None)
    return out


def _box(mask):
    """The box of a mask's pixels as fractions [x, y, w, h], ignoring stray rows and columns (under 0.5% lit)."""
    import numpy as np
    sh, sw = mask.shape
    cols = np.where(mask.sum(axis=0) > max(1, sh * 0.005))[0]
    rows = np.where(mask.sum(axis=1) > max(1, sw * 0.005))[0]
    if not len(cols) or not len(rows):
        return None
    return [cols[0] / sw, rows[0] / sh, (cols[-1] - cols[0] + 1) / sw, (rows[-1] - rows[0] + 1) / sh]


def screen(rgba, box):
    """A device's screen on a cut-out: a large uniform region inside the subject that fills its own rectangle. Grown
    from a few seeds around the subject's centre on a small copy, the biggest clean rectangle wins, and its edges are
    then found on the full picture. Pixels of the full image, or None."""
    import numpy as np
    from PIL import Image
    w, h = rgba.size
    full = np.asarray(rgba).astype(np.int16)
    k = min(1.0, 240 / max(w, h))
    small = np.asarray(rgba.resize((max(1, round(w * k)), max(1, round(h * k))), Image.BILINEAR)).astype(np.int16) if k < 1 else full
    H, W = small.shape[:2]
    bx, by, bw, bh = box[0] * W, box[1] * H, box[2] * W, box[3] * H
    best = None
    for fx, fy in ((0.5, 0.5), (0.5, 0.35), (0.5, 0.65), (0.35, 0.5), (0.65, 0.5)):
        x, y = int(bx + bw * fx), int(by + bh * fy)
        if not (0 <= x < W and 0 <= y < H) or small[y, x, 3] < 128:
            continue
        seed = small[y, x, :3]
        like = (np.abs(small[..., :3] - seed).sum(axis=2) <= 30) & (small[..., 3] >= 128)
        region = np.zeros_like(like)
        region[y, x] = True
        for _ in range(W + H):   # grow the region through like pixels until it stops
            grown = region.copy()
            grown[1:] |= region[:-1]; grown[:-1] |= region[1:]; grown[:, 1:] |= region[:, :-1]; grown[:, :-1] |= region[:, 1:]
            grown &= like
            if grown.sum() == region.sum():
                break
            region = grown
        ys, xs = np.where(region)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        rw, rh = x1 - x0 + 1, y1 - y0 + 1
        fill = region.sum() / (rw * rh)
        inside = x0 > bx and y0 > by and x1 < bx + bw - 1 and y1 < by + bh - 1
        share = rw * rh / max(1, bw * bh)
        if fill > 0.9 and inside and 0.12 < share < 0.9 and (not best or rw * rh > best[2] * best[3]):
            best = (x0, y0, rw, rh, small[region][:, :3].mean(axis=0))
    if not best:
        return None
    # the edges, exactly: on the full picture, where the screen's colour stops along the middle of each side
    x0, y0, x1, y1 = best[0] / k, best[1] / k, (best[0] + best[2]) / k, (best[1] + best[3]) / k
    like = (np.abs(full[..., :3] - best[4]).sum(axis=2) <= 36) & (full[..., 3] >= 128)
    pad = int(2 / k) + 2
    rows = slice(int(y0 + (y1 - y0) * 0.25), int(y0 + (y1 - y0) * 0.75) + 1)
    cols = slice(int(x0 + (x1 - x0) * 0.25), int(x0 + (x1 - x0) * 0.75) + 1)
    colfrac, rowfrac = like[rows, :].mean(axis=0), like[:, cols].mean(axis=1)

    def edge(frac, start, stop, step):
        for i in range(start, stop, step):
            if 0 <= i < len(frac) and frac[i] > 0.5:
                return i
        return None
    L = edge(colfrac, int(x0) - pad, int(x0) + pad, 1)
    R = edge(colfrac, int(x1) + pad, int(x1) - pad, -1)
    T = edge(rowfrac, int(y0) - pad, int(y0) + pad, 1)
    B = edge(rowfrac, int(y1) + pad, int(y1) - pad, -1)
    if None in (L, R, T, B) or R <= L or B <= T:
        return {"x": round(x0), "y": round(y0), "w": round(x1 - x0), "h": round(y1 - y0)}
    return {"x": int(L), "y": int(T), "w": int(R - L + 1), "h": int(B - T + 1)}


def colours(small, mask=None, n=5):
    """The main colours: [{hex, share}], from the subject's pixels on a cut-out, else the whole picture."""
    import numpy as np
    from PIL import Image
    a = np.asarray(small.convert("RGBA"))
    keep = a[..., 3] > 128
    if mask is not None:
        keep &= mask
    px = a[keep][:, :3]
    if not len(px):
        return []
    strip = Image.fromarray(px.reshape(1, -1, 3).astype("uint8"), "RGB")
    q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal, total = q.getpalette(), len(px)
    out = []
    for count, idx in sorted(q.getcolors() or [], reverse=True):
        r, g, b = pal[idx * 3: idx * 3 + 3]
        if count / total >= 0.03:
            out.append({"hex": f"#{r:02X}{g:02X}{b:02X}", "share": round(count / total, 2)})
    return out


# ---------- documents ----------
def pdf(path, name, out, idx, seen):
    import pymupdf as fitz
    from PIL import Image
    doc = fitz.open(path)
    stem = _safe(os.path.splitext(name)[0])
    text = [f"# {name}: {doc.page_count} pages", ""]
    for i, page in enumerate(doc, 1):
        t = page.get_text("text").strip()
        text += [f"## Page {i}", "", t or "(no text on this page: a picture)", ""]
    _put(out, f"pages/{stem}.md", "\n".join(text).encode())
    entry = {"source": f"sources/{name}", "kind": "pdf", "pages": doc.page_count, "text": f"digest/pages/{stem}.md",
             "sheet": f"digest/sheets/{stem}.jpg", "images": []}
    _put(out, f"sheets/{stem}.jpg", sheet([_page_image(p, 360) for p in doc], [f"p{i}" for i in range(1, doc.page_count + 1)]))
    done = {}
    for pno, page in enumerate(doc, 1):
        n_on_page = 0
        for info in page.get_images(full=True):
            xref, smask, w, h = info[0], info[1], info[2], info[3]
            if min(w, h) < MIN_SIDE or w * h < MIN_AREA:
                continue
            if xref in done:
                if pno not in done[xref]["pages"]:
                    done[xref]["pages"].append(pno)
                continue
            try:
                raw = doc.extract_image(xref)
                data = raw["image"]
                key = _sha(data + (doc.xref_stream_raw(smask) if smask else b""))
            except Exception:   # noqa: BLE001  (a picture PyMuPDF can't decode is left out)
                continue
            if key in seen:
                done[xref] = seen[key]
                if pno not in seen[key]["pages"]:
                    seen[key]["pages"].append(pno)
                continue
            try:
                im = _decode(doc, xref, smask)
            except Exception:   # noqa: BLE001
                continue
            n_on_page += 1
            base = f"images/{stem}-p{pno:02d}-{n_on_page}"
            if im.mode == "RGBA":
                rel, blob = base + ".png", _png(im)
            elif raw.get("ext") in ("jpeg", "jpg") and raw.get("colorspace") in (1, 3) and im.mode in ("RGB", "L"):
                rel, blob = base + ".jpg", data   # the JPEG as it was: no second compression
            elif _photo_like(im):
                rel, blob = base + ".jpg", _jpg(im)
            else:
                rel, blob = base + ".png", _png(im)
            _put(out, rel, blob)
            img = {"path": f"digest/{rel}", "from": f"sources/{name}", "pages": [pno], **({"mask": "merged into alpha"} if smask else {}), **look(im)}
            idx["images"].append(img)
            entry["images"].append(img["path"])
            seen[key] = done[xref] = img
    idx["documents"].append(entry)


def _page_image(page, width):
    import pymupdf as fitz
    from PIL import Image
    z = width / max(1, page.rect.width)
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _decode(doc, xref, smask):
    """A PDF picture as a Pillow image: RGB (CMYK and others converted), with its soft mask as alpha when it has one."""
    import pymupdf as fitz
    from PIL import Image
    pix = fitz.Pixmap(doc, xref)
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    if pix.n not in (1, 3):
        pix = fitz.Pixmap(fitz.csRGB, pix)
    im = Image.frombytes("L" if pix.n == 1 else "RGB", (pix.width, pix.height), pix.samples)
    if smask:
        m = fitz.Pixmap(doc, smask)
        if m.n != 1:
            m = fitz.Pixmap(fitz.csGRAY, m)
        mask = Image.frombytes("L", (m.width, m.height), m.samples)
        if mask.size != im.size:
            mask = mask.resize(im.size, Image.BILINEAR)
        im = im.convert("RGB")
        im.putalpha(mask)
    return im


def _photo_like(im):
    return len(im.convert("RGB").resize((64, 64)).getcolors(4096) or range(5000)) > 256


def _png(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def _jpg(im, q=88):
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=q, optimize=True)
    return b.getvalue()


def sheet(images, labels, cols=5):
    """One JPEG of every picture in a grid, each numbered, under SHEET_MAX (smaller tiles until it fits)."""
    from PIL import Image, ImageDraw, ImageFont
    cols = min(cols, max(1, len(images)))
    width = 360
    while True:
        tiles = [im.resize((width, max(1, round(im.height * width / im.width)))) for im in images]
        th = max(t.height for t in tiles)
        rows = (len(tiles) + cols - 1) // cols
        gap = 6
        out = Image.new("RGB", (cols * width + (cols + 1) * gap, rows * th + (rows + 1) * gap), (24, 24, 26))
        d = ImageDraw.Draw(out)
        try:
            font = ImageFont.load_default(size=max(12, width // 16))
        except TypeError:   # an older Pillow
            font = ImageFont.load_default()
        for i, (t, label) in enumerate(zip(tiles, labels)):
            x, y = gap + (i % cols) * (width + gap), gap + (i // cols) * (th + gap)
            out.paste(t, (x, y))
            bb = d.textbbox((0, 0), label, font=font)
            d.rectangle((x, y, x + bb[2] + 10, y + bb[3] + 8), fill=(0, 0, 0))
            d.text((x + 5, y + 3), label, fill=(255, 255, 255), font=font)
        blob = _jpg(out, 72)
        if len(blob) <= SHEET_MAX or width <= 120:
            return blob
        width = int(width * 0.82)


# ---------- SVG ----------
def clean_svg(text):
    """An SVG with nothing that runs or reaches out: no script, foreignObject or embedded documents, no on* handlers,
    no links but to its own parts or to embedded pictures. None when it isn't an SVG."""
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    text = re.sub(r"<!DOCTYPE[^>[]*(\[[^\]]*\])?>", "", text, flags=re.I)   # no entities: they can reach out too
    try:
        root = ET.fromstring(text.strip().encode())
    except ET.ParseError:
        return None
    if root.tag.split("}")[-1] != "svg":
        return None
    bad = {"script", "foreignobject", "iframe", "embed", "object", "handler", "listener"}
    for parent in list(root.iter()):
        for child in list(parent):
            if not isinstance(child.tag, str) or child.tag.split("}")[-1].lower() in bad:
                parent.remove(child)
    for el in root.iter():
        for k in list(el.attrib):
            name, v = k.split("}")[-1].lower(), el.attrib[k].strip()
            if name.startswith("on"):
                del el.attrib[k]
            elif name == "href" and not (v.startswith("#") or re.match(r"data:image/(png|jpe?g|gif|webp);", v, re.I)):
                del el.attrib[k]
            elif name == "style" and re.search(r"url\(\s*['\"]?(?!#)", v, re.I):
                del el.attrib[k]
    return ET.tostring(root, encoding="unicode")


def svg_info(text):
    m = re.search(r'viewBox\s*=\s*["\']([^"\']+)', text)
    return {"viewBox": m.group(1)} if m else {}


# ---------- JSON and HTML ----------
URL = re.compile(r"^(https?:)?//[^\s\"'<>]+$", re.I)
IMG_URL = re.compile(r"\.(png|jpe?g|webp|gif|avif|svg)(\?|#|$)", re.I)
IMG_KEY = re.compile(r"image|img|photo|picture|thumb|logo|icon|og_png|favicon|poster|src$", re.I)
TITLE_KEYS = ("title", "name", "product_title", "productTitle", "product_name", "productName", "label")
PRICE_KEY = re.compile(r"price|amount|cost", re.I)
FONT_PATH = re.compile(r"font|typeface|typograph", re.I)
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
HEX_IN = re.compile(r"(?<![\w&/])#([0-9a-fA-F]{6})\b")
DATA_URI = re.compile(r"data:image/(svg\+xml|png|jpe?g|webp|gif)((?:;[\w=.-]+)*),([^\s\"')<>]+)", re.I)
CSS_FONT = re.compile(r"font-family\s*:\s*([^;}{<>\n]+)", re.I)


class Found:
    """What the JSON and HTML sources hold, gathered across files."""
    def __init__(self):
        self.colours, self.fonts, self.products, self.urls, self.uris = {}, {}, [], {}, []

    def colour(self, hx, key, source):
        hx = hx.upper()
        if len(hx) in (4, 5):
            hx = "#" + "".join(c * 2 for c in hx[1:4])
        hx = hx[:7]
        c = self.colours.setdefault(hx, {"hex": hx, "count": 0, "keys": [], "names": [], "sources": []})
        c["count"] += 1
        if key and key not in c["keys"] and len(c["keys"]) < 4:
            c["keys"].append(key)
        name = _leaf(key)
        if name and name not in c["names"] and len(c["names"]) < 3:
            c["names"].append(name)
        if source not in c["sources"]:
            c["sources"].append(source)

    def font(self, value, key, source):
        for fam in value.split(","):
            fam = fam.strip().strip("'\"").strip()
            if not fam or fam.lower() in GENERIC_FONTS or len(fam) > 40 or URL.match(fam) or re.search(r"[/=\"']|var\(", fam):
                continue
            f = self.fonts.setdefault(fam.lower(), {"family": fam, "count": 0, "keys": [], "sources": []})
            f["count"] += 1
            if key and key not in f["keys"] and len(f["keys"]) < 3:
                f["keys"].append(key)
            if source not in f["sources"]:
                f["sources"].append(source)

    def url(self, u, key, source):
        if u.startswith("//"):
            u = "https:" + u
        if u not in self.urls:
            self.urls[u] = {"url": u, "key": key, "source": source}


def _leaf(key):
    parts = [p for p in str(key or "").split(".") if p and not p.isdigit() and p != "[]"]
    return parts[-1].lstrip("-") if parts else ""


def _key(path):
    return ".".join("[]" if isinstance(p, int) else str(p) for p in path)


def scan_string(s, path, source, found):
    key = _key(path)
    for m in DATA_URI.finditer(s):
        found.uris.append({"type": m.group(1).lower(), "params": m.group(2), "data": m.group(3), "key": key, "source": source})
    if s.startswith("data:"):
        return
    st = s.strip()
    if HEX.match(st):
        found.colour(st, key, source)
    elif len(st) < 4000:
        for m in HEX_IN.finditer(st):
            if not URL.match(st):
                found.colour("#" + m.group(1), key, source)
    if URL.match(st) and (IMG_URL.search(st) or IMG_KEY.search(_leaf(key))):
        found.url(st, key, source)
    bare = re.sub(r"\s*\([^)]*\)", "", st)   # "Acme Sans (400, 700)" is Acme Sans
    if FONT_PATH.search(key) and len(bare) <= 80 and not URL.match(st) and not re.search(r"[.!?]\s|\d{3,}|=", bare):
        found.font(bare, key, source)
    for m in CSS_FONT.finditer(st):
        found.font(m.group(1), key, source)


def walk(x, path, source, found):
    if isinstance(x, dict):
        product(x, path, source, found)
        for k, v in x.items():
            walk(v, path + (str(k),), source, found)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            walk(v, path + (i,), source, found)
    elif isinstance(x, str):
        scan_string(x, path, source, found)


def _image_of(v):
    if isinstance(v, str) and URL.match(v.strip()):
        return v.strip()
    if isinstance(v, list):
        return next((u for u in (_image_of(x) for x in v) if u), None)
    if isinstance(v, dict):
        return next((u for u in (_image_of(v.get(k)) for k in ("src", "url", "href", "original", "large", "full")) if u), None)
    return None


def _price_of(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str) and re.fullmatch(r"\s*[^\d\s]{0,4}\s*\d[\d\s.,]*\s*[^\d\s]{0,4}\s*", v):
        return v.strip()
    if isinstance(v, dict):
        return next((p for p in (_price_of(v.get(k)) for k in ("amount", "value", "price")) if p is not None), None)
    return None


def product(d, path, source, found):
    """An object that looks like a product: a title or name, a price, and an image URL."""
    title = next((d[k].strip() for k in TITLE_KEYS if isinstance(d.get(k), str) and d[k].strip()), None)
    if not title:
        return
    price = next(((k, p) for k, v in d.items() if PRICE_KEY.search(str(k)) for p in [_price_of(v)] if p is not None), None)
    image = next(((k, u) for k, v in d.items() if IMG_KEY.search(str(k)) for u in [_image_of(v)] if u), None)
    if not price or not image:
        return
    link = next((v for k, v in d.items() if re.search(r"url|link|href|pdp|handle", str(k), re.I) and k != image[0]
                 and isinstance(v, str) and v.strip()), None)
    found.products.append({"title": title, "price": price[1], "price_key": price[0], "image": image[1], **({"url": link} if link else {}),
                           "source": source, "at": _key(path)})


def html_scan(text, source, found):
    for m in DATA_URI.finditer(text):
        found.uris.append({"type": m.group(1).lower(), "params": m.group(2), "data": m.group(3), "key": "html", "source": source})
    for m in re.finditer(r"<svg\b.*?</svg>", text, re.S | re.I):
        found.uris.append({"type": "svg+xml", "params": ";inline", "data": m.group(0), "key": "inline svg", "source": source})
    for m in HEX_IN.finditer(text):
        found.colour("#" + m.group(1), "css", source)
    for m in CSS_FONT.finditer(text):
        found.font(m.group(1), "font-family", source)
    for m in re.finditer(r"""(?:src|href|content)\s*=\s*["']([^"']+)["']""", text, re.I):
        u = m.group(1).strip()
        if URL.match(u) and IMG_URL.search(u):
            found.url(u, "html", source)


def decode_uri(u):
    if u["params"] == ";inline":
        return u["data"].encode()
    data = u["data"]
    if ";base64" in u["params"].lower():
        try:
            return base64.b64decode(data + "=" * (-len(data) % 4))
        except ValueError:
            return None
    return urllib.parse.unquote_to_bytes(data)


# ---------- the whole digest ----------
def _put(out, rel, blob):
    p = os.path.join(out, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(blob)


def _image_file(path, rel, idx, seen, extra=None):
    from PIL import Image
    with open(path, "rb") as f:
        data = f.read()
    key = _sha(data)
    if key in seen:
        return seen[key]
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        if getattr(im, "n_frames", 1) > 1:
            im.seek(0)
    except Exception:   # noqa: BLE001
        return None
    img = {"path": rel, **(extra or {}), **look(im)}
    idx["images"].append(img)
    seen[key] = img
    return img


def video(path, name, out, idx):
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    entry = {"source": f"sources/{name}", "kind": "video"}
    if ff and fp:
        try:
            dur = float(subprocess.run([fp, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                       capture_output=True, text=True, timeout=60).stdout.strip() or 0)
            stem = _safe(os.path.splitext(name)[0])
            dst = os.path.join(out, "sheets", f"{stem}.jpg")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if dur > 0:
                subprocess.run([ff, "-v", "error", "-y", "-i", path, "-vf", f"fps={12 / dur:.5f},scale=320:-2,tile=4x3", "-frames:v", "1", "-q:v", "6", dst],
                               capture_output=True, timeout=300)
            if os.path.isfile(dst):
                entry.update(seconds=round(dur, 2), sheet=f"digest/sheets/{stem}.jpg")
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    idx["documents"].append(entry)


def fetch(found, out, old, idx, seen, allowed):
    """The image URLs the sources list, fetched once each (only with --fetch); ones fetched before are kept."""
    have = {f["url"]: f for f in (old or {}).get("fetched", []) if os.path.isfile(os.path.join(out, f["file"].replace("digest/", "", 1)))}
    urls = list(dict.fromkeys([p["image"] for p in found.products] + list(found.urls)))
    got = []
    for i, u in enumerate(urls):
        if u in have:
            got.append(have[u])
            continue
        if not allowed or len(got) >= FETCH_MAX:
            continue
        if u.startswith("//"):
            u2 = "https:" + u
        else:
            u2 = u
        if not re.match(r"^https?://", u2, re.I):
            continue
        try:
            req = urllib.request.Request(u2, headers={"User-Agent": "Mozilla/5.0 (Spliced profile digest)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read(FETCH_BYTES + 1)
                ctype = r.headers.get("Content-Type", "")
        except Exception:   # noqa: BLE001  (a picture that won't come is left out)
            continue
        if len(data) > FETCH_BYTES:
            continue
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg",
               "image/avif": ".avif"}.get(ctype.split(";")[0].strip().lower()) or (os.path.splitext(urllib.parse.urlsplit(u2).path)[1].lower() or ".img")
        name = f"fetched/{len(got) + 1:03d}-{_safe(os.path.splitext(os.path.basename(urllib.parse.urlsplit(u2).path))[0])[:40]}{ext}"
        _put(out, name, data)
        got.append({"url": u, "file": f"digest/{name}"})
    for g in got:
        p = os.path.join(out, g["file"].replace("digest/", "", 1))
        if p.endswith(".svg"):
            continue
        img = _image_file(p, g["file"], idx, seen, {"from": g["url"]})
        if img:
            g["kind"] = img.get("kind")
    idx["fetched"] = got
    by_url = {g["url"]: g["file"] for g in got}
    for pr in found.products:
        if pr["image"] in by_url:
            pr["file"] = by_url[pr["image"]]


def build(slug, do_fetch=False, force=False):
    """Digest one profile's sources, one run at a time (a second waits, then finds the work done). Returns (index, built)."""
    profiles.get(slug)
    lock = os.path.join(paths.profile_home(), ".cache", f"digest-{slug}.lock")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "w") as fh:
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
        except ImportError:   # no flock here: runs are rare enough to take the chance
            pass
        return _build(slug, do_fetch, force)


def _build(slug, do_fetch, force):
    folder = profiles._dir(slug)
    files = source_files(folder)
    final = os.path.join(folder, "digest")
    old = read_index(final)
    h = content_hash(files)
    if old and not force and old.get("hash") == h and old.get("version") == VERSION and not (do_fetch and not old.get("fetch_done")):
        if old.get("stamp") != stamp(files):
            old["stamp"] = stamp(files)
            _put(final, "index.json", (json.dumps(old, indent=1, ensure_ascii=False) + "\n").encode())
        return old, False
    out = f"{final}.building-{os.getpid()}"
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    if os.path.isdir(os.path.join(final, "fetched")):   # fetched once, kept: never asked for again
        shutil.copytree(os.path.join(final, "fetched"), os.path.join(out, "fetched"))
    idx = {"version": VERSION, "profile": slug, "hash": h, "stamp": stamp(files), "sources": [], "documents": [], "images": [],
           "logos": [], "colours": [], "fonts": [], "products": [], "image_urls": [], "notes": []}
    seen, found = {}, Found()
    for f in files:
        name = os.path.basename(f)
        ext = os.path.splitext(name)[1].lower()
        idx["sources"].append({"file": f"sources/{name}", "bytes": os.path.getsize(f)})
        try:
            if ext == ".pdf":
                pdf(f, name, out, idx, seen)
            elif ext in IMAGE_EXT:
                _image_file(f, f"sources/{name}", idx, seen, {"from": "source"})
            elif ext == ".svg":
                with open(f, encoding="utf-8", errors="replace") as fh:
                    found.uris.append({"type": "svg+xml", "params": ";inline", "data": fh.read(), "key": name, "source": name})
            elif ext == ".json":
                with open(f, encoding="utf-8", errors="replace") as fh:
                    walk(json.load(fh), (), name, found)
            elif ext in (".html", ".htm"):
                with open(f, encoding="utf-8", errors="replace") as fh:
                    html_scan(fh.read(), name, found)
            elif ext in VIDEO_EXT:
                video(f, name, out, idx)
            elif name.endswith(profiles.SITE):
                idx["documents"].append({"source": f"sources/{name}", "kind": "site", "note": "a website Spliced read: already a digest, read it as it is"})
            elif ext in (".txt", ".md"):
                idx["documents"].append({"source": f"sources/{name}", "kind": "text", "note": "plain text: read it as it is"})
            else:
                idx["notes"].append(f"sources/{name}: not digested (export a deck as PDF and add that)")
        except Exception as e:   # noqa: BLE001  (one unreadable file never stops the rest)
            idx["notes"].append(f"sources/{name}: couldn't be read ({type(e).__name__}: {str(e)[:120]})")
    logos(found, out, idx, seen)
    fetch(found, out, old if os.path.isdir(os.path.join(out, "fetched")) else None, idx, seen, do_fetch)
    idx["fetch_done"] = bool(do_fetch or (old or {}).get("fetch_done"))
    idx["colours"] = sorted(found.colours.values(), key=lambda c: -c["count"])
    idx["fonts"] = sorted(found.fonts.values(), key=lambda f: -f["count"])
    idx["products"] = found.products
    idx["image_urls"] = list(found.urls.values())
    _put(out, "index.json", (json.dumps(idx, indent=1, ensure_ascii=False) + "\n").encode())
    _put(out, "README.md", readme(slug, idx).encode())
    if os.path.isdir(final):
        gone = f"{final}.old-{os.getpid()}"
        os.rename(final, gone)
        os.rename(out, final)
        shutil.rmtree(gone, ignore_errors=True)
    else:
        os.rename(out, final)
    return idx, True


def logos(found, out, idx, seen):
    """SVGs (files, data URIs, inline) cleaned into logos/; raster data URIs measured as pictures."""
    done = set()
    for u in found.uris:
        data = decode_uri(u)
        if not data:
            continue
        key = _sha(data)
        if key in done:
            continue
        done.add(key)
        if u["type"] == "svg+xml":
            svg = clean_svg(data.decode("utf-8", "replace"))
            if not svg:
                continue
            stem = _safe(os.path.splitext(u["source"])[0] + ("-" + _leaf(u["key"]) if u["key"] != u["source"] else ""))
            rel, n = f"logos/{stem}.svg", 2
            while os.path.exists(os.path.join(out, rel)):
                rel, n = f"logos/{stem}-{n}.svg", n + 1
            _put(out, rel, svg.encode())
            idx["logos"].append({"path": f"digest/{rel}", "from": f"sources/{u['source']}", "key": u["key"],
                                 "how": "a file" if u["key"] == u["source"] else "inline" if u["params"] == ";inline" else "data URI", **svg_info(svg)})
        elif len(data) > 2048:
            ext = ".jpg" if "jp" in u["type"] else "." + u["type"]
            rel = f"images/{_safe(os.path.splitext(u['source'])[0])}-{_safe(_leaf(u['key']) or 'data')}-{key[:6]}{ext}"
            _put(out, rel, data)
            _image_file(os.path.join(out, rel), f"digest/{rel}", idx, seen, {"from": f"sources/{u['source']}", "key": u["key"]})
    # the likeliest logo first: one a key or file name calls a logo
    idx["logos"].sort(key=lambda x: (not re.search(r"logo|brand|mark", x["key"] + " " + os.path.basename(x["path"]), re.I), x["path"]))


def read_index(folder):
    try:
        with open(os.path.join(folder, "index.json")) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _pct(v):
    return f"{round(v * 100)}"


def image_line(im):
    s = f"- {im['path']}  {im['w']}x{im['h']}  {im['kind']}" + (" alpha" if im.get("alpha") else "")
    if im.get("mask"):
        s += " (soft mask merged)"
    if im.get("subject"):
        x, y, w, h = im["subject"]
        s += f"  subject x{_pct(x)} y{_pct(y)} w{_pct(w)} h{_pct(h)}%, centre {_pct(im['focus'][0])}% {_pct(im['focus'][1])}%"
    if im.get("screen"):
        r = im["screen"]
        s += f"  screen x{r['x']} y{r['y']} w{r['w']} h{r['h']}px"
    if im.get("colours"):
        s += "  " + " ".join(c["hex"] for c in im["colours"][:4])
    if im.get("pages"):
        ps = im["pages"]
        s += f"  (p{', p'.join(map(str, ps[:6]))}{' ...' if len(ps) > 6 else ''})"
    elif im.get("from") and im["from"] != "source":
        s += f"  ({im['from'][:80]})"
    return s


def readme(slug, idx):
    L = [f"# The sources of the profile {slug}, digested", "",
         f"Made by `{paths.CLI} profile digest {slug}`. Use these instead of opening sources/: a document's text is in "
         "pages/, its pages at a glance on one sheet in sheets/, its pictures in images/ (measured below), logos in logos/. "
         "Paths are relative to the profile's folder (the one holding this digest/). The full detail is in index.json.", ""]
    if idx["documents"]:
        L += ["## Documents", ""]
        for d in idx["documents"]:
            if d["kind"] == "pdf":
                L.append(f"- {d['source']}: {d['pages']} pages. Text: {d['text']}. Every page on one sheet: {d['sheet']}. {len(d['images'])} pictures in images/")
            elif d["kind"] == "video":
                L.append(f"- {d['source']}: a film" + (f" of {d['seconds']}s, twelve frames on {d['sheet']}" if d.get("sheet") else " (no ffmpeg here: not digested)"))
            else:
                L.append(f"- {d['source']}: {d['note']}")
        L.append("")
    if idx["images"]:
        kinds = {}
        for im in idx["images"]:
            kinds[im["kind"]] = kinds.get(im["kind"], 0) + 1
        L += ["## Pictures", "", "Kind: cutout (alpha, or a subject on near white; subject box and centre as % of the picture, for object-position "
              "and zoom), photo, backdrop (heavily blurred, little detail). A screen is a device's uniform screen, in pixels. "
              + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())) + ".", ""]
        order = {"cutout": 0, "photo": 1, "backdrop": 2}
        for im in sorted(idx["images"], key=lambda i: (order.get(i["kind"], 3), -i["w"] * i["h"])):
            L.append(image_line(im))
        L.append("")
    if idx["logos"]:
        L += ["## Logos (SVG, cleaned)", ""] + [f"- {x['path']}  ({x['how']} in {x['from']}{', ' + x['key'] if x['how'] == 'data URI' else ''})"
                                                 + (f"  viewBox {x['viewBox']}" if x.get("viewBox") else "") for x in idx["logos"]] + [""]
    if idx["colours"]:
        L += ["## Colours", ""] + [f"- {c['hex']}  {', '.join(c['names']) or '-'}  ({'; '.join(c['keys'][:2])}{', ' + str(c['count']) + 'x' if c['count'] > 1 else ''})"
                                   for c in idx["colours"][:24]]
        L += ([f"- ... {len(idx['colours']) - 24} more in index.json"] if len(idx["colours"]) > 24 else []) + [""]
    if idx["fonts"]:
        L += ["## Typefaces", ""] + [f"- {f['family']}  ({'; '.join(f['keys'][:2])})" for f in idx["fonts"][:12]] + [""]
    if idx["products"]:
        by = {}
        for p in idx["products"]:
            by.setdefault(p["source"], []).append(p)
        L += ["## Products", ""]
        for src, ps in by.items():
            L.append(f"{len(ps)} in sources/{src}:")
            for p in ps[:15]:
                L.append(f"- {p['title']}  {p['price']}  {p.get('file') or p['image']}")
            if len(ps) > 15:
                L.append(f"- ... {len(ps) - 15} more in index.json")
        L.append("")
    if idx["image_urls"]:
        n = len(idx["fetched"]) if idx.get("fetched") else 0
        L += ["## Picture addresses", "", f"{len(idx['image_urls'])} image URLs are listed in index.json (image_urls)"
              + (f"; {n} are fetched into fetched/." if n else f". Nothing was downloaded: `{paths.CLI} profile digest {slug} --fetch` fetches them once."), ""]
    if idx["notes"]:
        L += ["## Not digested", ""] + [f"- {n}" for n in idx["notes"]] + [""]
    return "\n".join(L).rstrip() + "\n"


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    slug = a[0]
    try:
        idx, built = build(slug, do_fetch="--fetch" in a, force="--force" in a)
    except (KeyError, ValueError) as e:
        sys.exit(str(e.args[0]) if e.args else str(e))
    where = profiles.where(slug)
    if not built:
        print(f"The digest of {slug} is current: {where}/digest/README.md")
        return
    kinds = {}
    for im in idx["images"]:
        kinds[im["kind"]] = kinds.get(im["kind"], 0) + 1
    bits = [f"{sum(d.get('pages', 0) for d in idx['documents'])} pages" if any(d["kind"] == "pdf" for d in idx["documents"]) else "",
            f"{len(idx['images'])} pictures ({', '.join(f'{n} {k}' for k, n in sorted(kinds.items()))})" if idx["images"] else "",
            f"{len(idx['logos'])} logos" if idx["logos"] else "", f"{len(idx['colours'])} colours" if idx["colours"] else "",
            f"{len(idx['fonts'])} typefaces" if idx["fonts"] else "", f"{len(idx['products'])} products" if idx["products"] else "",
            f"{len(idx['image_urls'])} image URLs" if idx["image_urls"] else ""]
    print(f"Digested {len(idx['sources'])} source(s) of {slug}: " + (", ".join(b for b in bits if b) or "nothing to digest") + f". Read {where}/digest/README.md")
    for n in idx["notes"]:
        print(f"  {n}")


if __name__ == "__main__":
    main()
