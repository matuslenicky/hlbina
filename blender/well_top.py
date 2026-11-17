"""Vrch studne pre zostup (Cycles): lúka s trávou a kamenný veniec namiesto béžovej plochy.

Volá sa po anims.well_c(): odstráni pôvodnú plochu a veniec, pridá lúku (mierne zvlnený terén,
pokosená tráva, ďatelina a sedmokrásky), trsy trávy (pri studni nepokosené, vyššie), veniec
z pieskovcových kvádrov na vrchu šachty a svetlo otvoru obmedzí na šachtu (light linking),
aby na tráve nesvietil umelý kruh. Šachta a hladina ostávajú rovnaké ako v anims.py, takže
snímky, na ktorých už vrch studne nie je vidno, netreba prerenderovať.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector, noise

import anims
import lib
from lib import hexcol

CROWN_IN = anims.R_IN - 0.03      # vnútorný okraj venca (prečnieva nad šachtu)
CROWN_DEPTH = 0.34                # šírka kvádrov venca
CROWN_OUT = CROWN_IN + CROWN_DEPTH
CROWN_TOP = 0.66
GROUND_IN = anims.R_IN + 0.23     # zem začína pri vonkajšej stene šachty
VIEW = 2.0                        # kamera na začiatku vidí zhruba |x|, |y| < 1.8 m


def ground_z(x, y):
    """Výška lúky: jemné vlny a mierny násyp okolo studne."""
    r = math.hypot(x, y)
    z = 0.025 * noise.noise(Vector((x * 0.9, y * 0.9, 1.7))) + 0.008 * noise.noise(Vector((x * 4.0, y * 4.0, 5.3)))
    z += 0.045 * math.exp(-((r - GROUND_IN) / 0.55) ** 2)  # násyp
    return z


# ---------------------------------------------------------------- materiály

def _math(nt, op, a, b):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _mix(nt, fac, a, b, blend="MIX"):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = blend
    for sock, v in ((n.inputs["Factor"], fac), (n.inputs["A"], a), (n.inputs["B"], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            nt.links.new(v, sock)
    return n.outputs["Result"]


def _noise(nt, vec, scale, detail=4.0, rough=0.55, out="Fac"):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs[out]


def mat_meadow():
    """Pokosená lúka zhora: odtiene zelenej, suché fliačiky, ďatelina, sedmokrásky, ušliapaná zem pri studni."""
    m, nt, out = lib._nodes("meadow")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = 0.93
    p.inputs["Specular IOR Level"].default_value = 0.3
    tc = nt.nodes.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    # podklad: veľké a stredné škvrny zelenej
    big = _noise(nt, pos, 0.6, 5.0, 0.6)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.32, hexcol("#55683a")
    el[1].position, el[1].color = 0.68, hexcol("#87905a")
    L.new(big, ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    mid = _noise(nt, pos, 3.5, 6.0, 0.62)
    col = _mix(nt, _math(nt, "MULTIPLY", mid, 0.5), col, hexcol("#8e9a5c"), "MULTIPLY")
    # suchá tráva
    dry = _noise(nt, pos, 1.6, 4.0, 0.5)
    dryf = _math(nt, "MULTIPLY", _math(nt, "MAXIMUM", _math(nt, "SUBTRACT", dry, 0.58), 0.0), 3.2)
    col = _mix(nt, dryf, col, hexcol("#aca277"))
    # jemné steblá: pruhovaný šum v náhodných smeroch
    fine = _noise(nt, pos, 140.0, 2.0, 0.5)
    col = _mix(nt, _math(nt, "MULTIPLY", fine, 0.45), col, hexcol("#3c5524"), "MULTIPLY")
    # ďatelina: tmavšie zelené ostrovčeky
    clov = _noise(nt, pos, 7.0, 3.0, 0.5)
    clf = nt.nodes.new("ShaderNodeMapRange")
    clf.inputs["From Min"].default_value = 0.62
    clf.inputs["From Max"].default_value = 0.68
    L.new(clov, clf.inputs["Value"])
    col = _mix(nt, _math(nt, "MULTIPLY", clf.outputs[0], 0.6), col, hexcol("#4a6634"))
    # sedmokrásky a žlté kvietky: riedke bodky
    for scale, color, thr, seed in ((38.0, "#ecebe2", 0.035, 0.0), (31.0, "#d9c34a", 0.03, 7.0)):
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = scale
        vor.inputs["Randomness"].default_value = 1.0
        off = nt.nodes.new("ShaderNodeVectorMath")
        off.operation = "ADD"
        off.inputs[1].default_value = (seed, seed * 0.7, 0.0)
        L.new(pos, off.inputs[0])
        L.new(off.outputs[0], vor.inputs["Vector"])
        dot = nt.nodes.new("ShaderNodeMapRange")
        dot.inputs["From Min"].default_value = thr
        dot.inputs["From Max"].default_value = thr * 0.4
        L.new(vor.outputs["Distance"], dot.inputs["Value"])
        # len v niektorých bunkách (kvety rastú v skupinkách)
        grp = _noise(nt, pos, 1.3, 2.0, 0.5)
        gm = nt.nodes.new("ShaderNodeMapRange")
        gm.inputs["From Min"].default_value = 0.55
        gm.inputs["From Max"].default_value = 0.62
        L.new(grp, gm.inputs["Value"])
        cell = nt.nodes.new("ShaderNodeSeparateColor")
        L.new(vor.outputs["Color"], cell.inputs[0])
        keep = _math(nt, "GREATER_THAN", cell.outputs[0], 0.55)
        f = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", dot.outputs[0], gm.outputs[0]), keep)
        col = _mix(nt, f, col, hexcol(color))
    # ušliapaná zem tesne pri venci
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(pos, sep.inputs[0])
    rr = nt.nodes.new("ShaderNodeVectorMath")
    rr.operation = "LENGTH"
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(sep.outputs["X"], comb.inputs["X"])
    L.new(sep.outputs["Y"], comb.inputs["Y"])
    L.new(comb.outputs[0], rr.inputs[0])
    patch = _noise(nt, pos, 5.0, 4.0, 0.6)
    worn = nt.nodes.new("ShaderNodeMapRange")
    worn.inputs["From Min"].default_value = CROWN_OUT + 0.02
    worn.inputs["From Max"].default_value = CROWN_OUT + 0.30
    worn.inputs["To Min"].default_value = 0.85
    worn.inputs["To Max"].default_value = 0.0
    L.new(rr.outputs["Value"], worn.inputs["Value"])
    wf = _math(nt, "MULTIPLY", worn.outputs[0], _math(nt, "ADD", _math(nt, "MULTIPLY", patch, 0.8), 0.3))
    col = _mix(nt, _math(nt, "MINIMUM", wf, 1.0), col, hexcol("#6e604a"))
    L.new(col, p.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.01
    L.new(_math(nt, "ADD", fine, _math(nt, "MULTIPLY", mid, 0.6)), bump.inputs["Height"])
    L.new(bump.outputs[0], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m


def mat_grass():
    """Steblá: difúzne + presvitajúce, odtieň podľa polohy (rovnako ako tráva pri kameni v land.py)."""
    m, nt, out = lib._nodes("wellgrass")
    L = nt.links
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = _noise(nt, geo.outputs["Position"], 2.5, 3.0, 0.5)
    L.new(_mix(nt, nz, hexcol("#5f7240"), hexcol("#a8a172")), d.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = hexcol("#9aa65c")
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = 0.35
    L.new(d.outputs[0], mx.inputs[1])
    L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])
    return m


def mat_crown():
    """Pieskovcové kvádre venca: odtieň podľa kvádra, lišajníky, machy pri spodnej hrane."""
    m, nt, out = lib._nodes("crown")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = 0.86
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_type = "GEOMETRY"
    att.attribute_name = "rand"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#857a66")
    ramp.color_ramp.elements[1].color = hexcol("#b3a68c")
    L.new(att.outputs["Fac"], ramp.inputs["Fac"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    n1 = _noise(nt, pos, 9.0, 10.0, 0.62)
    col = _mix(nt, 0.55, ramp.outputs["Color"], n1, "OVERLAY")
    lich = _noise(nt, pos, 16.0, 6.0, 0.5)
    lm = nt.nodes.new("ShaderNodeMapRange")
    lm.inputs["From Min"].default_value = 0.60
    lm.inputs["From Max"].default_value = 0.66
    L.new(lich, lm.inputs["Value"])
    col = _mix(nt, _math(nt, "MULTIPLY", lm.outputs[0], 0.5), col, hexcol("#aaa886"))
    moss = _noise(nt, pos, 6.0, 5.0, 0.6)
    mm = nt.nodes.new("ShaderNodeMapRange")
    mm.inputs["From Min"].default_value = 0.56
    mm.inputs["From Max"].default_value = 0.64
    L.new(moss, mm.inputs["Value"])
    col = _mix(nt, _math(nt, "MULTIPLY", mm.outputs[0], 0.6), col, hexcol("#5f6e3a"))
    L.new(col, p.inputs["Base Color"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 70.0
    L.new(pos, vor.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.85
    bump.inputs["Distance"].default_value = 0.006
    L.new(_math(nt, "ADD", _math(nt, "MULTIPLY", vor.outputs["Distance"], 0.6), n1), bump.inputs["Height"])
    L.new(bump.outputs[0], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------- geometria

def meadow_mesh(r0=GROUND_IN - 0.01, r1=9.0, rings=90, seg=160):
    """Polárna sieť lúky: husto pri studni, riedko ďaleko."""
    bm = bmesh.new()
    grid = []
    for i in range(rings + 1):
        t = i / rings
        r = r0 * (r1 / r0) ** t
        row = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            x, y = r * math.cos(a), r * math.sin(a)
            row.append(bm.verts.new((x, y, ground_z(x, y))))
        grid.append(row)
    for i in range(rings):
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((grid[i][j], grid[i][k], grid[i + 1][k], grid[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("meadow")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new("meadow", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat_meadow())
    return ob


def tufts(n=19000, seed=21):
    """Trsy trávy v zábere kamery; pri venci hustejšie a vyššie (tam sa nekosí)."""
    rng = random.Random(seed)
    bm = bmesh.new()
    made = 0
    while made < n:
        x, y = rng.uniform(-VIEW, VIEW), rng.uniform(-VIEW, VIEW)
        r = math.hypot(x, y)
        if r < CROWN_OUT - 0.02:
            continue
        near = math.exp(-((r - CROWN_OUT) / 0.22) ** 2)  # 1 pri venci, 0 ďalej
        # ďalej od studne redšie a nižšie, v škvrnách
        patch = 0.5 + 0.5 * noise.noise(Vector((x * 1.3, y * 1.3, 9.1)))
        if rng.random() > 0.35 + 0.45 * patch + 0.6 * near:
            continue
        made += 1
        z0 = ground_z(x, y) - 0.01
        hmax = 0.07 + 0.06 * patch + 0.22 * near
        for _b in range(rng.randint(5, 11)):
            h = rng.uniform(0.35, 1.0) * hmax
            a = rng.random() * 2 * math.pi
            if near > 0.3 and rng.random() < 0.6:
                a = math.atan2(y, x) + rng.uniform(-0.9, 0.9)  # pri kameni sa steblá ohýbajú od neho
            lean = rng.uniform(0.15, 0.6)
            w = rng.uniform(0.0022, 0.0038)
            bx, by = x + rng.uniform(-0.02, 0.02), y + rng.uniform(-0.02, 0.02)
            dx, dy = math.cos(a), math.sin(a)
            px, py = -dy * w, dx * w
            prev = None
            for s in range(5):
                t = s / 4
                off = lean * h * t * t
                cx, cy, cz = bx + dx * off, by + dy * off, z0 + h * t * (1 - 0.25 * lean * t)
                ww = 1.0 - t * 0.9
                v1 = bm.verts.new((cx - px * ww, cy - py * ww, cz))
                v2 = bm.verts.new((cx + px * ww, cy + py * ww, cz))
                if prev:
                    bm.faces.new((prev[0], prev[1], v2, v1))
                prev = (v1, v2)
    me = bpy.data.meshes.new("tufts")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new("tufts", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat_grass())
    return ob


def crown_blocks(n=14, seed=5, gap=0.016, h=0.11):
    """Jeden rad ručne tesaných pieskovcových kvádrov: rôzne široké, vysoké aj dlhé, s hrubým vrchom."""
    rng = random.Random(seed)
    widths = [rng.uniform(0.75, 1.3) for _ in range(n)]
    tot = sum(widths)
    a = rng.random() * 2 * math.pi
    bm = bmesh.new()
    lay = bm.faces.layers.float.new("rand")
    K, R = 14, 6  # členenie po obvode a do šírky (pre hrubý povrch)
    for wdt in widths:
        span = 2 * math.pi * wdt / tot
        a0, a1 = a + gap / (2 * CROWN_IN), a + span - gap / (2 * CROWN_IN)
        a += span
        ri = CROWN_IN + rng.uniform(-0.01, 0.01)
        ro = CROWN_OUT + rng.uniform(-0.03, 0.025)
        zt = CROWN_TOP + rng.uniform(-0.015, 0.012)
        zb = zt - h
        tilt = rng.uniform(-0.008, 0.008)
        sd = rng.random() * 100
        rv = rng.random()
        top, bot = {}, {}
        for k in range(K + 1):
            ang = a0 + (a1 - a0) * k / K
            for j in range(R + 1):
                r = ri + (ro - ri) * j / R
                x, y = r * math.cos(ang), r * math.sin(ang)
                edge = min(k, K - k, j, R - j)
                rough = 0.0 if edge == 0 else 0.011 * noise.noise(Vector((x * 7, y * 7, sd))) + 0.004 * noise.noise(Vector((x * 23, y * 23, sd)))
                dz = tilt * (j / R - 0.5) + rough - (0.012 if edge == 0 else 0.0)  # otlčené hrany
                top[(k, j)] = bm.verts.new((x, y, zt + dz))
                bot[(k, j)] = bm.verts.new((x, y, zb))
        faces = []
        for k in range(K):
            for j in range(R):
                faces.append((top[(k, j)], top[(k + 1, j)], top[(k + 1, j + 1)], top[(k, j + 1)]))
                faces.append((bot[(k, j)], bot[(k, j + 1)], bot[(k + 1, j + 1)], bot[(k + 1, j)]))
            faces.append((bot[(k, 0)], bot[(k + 1, 0)], top[(k + 1, 0)], top[(k, 0)]))            # vnútro
            faces.append((bot[(k, R)], top[(k, R)], top[(k + 1, R)], bot[(k + 1, R)]))            # vonkajšok
        for j in range(R):
            faces.append((bot[(0, j)], top[(0, j)], top[(0, j + 1)], bot[(0, j + 1)]))
            faces.append((bot[(K, j)], bot[(K, j + 1)], top[(K, j + 1)], top[(K, j)]))
        for fv in faces:
            f = bm.faces.new(fv)
            f[lay] = rv
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("crown")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    try:
        me.set_sharp_from_angle(angle=math.radians(50))
    except Exception:
        pass
    ob = bpy.data.objects.new("crown", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def crown():
    """Jeden rad pieskovcových kvádrov na vrchu šachty, pod ním malta."""
    ob = crown_blocks()
    ob.data.materials.append(mat_crown())
    bed = anims.annulus("crown_bed", CROWN_IN + 0.012, CROWN_OUT - 0.035, CROWN_TOP - 0.04)
    sol = bed.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.08
    bed.data.materials.append(lib.mat_matte("crown_mortar", hexcol("#58554c"), 0.95))
    return ob


# ---------------------------------------------------------------- celé

def dress(sc):
    for name in ("cap", "ground"):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)
    meadow_mesh()
    tufts()
    crown()
    top = bpy.data.objects.get("opening")
    if top:
        # svetlo otvoru len do šachty: na tráve a venci by svietilo ako umelý kruh
        lib.only_light(top, [bpy.data.objects[n] for n in ("wall", "mortar", "water") if n in bpy.data.objects],
                       "shaft_only")
    return sc
