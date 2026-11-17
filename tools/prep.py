"""Pripraví obrázky pre web z renderov v blender/out.

python tools/prep.py          # všetko, čo už existuje
Fotky:   blender/out/stills/<meno>.png  -> assets/img/<meno>-<šírka>.webp
Zostup:  blender/out/well/NNN.png       -> assets/well/d/NNN.webp (960) a assets/well/m/NNN.webp (600)
Hladina: posledná snímka zostupu        -> assets/bottom-960.webp a assets/bottom-600.webp
"""
import glob
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "blender", "out")
ASSETS = os.path.join(ROOT, "assets")

WIDE = (2400, 1600, 1000)   # zábery 16:9
TALL = (1080, 720)          # zábery na výšku pre mobil


def save(im, path, width, q):
    if os.path.exists(path) and os.path.getmtime(path) > src_time:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(path, "WEBP", quality=q, method=6)
    return True


made = 0
for png in sorted(glob.glob(os.path.join(OUT, "stills", "*.png"))):
    name = os.path.splitext(os.path.basename(png))[0]
    src_time = os.path.getmtime(png)
    im = Image.open(png).convert("RGB")
    for w in (TALL if im.height > im.width else WIDE):
        made += save(im, os.path.join(ASSETS, "img", f"{name}-{w}.webp"), w, 80)

frames = sorted(glob.glob(os.path.join(OUT, "well", "[0-9][0-9][0-9].png")))
for png in frames:
    n = os.path.basename(png)[:3]
    src_time = os.path.getmtime(png)
    im = Image.open(png).convert("RGB")
    made += save(im, os.path.join(ASSETS, "well", "d", f"{n}.webp"), 960, 64)
    made += save(im, os.path.join(ASSETS, "well", "m", f"{n}.webp"), 600, 62)

last = os.path.join(OUT, "well", "072.png")
if os.path.exists(last):
    src_time = os.path.getmtime(last)
    im = Image.open(last).convert("RGB")
    made += save(im, os.path.join(ASSETS, "bottom-960.webp"), 960, 82)
    made += save(im, os.path.join(ASSETS, "bottom-600.webp"), 600, 80)

total = sum(os.path.getsize(p) for p in glob.glob(os.path.join(ASSETS, "**", "*.webp"), recursive=True))
print(f"nových súborov: {made}, snímok zostupu: {len(frames)}, assets spolu {total / 1e6:.1f} MB")
