"""Masky leptaného (pieskovaného) motívu na sklo. Biela = matné sklo.

Obrázok pokrýva celý obvod (u 0..1) a výšku fľaše (v 0..1 = z 0..h_top).
Predná strana fľaše (smer -Y, kamera) je u = 0.75, overené testom test/uv_side.py.
Do 12. 11. 2026 bol nápis omylom na u = 0.25, teda vzadu, a kamera ho videla cez vodu.

Verzia 2: dolu okolo celej fľaše matný pás s obrysom kopcov Myjavskej pahorkatiny,
nad ním tenká línia vzdialeného hrebeňa. Pás je leptaný jemnejšie (sivá v maske),
nápisy naplno (biela). Nad pásom zvislý nápis HLBINA a vedľa neho drobné
„MYJAVA · 0,75 l · 13 m". Písmo v páse by nebolo vidno: cez matný predok sa pozeráte
na matnú zadnú stranu pásu a všetko splynie.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec import BOTTLES, LABEL_W  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
OUT = os.path.join(HERE, "tex")
os.makedirs(OUT, exist_ok=True)
SS = 2  # kreslí sa vo dvojnásobnom rozlíšení a zmenší, kvôli hladkým hranám
BAND = 125  # jemnejšie leptanie pásu kopcov (255 = naplno)


def font(name, px):
    return ImageFont.truetype(os.path.join(FONTS, name), int(px))


def text_img(txt, fnt, tracking_px):
    """Riadok textu s prestrkaním písmen, vráti L obrázok orezaný na písmo."""
    widths = [fnt.getlength(c) for c in txt]
    total = int(sum(widths) + tracking_px * (len(txt) - 1)) + 40
    asc, desc = fnt.getmetrics()
    img = Image.new("L", (total, asc + desc + 40), 0)
    d = ImageDraw.Draw(img)
    x = 20
    for c, w in zip(txt, widths):
        d.text((x, 20), c, font=fnt, fill=255)
        x += w + tracking_px
    return img.crop(img.getbbox())


def hills(u, scale, peaks):
    """Periodický obrys mäkkých kopcov (u 0..1), v metroch nad stredom pásu."""
    z = 0.0
    for pos, h, w in peaks:
        d = (u - pos + 0.5) % 1.0 - 0.5  # periodická vzdialenosť
        z += h * math.exp(-(d / w) ** 2)
    return z * scale


# kopce pásu: (poloha na obvode, výška, šírka); predok je u = 0.25
NEAR = [(0.03, 0.50, 0.050), (0.10, 0.95, 0.045), (0.155, 0.55, 0.035), (0.215, 1.15, 0.040),
        (0.29, 0.40, 0.050), (0.355, 0.85, 0.040), (0.41, 1.10, 0.040), (0.49, 0.55, 0.060),
        (0.585, 1.05, 0.050), (0.66, 0.45, 0.035), (0.735, 0.90, 0.045), (0.82, 1.25, 0.040),
        (0.90, 0.60, 0.050), (0.96, 0.85, 0.030)]
FAR = [(0.0, 0.6, 0.07), (0.09, 1.0, 0.06), (0.19, 0.7, 0.08), (0.30, 0.95, 0.05), (0.40, 0.6, 0.07),
       (0.52, 1.5, 0.06), (0.63, 0.8, 0.07), (0.75, 1.0, 0.06), (0.87, 0.7, 0.08)]
FRONT = 0.75  # predná strana fľaše
SHIFT = FRONT - 0.25  # obrys kopcov je navrhnutý okolo u = 0.25, posunie sa dopredu
TREE_U = 0.215  # osamelý strom na vrchole kopca vľavo od nápisu (pred posunom)


def make(key):
    b = BOTTLES[key]
    ppm = LABEL_W * SS / (2 * math.pi * b["R"])  # pixelov na meter
    W = LABEL_W * SS
    H = int(math.ceil(b["h_top"] * ppm))
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    cx = int(W * FRONT)

    def zpx(z):  # z v metroch -> riadok obrázka (hore je vrch fľaše)
        return H - z * ppm

    band = b["band"]
    amp = band * 0.36
    # matný pás: od dna po obrys kopcov
    pts = [(0, H)]
    for i in range(W + 1):
        u = i / W
        pts.append((i, zpx(band - amp * 0.35 + amp * hills((u - SHIFT) % 1.0, 1.0, NEAR))))
    pts.append((W, H))
    d.polygon(pts, fill=BAND)
    # vzdialený hrebeň: tenká línia nad pásom
    lw = max(2, int(0.00055 * ppm))
    far = [(i, zpx(band + amp * 1.05 + amp * 0.55 * hills((i / W - SHIFT) % 1.0, 1.0, FAR))) for i in range(0, W + 1, 2)]
    d.line(far, fill=170, width=lw)
    # osamelý strom na vrchole kopca: kmeň a okrúhla koruna
    tz = band - amp * 0.35 + amp * hills(TREE_U, 1.0, NEAR)
    tx = ((TREE_U + SHIFT) % 1.0) * W
    th, cr = 0.0062 * ppm, 0.0026 * ppm
    trunk_w = max(2, int(0.00045 * ppm))
    d.rectangle([tx - trunk_w / 2, zpx(tz) - th * 0.62, tx + trunk_w / 2, zpx(tz) + 2], fill=BAND)
    for ox, oy, rr in ((0, 0.70, 1.0), (-0.55, 0.55, 0.72), (0.55, 0.58, 0.75), (0.1, 0.92, 0.7)):
        ccx, ccy = tx + ox * cr, zpx(tz) - th * oy
        d.ellipse([ccx - cr * rr, ccy - cr * rr, ccx + cr * rr, ccy + cr * rr], fill=BAND)

    # zvislý nápis HLBINA nad pásom, číta sa zdola nahor
    word_h = b["word_h"] * ppm
    probe = text_img("HLBINA", font("Italiana.woff", 400), 400 * 0.42)
    scale = word_h / probe.width
    word = text_img("HLBINA", font("Italiana.woff", 400 * scale), 400 * scale * 0.42)
    word = word.rotate(90, expand=True)
    top = int(zpx(b["word_z"])) - word.height
    img.paste(255, (cx - word.width // 2, top), word)

    # drobný zvislý text vpravo vedľa nápisu, zarovnaný s jeho spodkom
    cap = 0.0021 * ppm
    small = text_img("MYJAVA  ·  " + b["size"] + "  ·  13 m", font("Jost_wght_400.woff", cap / 0.7), cap * 0.62)
    small = small.rotate(90, expand=True)
    sx = cx + word.width // 2 + int(0.0042 * ppm)
    img.paste(255, (sx, int(zpx(b["word_z"])) - small.height), small)

    img = img.resize((LABEL_W, H // SS), Image.LANCZOS)
    path = os.path.join(OUT, f"label_{key}.png")
    img.save(path)
    print("label", key, img.size, path)


if __name__ == "__main__":
    for k in BOTTLES:
        make(k)
