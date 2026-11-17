"""Krajina pod fľaše: Myjavská pahorkatina (Blender 5.2, Cycles).

Fľaša stojí na kameni na hrane lúky (počiatok súradníc, vrch kameňa z = 0). Kamera sa pozerá
na sever (+Y): za kameňom sa lúka láme do doliny s oparom, za ňou mäkké kopce s lesíkmi,
osamelými stromami a kopanicami so sadmi, na obzore modrastý hrebeň Bielych Karpát.

Opar (vzdušná perspektíva) je priamo v materiáloch krajiny: povrch sa podľa vzdialenosti
od kamery mieša s farbou oblohy v smere pohľadu. Funguje to aj v lomoch cez sklo.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector, noise

import lib
from lib import hexcol

# ---------------------------------------------------------------- nálady

MOODS = {
    # ráno: slnko nízko vľavo za fľašou, svieži opar v doline
    "morning": dict(
        sun_rot=-34.0, sun_elev=9.0, sun=6.5, sun_col=(1.0, 0.86, 0.68), sun_angle=0.9,
        air=1.0, aerosol=0.9, ozone=1.0, sky=0.085, fog_d=13000.0, mist=0.24, mist_col=1.08, fog_gain=0.9,
        fog_sat=0.7,
        exposure=-0.3,
    ),
    # podvečer: slnko tesne nad obzorom vpravo za fľašou
    "dusk": dict(
        sun_rot=31.0, sun_elev=3.6, sun=7.0, sun_col=(1.0, 0.56, 0.28), sun_angle=1.1,
        air=1.3, aerosol=1.3, ozone=1.0, sky=0.12, fog_d=13000.0, mist=0.20, mist_col=1.0, fog_gain=0.92,
        fog_sat=1.0, fill=5.0,
        exposure=0.15,
    ),
}


def to_sun(M):
    r, e = math.radians(M["sun_rot"]), math.radians(M["sun_elev"])
    return Vector((math.sin(r) * math.cos(e), math.cos(r) * math.cos(e), math.sin(e)))


def sky_node(nt, M):
    s = nt.nodes.new("ShaderNodeTexSky")
    s.sky_type = "MULTIPLE_SCATTERING"
    s.sun_disc = False
    s.sun_elevation = math.radians(M["sun_elev"])
    s.sun_rotation = math.radians(M["sun_rot"])
    s.altitude = 400.0
    s.air_density = M["air"]
    s.aerosol_density = M["aerosol"]
    s.ozone_density = M["ozone"]
    return s


def world_sky(sc, M):
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    s = sky_node(nt, M)
    nt.links.new(s.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = M["sky"]
    return w


def sun(M):
    return lib.sun_lamp("sun", to_sun(M), M["sun"], M["sun_angle"], M["sun_col"])


# ---------------------------------------------------------------- opar v materiáloch

def _math(nt, op, a=None, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def fogged(nt, surface, out, M, gain=1.0):
    """Zmieša povrch s farbou oblohy v smere pohľadu podľa vzdialenosti a výšky (opar v doline)."""
    L = nt.links
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    neg = nt.nodes.new("ShaderNodeVectorMath")
    neg.operation = "SCALE"
    neg.inputs["Scale"].default_value = -1.0
    L.new(geo.outputs["Incoming"], neg.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(neg.outputs[0], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(sep.outputs[0], comb.inputs[0])
    L.new(sep.outputs[1], comb.inputs[1])
    L.new(_math(nt, "MAXIMUM", sep.outputs[2], 0.02), comb.inputs[2])
    nrm = nt.nodes.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    L.new(comb.outputs[0], nrm.inputs[0])
    sk = sky_node(nt, M)
    L.new(nrm.outputs[0], sk.inputs["Vector"])
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = M.get("fog_sat", 1.0)
    L.new(sk.outputs[0], hs.inputs["Color"])
    em = nt.nodes.new("ShaderNodeEmission")
    L.new(hs.outputs[0], em.inputs["Color"])
    em.inputs["Strength"].default_value = M["sky"] * gain * M.get("fog_gain", 1.0)

    cam = nt.nodes.new("ShaderNodeCameraData")
    dist = cam.outputs["View Distance"]
    # vzdušná perspektíva: 1 - exp(-d / D)
    fog_d = _math(nt, "SUBTRACT", 1.0, _math(nt, "EXPONENT", _math(nt, "DIVIDE", dist, -M["fog_d"])))
    # opar v doline: silný pod -48 m, nad ňou rýchlo slabne, a až od pár stoviek metrov
    pos = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], pos.inputs[0])
    hz = _math(nt, "MAXIMUM", _math(nt, "DIVIDE", _math(nt, "SUBTRACT", pos.outputs[2], -50.0), 14.0), 0.0)
    mz = _math(nt, "EXPONENT", _math(nt, "MULTIPLY", hz, -1.0))
    md = _math(nt, "SUBTRACT", 1.0, _math(nt, "EXPONENT", _math(nt, "DIVIDE", dist, -650.0)))
    patch = nt.nodes.new("ShaderNodeTexNoise")
    patch.inputs["Scale"].default_value = 0.0028
    patch.inputs["Detail"].default_value = 3.0
    L.new(geo.outputs["Position"], patch.inputs["Vector"])
    pm = _math(nt, "MAXIMUM", _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", patch.outputs["Fac"], 0.25), 2.0), 0.15)
    mist = _math(nt, "MINIMUM", _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", mz, md), M["mist"]), pm), 0.92)
    # f = 1 - (1 - fog)(1 - mist)
    f = _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, fog_d), _math(nt, "SUBTRACT", 1.0, mist)))
    mix = nt.nodes.new("ShaderNodeMixShader")
    L.new(f, mix.inputs["Fac"])
    L.new(surface, mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])


# ---------------------------------------------------------------- terén

def _fbm(x, y, s, octaves=4, seed=0.0):
    v, a, f = 0.0, 1.0, 1.0
    for _ in range(octaves):
        v += a * noise.noise(Vector((x * f / s, y * f / s, seed)))
        a *= 0.5
        f *= 2.03
    return v


def _pol(yaw, d):
    """Bod v krajine zadaný uhlom od osi pohľadu (stupne, + vpravo) a vzdialenosťou."""
    a = math.radians(yaw)
    return d * math.sin(a), d * math.cos(a)


# kopce na druhej strane doliny: (uhol, vzdialenosť, výška nad dnom doliny, polomer x, polomer y)
HILLS = [
    (-10.0, 2100, 56, 650, 400),
    (3.0, 2300, 66, 750, 450),
    (-4.0, 1400, 38, 450, 280),
    (8.0, 1200, 34, 400, 250),
    (-22.0, 1600, 44, 600, 380),
    (15.0, 1800, 58, 650, 400),
    (-34.0, 2000, 70, 700, 420),
    (28.0, 2100, 66, 700, 420),
    (-16.0, 3000, 66, 900, 520),
    (11.0, 3300, 82, 900, 520),
]
HILLS_XY = [(*_pol(a, d), h, rx, ry) for a, d, h, rx, ry in HILLS]
FLOOR = -60.0


def height(x, y):
    """Výška terénu v metroch (vrch kameňa je 0)."""
    # náš kopec: hrebeň popri osi X, za kameňom sa láme do doliny na sever
    z = -0.27 + 0.03 * noise.noise(Vector((x * 0.9, y * 0.9, 1.7)))
    if y > 1.4:
        z += FLOOR * (1.0 - math.exp(-(y - 1.4) / 170.0))
        z += 4.0 * _fbm(x, y, 140.0, 3, 2.0) * min(1.0, (y - 1.4) / 60.0)
    else:
        z += min(-y, 400.0) * 0.012 + 2.0 * _fbm(x, y, 120.0, 3, 2.5) * min(1.0, -y / 40.0) if y < 0 else 0.0
    # kopce za dolinou
    for hx, hy, hh, rx, ry in HILLS_XY:
        dx, dy = (x - hx) / rx, (y - hy) / ry
        q = dx * dx + dy * dy
        if q < 9.0:
            z += hh * math.exp(-q * 1.1)
    # za kopcami mierne zdvihnutý terén a vrstvy hrebeňov, každý ďalší vyšší
    z += 10.0 * min(1.0, max(0.0, (y - 2600.0) / 1500.0))
    for y0, h0, amp, wid, xs, sd in RIDGES:
        z += _ridge(x, y, y0, h0, amp, wid, xs, sd)
    # drobné zvlnenie dna a svahov
    if y > 300:
        z += 6.0 * _fbm(x, y, 420.0, 3, 7.0)
    return z


# hrebene za dolinou: (vzdialenosť, výška, rozptyl výšky, šírka, mierka zvlnenia, semienko)
# posledný je hrebeň Bielych Karpát s Javorinou
RIDGES = [
    (4300.0, 120.0, 50.0, 900.0, 1400.0, 31.0),
    (7000.0, 330.0, 80.0, 1400.0, 2200.0, 37.0),
    (15000.0, 900.0, 150.0, 3600.0, 3400.0, 11.0),
]


def _ridge(x, y, y0, h0, amp, wid, xs, sd):
    yr = y0 + 0.09 * y0 * noise.noise(Vector((x / (xs * 1.6), 0.0, sd)))
    dr = (y - yr) / wid
    if abs(dr) > 3.0:
        return 0.0
    hr = h0 + amp * _fbm(x, 0.0, xs, 3, sd + 0.5)
    return hr * math.exp(-dr * dr * 1.4)


def forest(x, y, z):
    """0..1: kde rastie les (lesíky na kopcoch, súvislý les na hrebeni)."""
    if y < 800:
        return 0.0
    n = _fbm(x, y, 650.0, 3, 21.0)
    f = min(1.0, max(0.0, (n - 0.18) / 0.22))
    f *= min(1.0, max(0.0, (z - FLOOR - 25.0) / 30.0))  # nie na dne doliny
    if y > 3500:  # hrebene: lesy na vrchoch
        f = max(f, min(1.0, max(0.0, (z - 30.0) / 60.0)) * min(1.0, max(0.0, 0.6 + _fbm(x, y, 900.0, 2, 25.0))))
    if y > 11000:
        f = max(f, min(1.0, max(0.0, (z - 150.0) / 150.0)))
    return f


def terrain(M):
    """Polárna sieť okolo kameňa: hustá dopredu, riedka do strán a dozadu."""
    rings = 270
    r0, r1 = 0.35, 32000.0
    radii = [r0 * (r1 / r0) ** (i / (rings - 1)) for i in range(rings)]
    front = [math.radians(90 - 62 + 124 * i / 1000) for i in range(1000)]
    back_n = 260
    back = [math.radians(90 + 62 + (360 - 124) * (i + 1) / (back_n + 1)) for i in range(back_n)]
    angles = front + back
    na = len(angles)
    cos_a = [math.cos(a) for a in angles]
    sin_a = [math.sin(a) for a in angles]
    verts, fattr = [(0.0, 0.0, height(0.0, 0.0))], [0.0]
    for r in radii:
        for c, s in zip(cos_a, sin_a):
            x, y = r * c, r * s
            z = height(x, y)
            f = forest(x, y, z)
            verts.append((x, y, z + 17.0 * f))
            fattr.append(f)
    faces = []
    for k in range(na):
        faces.append((0, 1 + k, 1 + (k + 1) % na))
    for i in range(rings - 1):
        a0, b0 = 1 + i * na, 1 + (i + 1) * na
        for k in range(na):
            k2 = (k + 1) % na
            faces.append((a0 + k, b0 + k, b0 + k2, a0 + k2))
    me = bpy.data.meshes.new("terrain")
    me.from_pydata(verts, [], faces)
    at = me.attributes.new("forest", "FLOAT", "POINT")
    at.data.foreach_set("value", fattr)
    me.shade_smooth()
    ob = bpy.data.objects.new("terrain", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat_terrain(M))
    return ob


def mat_terrain(M):
    m, nt, out = lib._nodes("terrain")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = 0.95
    p.inputs["Specular IOR Level"].default_value = 0.25
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    # políčka: úzke pásy pozdĺž svahov (kopaničiarske parcely)
    fc = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(_math(nt, "DIVIDE", sep.outputs[0], 70.0), fc.inputs[0])
    L.new(_math(nt, "DIVIDE", sep.outputs[1], 210.0), fc.inputs[1])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.voronoi_dimensions = "2D"
    vor.inputs["Randomness"].default_value = 0.9
    L.new(fc.outputs[0], vor.inputs["Vector"])
    cell = nt.nodes.new("ShaderNodeSeparateColor")
    L.new(vor.outputs["Color"], cell.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    cols = [(0.0, "#5f8a3c"), (0.30, "#76944a"), (0.52, "#a39f5c"), (0.66, "#4f7a36"), (0.84, "#b0a466"), (0.94, "#7d6a4e")]
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = cols[0][0], hexcol(cols[0][1])
    el[1].position, el[1].color = cols[1][0], hexcol(cols[1][1])
    for pos, c in cols[2:]:
        e = el.new(pos)
        e.color = hexcol(c)
    L.new(cell.outputs[0], ramp.inputs["Fac"])
    # tráva: jemné škvrny a tóny (blízko kameňa)
    gn = nt.nodes.new("ShaderNodeTexNoise")
    gn.inputs["Scale"].default_value = 2.2
    gn.inputs["Detail"].default_value = 6.0
    gn.inputs["Roughness"].default_value = 0.62
    L.new(geo.outputs["Position"], gn.inputs["Vector"])
    gmix = nt.nodes.new("ShaderNodeMix")
    gmix.data_type = "RGBA"
    gmix.blend_type = "MULTIPLY"
    L.new(_math(nt, "MULTIPLY", gn.outputs["Fac"], 0.55), gmix.inputs["Factor"])
    L.new(ramp.outputs["Color"], gmix.inputs["A"])
    gmix.inputs["B"].default_value = hexcol("#8a9a63")
    # suchá tráva a kvety v blízkej lúke
    dn = nt.nodes.new("ShaderNodeTexNoise")
    dn.inputs["Scale"].default_value = 9.0
    dn.inputs["Detail"].default_value = 4.0
    L.new(geo.outputs["Position"], dn.inputs["Vector"])
    dry = nt.nodes.new("ShaderNodeMix")
    dry.data_type = "RGBA"
    L.new(_math(nt, "MULTIPLY", _math(nt, "MAXIMUM", _math(nt, "SUBTRACT", dn.outputs["Fac"], 0.55), 0.0), 2.6), dry.inputs["Factor"])
    L.new(gmix.outputs["Result"], dry.inputs["A"])
    dry.inputs["B"].default_value = hexcol("#b8ad7a")
    # les
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_type = "GEOMETRY"
    att.attribute_name = "forest"
    cn = nt.nodes.new("ShaderNodeTexNoise")
    cn.inputs["Scale"].default_value = 0.12
    cn.inputs["Detail"].default_value = 5.0
    L.new(geo.outputs["Position"], cn.inputs["Vector"])
    fcol = nt.nodes.new("ShaderNodeMix")
    fcol.data_type = "RGBA"
    L.new(cn.outputs["Fac"], fcol.inputs["Factor"])
    fcol.inputs["A"].default_value = hexcol("#22371f")
    fcol.inputs["B"].default_value = hexcol("#3f5a2f")
    fmix = nt.nodes.new("ShaderNodeMix")
    fmix.data_type = "RGBA"
    L.new(att.outputs["Fac"], fmix.inputs["Factor"])
    L.new(dry.outputs["Result"], fmix.inputs["A"])
    L.new(fcol.outputs["Result"], fmix.inputs["B"])
    L.new(fmix.outputs["Result"], p.inputs["Base Color"])
    # reliéf: tráva + koruny lesa
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.05
    hsum = _math(nt, "ADD", gn.outputs["Fac"], _math(nt, "MULTIPLY", cn.outputs["Fac"], att.outputs["Fac"]))
    L.new(hsum, bump.inputs["Height"])
    L.new(bump.outputs[0], p.inputs["Normal"])
    fogged(nt, p.outputs[0], out, M)
    return m


# ---------------------------------------------------------------- stromy a kopanice

def _blob(bm, center, radius, rng, sub=2):
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=radius)
    for v in res["verts"]:
        n = v.co.normalized()
        d = 1.0 + 0.22 * noise.noise(Vector(n * 2.2) + Vector((rng.random() * 50, 0, 0)))
        v.co = Vector(center) + n * radius * d


def tree_mesh(name, seed, crown="round"):
    """Listnatý strom s výškou 1 (mierka = výška v metroch): kmeň + koruna z niekoľkých gúľ."""
    rng = random.Random(seed)
    bm = bmesh.new()
    if crown == "round":
        _blob(bm, (0, 0, 0.58), 0.34, rng)
        for _ in range(6):
            a = rng.random() * 2 * math.pi
            _blob(bm, (0.24 * math.cos(a), 0.24 * math.sin(a), 0.40 + rng.random() * 0.32), 0.20 + rng.random() * 0.07, rng)
    else:  # štíhlejší, vyšší
        _blob(bm, (0, 0, 0.62), 0.26, rng)
        for _ in range(5):
            a = rng.random() * 2 * math.pi
            _blob(bm, (0.15 * math.cos(a), 0.15 * math.sin(a), 0.32 + rng.random() * 0.45), 0.17 + rng.random() * 0.05, rng)
    crown_faces = set(bm.faces)
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=0.035, radius2=0.02, depth=0.4)
    for v in res["verts"]:
        v.co.z += 0.17
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for i, poly in enumerate(me.polygons):
        poly.material_index = 0 if i < len(crown_faces) else 1
    me.shade_smooth()
    return me


def mat_foliage(M):
    m, nt, out = lib._nodes("foliage")
    L = nt.links
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.6
    L.new(geo.outputs["Position"], nz.inputs["Vector"])
    c = nt.nodes.new("ShaderNodeMix")
    c.data_type = "RGBA"
    L.new(nz.outputs["Fac"], c.inputs["Factor"])
    c.inputs["A"].default_value = hexcol("#2b4223")
    c.inputs["B"].default_value = hexcol("#56703a")
    L.new(c.outputs["Result"], d.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = hexcol("#6f8a35")
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = 0.3
    L.new(d.outputs[0], mx.inputs[1])
    L.new(tr.outputs[0], mx.inputs[2])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    L.new(nz.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs[0], d.inputs["Normal"])
    fogged(nt, mx.outputs[0], out, M)
    return m


def mat_fogged_matte(name, color, M, rough=0.9):
    m, nt, out = lib._nodes(name)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = hexcol(color)
    p.inputs["Roughness"].default_value = rough
    fogged(nt, p.outputs[0], out, M)
    return m


def place_trees(M, seed=4):
    rng = random.Random(seed)
    leaf, bark = mat_foliage(M), mat_fogged_matte("bark", "#3b3128", M)
    meshes = []
    for i in range(4):
        me = tree_mesh(f"tree{i}", 100 + i, "round" if i % 2 == 0 else "tall")
        me.materials.append(leaf)
        me.materials.append(bark)
        meshes.append(me)
    coll = bpy.data.collections.new("trees")
    bpy.context.scene.collection.children.link(coll)
    spots = []
    # osamelé stromy na lúkach (typické pre kopanice)
    for yaw, d, h in [(-18.0, 640, 15), (-9.5, 820, 17), (10.5, 700, 14), (-26.0, 760, 16), (19.0, 900, 15),
                      (-13.5, 1180, 16), (-6.5, 1560, 15), (-2.2, 980, 13), (4.6, 1320, 17), (6.8, 1900, 15),
                      (-9.0, 2250, 16), (-15.5, 1700, 14), (1.5, 1700, 14), (9.5, 1150, 12), (-19.0, 1050, 15)]:
        x, y = _pol(yaw, d)
        spots.append((x, y, h))
    # stromoradia popri medziach
    for (ya, da), (yb, db), n in [((-17, 1350), (-8, 1450), 22), ((-5, 1150), (3, 1100), 18),
                                  ((2, 1500), (10, 1620), 20), ((-12, 1900), (-4, 2050), 18),
                                  ((-24, 1250), (-18, 1300), 12), ((6, 2300), (13, 2350), 14)]:
        ax, ay = _pol(ya, da)
        bx, by = _pol(yb, db)
        for k in range(n):
            t = k / (n - 1)
            x = ax + (bx - ax) * t + rng.uniform(-6, 6)
            y = ay + (by - ay) * t + rng.uniform(-6, 6) + 25 * math.sin(t * 3.0)
            if rng.random() < 0.85:
                spots.append((x, y, rng.uniform(9, 16)))
    # stromy v doline a na svahoch, náhodne
    for _ in range(70):
        yaw, d = rng.uniform(-40, 40), rng.uniform(800, 2600)
        x, y = _pol(yaw, d)
        if forest(x, y, height(x, y)) > 0.1:
            continue
        spots.append((x, y, rng.uniform(8, 15)))
    # kopanice: dvorce so sadom
    farms = [(-6.0, 930), (5.2, 1420), (-14.5, 1120), (13.0, 1050), (-3.0, 1820)]
    for yaw, d in farms:
        fx, fy = _pol(yaw, d)
        for _ in range(16):
            a, rr = rng.random() * 2 * math.pi, rng.uniform(18, 55)
            spots.append((fx + rr * math.cos(a), fy + rr * math.sin(a), rng.uniform(5, 8)))
    for i, (x, y, h) in enumerate(spots):
        ob = bpy.data.objects.new(f"t{i}", meshes[i % len(meshes)])
        coll.objects.link(ob)
        ob.location = (x, y, height(x, y) - 0.3)
        ob.rotation_euler = (0, 0, rng.random() * 2 * math.pi)
        s = h * rng.uniform(0.9, 1.1)
        ob.scale = (s * rng.uniform(0.85, 1.15), s * rng.uniform(0.85, 1.15), s)
    houses(M, farms, rng)
    return coll


def houses(M, farms, rng):
    wall = mat_fogged_matte("wall", "#ece8de", M, 0.85)
    roof = mat_fogged_matte("roof", "#5b3d30", M, 0.7)
    for i, (yaw, d) in enumerate(farms):
        fx, fy = _pol(yaw, d)
        for j, (dx, dy, L_, W, H) in enumerate([(0, 0, 13, 7, 4.2), (16, 9, 10, 6, 3.6)]):
            x, y = fx + dx, fy + dy
            z = height(x, y)
            rot = rng.uniform(-0.3, 0.3)
            body = lib.box(f"house{i}_{j}", (L_, W, H), (x, y, z + H / 2 - 1.0), bevel=0, mat=wall)
            body.rotation_euler = (0, 0, rot)
            bm = bmesh.new()
            hw, hl, rh = W / 2 + 0.5, L_ / 2 + 0.5, 3.4
            vs = [bm.verts.new(c) for c in [(-hl, -hw, 0), (hl, -hw, 0), (hl, hw, 0), (-hl, hw, 0), (-hl, 0, rh), (hl, 0, rh)]]
            for f in [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5)]:
                bm.faces.new([vs[k] for k in f])
            me = bpy.data.meshes.new(f"roof{i}_{j}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(roof)
            ro = bpy.data.objects.new(f"roof{i}_{j}", me)
            bpy.context.scene.collection.objects.link(ro)
            ro.location = (x, y, z + H - 1.0)
            ro.rotation_euler = (0, 0, rot)


# ---------------------------------------------------------------- kameň

def _smin(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


def rock(name="rock", size=(0.42, 0.34, 0.50), center=(-0.06, 0.10), seed=3.0):
    """Pieskovcový balvan s rovným, mierne zvlneným vrchom v z = 0 (na ňom stoja fľaše)."""
    rx, ry, rz = size
    cz = -0.30
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=160, v_segments=80, radius=1.0)
    for v in bm.verts:
        n = v.co.copy()
        p = Vector((n.x * rx, n.y * ry, n.z * rz))
        # tvar balvana: nízkofrekvenčný šum pozdĺž normály
        d = 0.07 * noise.noise(n * 1.4 + Vector((seed, 0, 0))) + 0.035 * noise.noise(n * 3.9 + Vector((0, seed, 0)))
        d += 0.012 * noise.noise(n * 11.0 + Vector((0, 0, seed))) + 0.004 * noise.noise(n * 31.0 + Vector((seed, seed, 0)))
        dist = noise.voronoi(n * 3.2 + Vector((seed, 2 * seed, 0)), distance_metric="DISTANCE", exponent=2.5)[0]
        d += 0.035 * min(dist[1] - dist[0], 0.3)  # zaoblené fazety s ryhami medzi nimi
        p += n * d
        z = p.z + cz
        top = 0.0006 * noise.noise(Vector((p.x * 18, p.y * 18, seed)))
        z = _smin(z, top, 0.016)
        v.co = Vector((p.x + center[0], p.y + center[1], z))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat_rock())
    return ob


def mat_rock():
    """Svetlý flyšový pieskovec, zvetraný, so škvrnami lišajníkov."""
    m, nt, out = lib._nodes("rock")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = 0.82
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 6.0
    n1.inputs["Detail"].default_value = 10.0
    n1.inputs["Roughness"].default_value = 0.62
    L.new(tc.outputs["Object"], n1.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = hexcol("#a3967f")
    ramp.color_ramp.elements[1].position = 0.68
    ramp.color_ramp.elements[1].color = hexcol("#d4c8af")
    L.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    # lišajníky: sivé a bledožltozelené škvrny
    ln = nt.nodes.new("ShaderNodeTexNoise")
    ln.inputs["Scale"].default_value = 14.0
    ln.inputs["Detail"].default_value = 6.0
    L.new(tc.outputs["Object"], ln.inputs["Vector"])
    lm = nt.nodes.new("ShaderNodeMapRange")
    lm.inputs["From Min"].default_value = 0.60
    lm.inputs["From Max"].default_value = 0.66
    L.new(ln.outputs["Fac"], lm.inputs["Value"])
    lc = nt.nodes.new("ShaderNodeMix")
    lc.data_type = "RGBA"
    L.new(lm.outputs[0], lc.inputs["Factor"])
    L.new(ramp.outputs["Color"], lc.inputs["A"])
    lc.inputs["B"].default_value = hexcol("#b9b78f")
    ln2 = nt.nodes.new("ShaderNodeTexNoise")
    ln2.inputs["Scale"].default_value = 22.0
    ln2.inputs["Detail"].default_value = 6.0
    L.new(tc.outputs["Object"], ln2.inputs["Vector"])
    lm2 = nt.nodes.new("ShaderNodeMapRange")
    lm2.inputs["From Min"].default_value = 0.63
    lm2.inputs["From Max"].default_value = 0.67
    L.new(ln2.outputs["Fac"], lm2.inputs["Value"])
    lc2 = nt.nodes.new("ShaderNodeMix")
    lc2.data_type = "RGBA"
    L.new(_math(nt, "MULTIPLY", lm2.outputs[0], 0.35), lc2.inputs["Factor"])
    L.new(lc.outputs["Result"], lc2.inputs["A"])
    lc2.inputs["B"].default_value = hexcol("#d3cdbd")
    # pukliny: tmavé ryhy po hranách buniek
    crk = nt.nodes.new("ShaderNodeTexVoronoi")
    crk.feature = "DISTANCE_TO_EDGE"
    crk.inputs["Scale"].default_value = 11.0
    crk.inputs["Randomness"].default_value = 1.0
    cw = nt.nodes.new("ShaderNodeTexNoise")
    cw.inputs["Scale"].default_value = 4.0
    L.new(tc.outputs["Object"], cw.inputs["Vector"])
    warp = nt.nodes.new("ShaderNodeVectorMath")
    warp.operation = "MULTIPLY_ADD"
    warp.inputs[1].default_value = (0.06, 0.06, 0.06)
    L.new(cw.outputs["Color"], warp.inputs[0])
    L.new(tc.outputs["Object"], warp.inputs[2])
    L.new(warp.outputs[0], crk.inputs["Vector"])
    cm = nt.nodes.new("ShaderNodeMapRange")
    cm.inputs["From Min"].default_value = 0.0
    cm.inputs["From Max"].default_value = 0.012
    L.new(crk.outputs["Distance"], cm.inputs["Value"])
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.blend_type = "MULTIPLY"
    L.new(_math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, cm.outputs[0]), 0.10), dark.inputs["Factor"])
    L.new(lc2.outputs["Result"], dark.inputs["A"])
    dark.inputs["B"].default_value = hexcol("#5d554a")
    L.new(dark.outputs["Result"], p.inputs["Base Color"])
    # zrnitosť a jamky
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 90.0
    L.new(tc.outputs["Object"], vor.inputs["Vector"])
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 260.0
    fine.inputs["Detail"].default_value = 2.0
    L.new(tc.outputs["Object"], fine.inputs["Vector"])
    h = _math(nt, "ADD", _math(nt, "MULTIPLY", vor.outputs["Distance"], 0.6), _math(nt, "MULTIPLY", fine.outputs["Fac"], 0.5))
    h = _math(nt, "ADD", h, _math(nt, "MULTIPLY", n1.outputs["Fac"], 1.2))
    h = _math(nt, "ADD", h, _math(nt, "MULTIPLY", cm.outputs[0], 0.15))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    bump.inputs["Distance"].default_value = 0.002
    L.new(h, bump.inputs["Height"])
    L.new(bump.outputs[0], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------- tráva pri kameni

def grass_tufts(n=5000, seed=11, region=((-1.0, 0.9), (-1.2, 1.1)), exclude=None):
    """Steblá trávy okolo kameňa (len tam, kde ich kamera vidí)."""
    rng = random.Random(seed)
    bm = bmesh.new()
    for _ in range(n):
        x = rng.uniform(*region[0])
        y = rng.uniform(*region[1])
        if exclude and exclude(x, y):
            continue
        z0 = height(x, y) - 0.01
        for _b in range(rng.randint(6, 12)):
            h = rng.uniform(0.07, 0.24)
            a = rng.random() * 2 * math.pi
            lean = rng.uniform(0.1, 0.5)
            w = rng.uniform(0.0025, 0.004)
            bx, by = x + rng.uniform(-0.02, 0.02), y + rng.uniform(-0.02, 0.02)
            dx, dy = math.cos(a), math.sin(a)
            px, py = -dy * w, dx * w
            segs = 4
            prev = None
            for s in range(segs + 1):
                t = s / segs
                off = lean * h * t * t
                cx, cy, cz = bx + dx * off, by + dy * off, z0 + h * t
                ww = 1.0 - t * 0.9
                v1 = bm.verts.new((cx - px * ww, cy - py * ww, cz))
                v2 = bm.verts.new((cx + px * ww, cy + py * ww, cz))
                if prev:
                    bm.faces.new((prev[0], prev[1], v2, v1))
                prev = (v1, v2)
    me = bpy.data.meshes.new("grass")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new("grass", me)
    bpy.context.scene.collection.objects.link(ob)
    m, nt, out = lib._nodes("grass")
    L = nt.links
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    L.new(geo.outputs["Position"], nz.inputs["Vector"])
    c = nt.nodes.new("ShaderNodeMix")
    c.data_type = "RGBA"
    L.new(nz.outputs["Fac"], c.inputs["Factor"])
    c.inputs["A"].default_value = hexcol("#66783f")
    c.inputs["B"].default_value = hexcol("#ada676")
    L.new(c.outputs["Result"], d.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = hexcol("#a2aa63")
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = 0.4
    L.new(d.outputs[0], mx.inputs[1])
    L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])
    del oi
    me.materials.append(m)
    return ob


# ---------------------------------------------------------------- celá krajina

def build(sc, mood="morning", grass=True):
    M = MOODS[mood]
    world_sky(sc, M)
    sun(M)
    terrain(M)
    place_trees(M)
    rk = rock()

    def under_rock(x, y):
        return ((x + 0.06) / 0.40) ** 2 + ((y - 0.10) / 0.33) ** 2 < 1.0

    if grass:
        grass_tufts(exclude=under_rock)
    # odrazová doska za kamerou: jemne zdvihne tieňovú stranu kameňa a fliaš
    fill = lib.area_light("fill", (0.6, -2.6, 0.55), (0, 0, 0.12), size=(1.2, 1.2), power=M.get("fill", 9.0),
                          color=(1.0, 0.95, 0.88))
    fill.visible_camera = False
    # doska len svieti: inak sa zrkadlí v skle a vode ako svetlé obdĺžniky za nápisom
    fill.visible_glossy = False
    fill.visible_transmission = False
    sc.view_settings.exposure = M["exposure"]
    return M, rk
