"""blender -b --factory-startup -P render_well.py -- <priečinok> <veľkosť> <samples> <K> [indexy 1..K oddelené čiarkou]

Vyrenderuje K snímok zostupu rovnomerne v čase t = 0..1 (podsnímky 120-snímkovej animácie)
ako 001.png .. K.png. Existujúce snímky preskočí. Vrch studne (lúka, veniec) dopĺňa well_top.py.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402

import anims  # noqa: E402
import well_top  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
out, size, s, K = os.path.abspath(argv[0]), int(argv[1]), int(argv[2]), int(argv[3])
only = [int(x) for x in argv[4].split(",")] if len(argv) > 4 else list(range(1, K + 1))
os.makedirs(out, exist_ok=True)
sc = anims.well_c(size, size, s)
well_top.dress(sc)  # lúka, tráva a kamenný veniec okolo studne
sc.cycles.diffuse_bounces = 5


def exposure(t):
    """Oči si v tme zvykajú: expozícia rastie s hĺbkou."""
    a = min(1.0, max(0.0, (t - 0.12) / 0.5))
    return 2.4 * a * a * (3 - 2 * a) + 0.4 * max(0.0, t - 0.62) / 0.38


for k in only:
    target = os.path.join(out, f"{k:03d}.png")
    if os.path.exists(target):
        continue
    t = (k - 1) / (K - 1)
    f = 1 + t * (anims.FRAMES - 1)
    sc.frame_set(int(f), subframe=f - int(f))
    sc.view_settings.exposure = exposure(t)
    sc.render.filepath = target
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[well] {k}/{K} {time.time() - t0:.1f}s", flush=True)
print("[well] done", flush=True)
