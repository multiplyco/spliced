# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools"]
# ///
"""Set the app's wordmark from the typeface and write every wordmark and lockup file.

The wordmark is Anybody (Google Fonts, OFL) at width 130, weight 700, uppercase, no tracking, cap height 100 units,
outlined (never live text), with the first letter's left side bearing trimmed so the word starts at x = 0. That is
how the original SPLICE wordmark was cut (checked letter by letter), so changing the name is: change NAME, run this.

  uv run scripts/brand_wordmark.py      # writes spliced/web/brand/*-wordmark-*.svg, *-lockup-*.svg,
                                        # and the inline lockup in spliced/web/index.html
The variable font is downloaded once to ~/.cache/brand-fonts/.
"""
import os, re, urllib.request
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

NAME = "Spliced"
AXES = {"wdth": 130, "wght": 700}
CAP = 100.0  # cap height in svg units
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spliced", "web")  # the app's own files
BRAND = os.path.join(WEB, "brand")
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/anybody/Anybody%5Bwdth,wght%5D.ttf"
FONT = os.path.expanduser("~/.cache/brand-fonts/Anybody[wdth,wght].ttf")
INK = {"white": "#F4F4F1", "black": "#0B0B0C", "volt": "#DFFF1A"}
# The mark's polygons in each tone (copied from the existing lockups, which stay the source of the mark).
MARK = {"white": "splice-lockup-horizontal-white.svg", "black": "splice-lockup-horizontal-black.svg", "volt": "splice-lockup-horizontal-volt.svg"}
H_MARK_S, H_DX, H_DY = 0.72176, 266.67, 22.9      # horizontal lockup: mark scale, wordmark offset
S_MARK_S, S_DY = 1.19692, 341.28                  # stacked lockup: mark scale (centred), wordmark offset
MARK_W, MARK_H = 277.1, 202.0


def font():
    if not os.path.exists(FONT):
        os.makedirs(os.path.dirname(FONT), exist_ok=True)
        urllib.request.urlretrieve(FONT_URL, FONT)
    return instantiateVariableFont(TTFont(FONT), AXES)


def wordmark(text):
    """The outlined word: (svg path d, width), cap top at y = 0, baseline at y = CAP."""
    f = font()
    gs, cmap, upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    cap = f["OS/2"].sCapHeight
    s = CAP / cap
    names = [cmap[ord(ch)] for ch in text.upper()]
    bp = BoundsPen(gs); gs[names[0]].draw(bp)
    x, lsb = 0, bp.bounds[0]
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    right = 0
    for n in names:
        gs[n].draw(TransformPen(pen, (s, 0, 0, -s, (x - lsb) * s, cap * s)))
        b = BoundsPen(gs); gs[n].draw(b); right = (x + b.bounds[2] - lsb) * s
        x += gs[n].width
    return pen.getCommands(), round(right, 2)


def shift(d, dx, dy):
    """Move every absolute coordinate pair of a path (M/L/Q/C/H/V as SVGPathPen writes them)."""
    out, cmd = [], None
    for tok in re.findall(r"[MLQCHVZ]|-?\d+\.?\d*", d):
        if tok.isalpha():
            cmd, i = tok, 0; out.append(tok); continue
        v = float(tok)
        if cmd == "H": v += dx
        elif cmd == "V": v += dy
        else: v += dx if i % 2 == 0 else dy; i += 1
        out.append(f"{v:.2f}".rstrip("0").rstrip("."))
    return re.sub(r" (?=[MLQCHVZ])|(?<=[MLQCHVZ]) ", "", " ".join(out))


def polygons(tone):
    return "\n".join(re.findall(r"<polygon[^>]*/>", open(os.path.join(BRAND, MARK[tone])).read()))


def main():
    d, w = wordmark(NAME)
    head = lambda vw, vh: f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw:.2f} {vh:.2f}" width="{round(vw)}" height="{round(vh)}" role="img" aria-label="{NAME}">\n<title>{NAME}</title>\n'
    files = {}
    for tone, ink in INK.items():
        files[f"splice-wordmark-{tone}.svg"] = head(w, CAP) + f'<path fill="{ink}" d="{d}"/>\n</svg>\n'
        hw = H_DX + w
        files[f"splice-lockup-horizontal-{tone}.svg"] = (head(hw, MARK_H * H_MARK_S) + f'<g transform="translate(0.00 0.00) scale({H_MARK_S})">\n{polygons(tone)}\n</g>\n'
                                                       + f'<path fill="{ink}" d="{shift(d, H_DX, H_DY)}"/>\n</svg>\n')
        files[f"splice-lockup-stacked-{tone}.svg"] = (head(w, S_DY + CAP) + f'<g transform="translate({(w - MARK_W * S_MARK_S) / 2:.2f} 0.00) scale({S_MARK_S})">\n{polygons(tone)}\n</g>\n'
                                                    + f'<path fill="{ink}" d="{shift(d, 0, S_DY)}"/>\n</svg>\n')
    for fn, svg in files.items():
        open(os.path.join(BRAND, fn), "w").write(svg)
    # the sidebar's inline lockup (fills follow the theme through CSS variables): new viewBox, label and word path
    p = os.path.join(WEB, "index.html")
    html = open(p).read()
    m = re.search(r'<svg class="lockup"[^>]*>.*?</svg>', html, re.S)
    old = m.group(0)
    new = re.sub(r'viewBox="0 0 [\d.]+ ([\d.]+)"', lambda k: f'viewBox="0 0 {H_DX + w:.2f} {k.group(1)}"', old)
    new = re.sub(r'aria-label="[^"]*"', f'aria-label="{NAME}"', new)
    new = re.sub(r'(<path[^>]* d=")[^"]*(")', lambda k: k.group(1) + shift(d, H_DX, H_DY) + k.group(2), new)
    open(p, "w").write(html.replace(old, new))
    print(f"{NAME.upper()}: {w} x {CAP} units; wrote {len(files)} files in library/toolbox/brand and the lockup in index.html")


if __name__ == "__main__":
    main()
