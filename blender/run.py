"""blender -b --factory-startup -P run.py -- <záber> <výstup.png|priečinok> [--w 1920 --h 1080 --s 256 --frames 1:120 --blend cesta.blend]"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import shots  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
name, out = argv[0], os.path.abspath(argv[1])
opts = {argv[i].lstrip("-"): argv[i + 1] for i in range(2, len(argv) - 1, 2)}
w, h, s = int(opts.get("w", 1920)), int(opts.get("h", 1080)), int(opts.get("s", 256))

builders = dict(shots.SHOTS)
try:
    import anims
    builders.update(anims.ANIMS)
except ImportError:
    pass

t0 = time.time()
sc = builders[name](w, h, s)
if "blend" in opts:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(opts["blend"]))
print(f"[run] scene {name} built in {time.time() - t0:.1f}s")

t0 = time.time()
if "frames" in opts:
    a, b = (int(x) for x in opts["frames"].split(":"))
    os.makedirs(out, exist_ok=True)
    for f in range(a, b + 1):
        target = os.path.join(out, f"{f:04d}.png")
        if os.path.exists(target) and not opts.get("force"):
            continue
        sc.frame_set(f)
        sc.render.filepath = target
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[run] frame {f} {time.time() - t1:.1f}s", flush=True)
else:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
print(f"[run] {name} rendered in {time.time() - t0:.1f}s", flush=True)
