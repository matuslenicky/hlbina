"""Animácie pre web HLBINA (EEVEE na grafickej karte).

well   – zostup kamerou do studne, snímky 1..FRAMES (web ich prehráva podľa scrollu)
ripple – hladina na dne studne, kruhy po kvapke, slučka RIPPLE_FRAMES snímok
"""
import math
import random

import bpy
import bmesh
from mathutils import Vector

import lib
from lib import hexcol

FRAMES = 120
RIPPLE_FRAMES = 96
R_IN = 0.55        # vnútorný polomer šachty
Z_WATER = -13.6    # hladina
Z_CAM_END = -12.7  # kde kamera skončí (nadväzuje ripple)


# ---------------------------------------------------------------- render

def eevee(sc, w, h, samples=48):
    sc.render.engine = "BLENDER_EEVEE"
    e = sc.eevee
    e.taa_render_samples = samples
    for attr, val in (("use_raytracing", True), ("use_shadows", True), ("use_volumetric_shadows", True),
                      ("volumetric_start", 0.05), ("volumetric_end", 18.0), ("volumetric_tile_size", "4"),
                      ("volumetric_samples", 96), ("use_gtao", True), ("gtao_distance", 0.6),
                      ("fast_gi_distance", 0.8), ("shadow_ray_count", 2), ("shadow_step_count", 8)):
        if hasattr(e, attr):
            try:
                setattr(e, attr, val)
            except Exception as ex:  # noqa: BLE001
                print("eevee skip", attr, ex)
    try:
        e.ray_tracing_options.resolution_scale = "1"
        e.ray_tracing_options.screen_trace_quality = 0.5
    except Exception:
        pass
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.film_transparent = False


# ---------------------------------------------------------------- geometria

def masonry(name, r_in, z_top, z_bottom, seed=7, course=0.17, gap=0.014, depth=0.24):
    """Kamenné kvádre v prstencoch (vymurovaná šachta) ako jeden mesh.

    Plošný atribút "rand" (0..1) dáva každému kameňu iný odtieň.
    """
    rng = random.Random(seed)
    bm = bmesh.new()
    lay = bm.faces.layers.float.new("rand")
    z = z_top
    K = 6
    while z > z_bottom:
        h = course * rng.uniform(0.82, 1.2)
        n = max(9, int(2 * math.pi * r_in / rng.uniform(0.30, 0.42)))
        off = rng.random() * 2 * math.pi / n
        for i in range(n):
            a0 = off + 2 * math.pi * i / n + gap / (2 * r_in)
            a1 = off + 2 * math.pi * (i + 1) / n - gap / (2 * r_in)
            pr = rng.uniform(-0.012, 0.022)
            ri = r_in - pr
            ro = ri + depth
            zt, zb = z - gap / 2, z - h + gap / 2
            rv = rng.random()
            ring = {}
            for k in range(K + 1):
                a = a0 + (a1 - a0) * k / K
                bulge = math.sin(math.pi * k / K) * rng.uniform(0.0, 0.005)
                for side, r in (("i", ri - bulge), ("o", ro)):
                    for lvl, zz in (("t", zt), ("b", zb)):
                        jz = rng.uniform(-0.003, 0.003) if side == "i" else 0
                        ring[(k, side, lvl)] = bm.verts.new((r * math.cos(a), r * math.sin(a), zz + jz))
            faces = []
            for k in range(K):
                v = lambda kk, s_, l_: ring[(kk, s_, l_)]  # noqa: E731
                faces.append((v(k, "i", "b"), v(k, "i", "t"), v(k + 1, "i", "t"), v(k + 1, "i", "b")))  # vnútro
                faces.append((v(k, "o", "b"), v(k + 1, "o", "b"), v(k + 1, "o", "t"), v(k, "o", "t")))  # vonkajšok
                faces.append((v(k, "i", "t"), v(k, "o", "t"), v(k + 1, "o", "t"), v(k + 1, "i", "t")))  # vrch
                faces.append((v(k, "i", "b"), v(k + 1, "i", "b"), v(k + 1, "o", "b"), v(k, "o", "b")))  # spodok
            faces.append((ring[(0, "i", "b")], ring[(0, "o", "b")], ring[(0, "o", "t")], ring[(0, "i", "t")]))
            faces.append((ring[(K, "i", "b")], ring[(K, "i", "t")], ring[(K, "o", "t")], ring[(K, "o", "b")]))
            for fv in faces:
                f = bm.faces.new(fv)
                f[lay] = rv
        z -= h
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    bev = ob.modifiers.new("bevel", "BEVEL")
    bev.width = 0.008
    bev.segments = 2
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(35)
    try:
        me.set_sharp_from_angle(angle=math.radians(50))
    except Exception:
        pass
    return ob


def tube(name, r, z_top, z_bottom, seg=96, inward=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=seg, radius=r, depth=z_top - z_bottom,
                                        location=(0, 0, (z_top + z_bottom) / 2), end_fill_type="NOTHING")
    ob = bpy.context.active_object
    ob.name = name
    if inward:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    return ob


def annulus(name, r0, r1, z, seg=128):
    bm = bmesh.new()
    inner = [bm.verts.new((r0 * math.cos(2 * math.pi * i / seg), r0 * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)]
    outer = [bm.verts.new((r1 * math.cos(2 * math.pi * i / seg), r1 * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((inner[i], outer[i], outer[j], inner[j]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------- materiály

def mat_wellstone():
    """Kameň studne: odtieň podľa kameňa, hore suchý svetlý, dole tmavý a mokrý."""
    m, nt, out = lib._nodes("wellstone")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_type = "GEOMETRY"
    att.attribute_name = "rand"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#7a7468")
    ramp.color_ramp.elements[1].color = hexcol("#c4bdad")
    L.new(att.outputs["Fac"], ramp.inputs["Fac"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 16.0
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.62
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    nmix = nt.nodes.new("ShaderNodeMix")
    nmix.data_type = "RGBA"
    nmix.blend_type = "OVERLAY"
    nmix.inputs["Factor"].default_value = 0.7
    L.new(ramp.outputs["Color"], nmix.inputs["A"])
    L.new(noise.outputs["Fac"], nmix.inputs["B"])  # šedý šum, nie farebný
    # vlhkosť podľa hĺbky
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    wet = nt.nodes.new("ShaderNodeMapRange")
    wet.inputs["From Min"].default_value = -1.5
    wet.inputs["From Max"].default_value = -11.0
    L.new(sep.outputs["Z"], wet.inputs["Value"])
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.blend_type = "MULTIPLY"
    L.new(wet.outputs[0], dark.inputs["Factor"])
    L.new(nmix.outputs["Result"], dark.inputs["A"])
    dark.inputs["B"].default_value = hexcol("#4a5452")
    L.new(dark.outputs["Result"], p.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.82
    rough.inputs["To Max"].default_value = 0.28
    L.new(wet.outputs[0], rough.inputs["Value"])
    L.new(rough.outputs[0], p.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    bump.inputs["Distance"].default_value = 0.006
    L.new(noise.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs[0], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m


def mat_well_water(ripples=False):
    """Tmavá zrkadlová hladina; s ripples=True kruhy z kvapiek (bump z času)."""
    m, nt, out = lib._nodes("wellwater")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = hexcol("#05090a")
    p.inputs["Roughness"].default_value = 0.015
    p.inputs["IOR"].default_value = 1.333
    p.inputs["Specular IOR Level"].default_value = 0.9
    if ripples:
        h = ripple_height(nt)
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 1.0
        bump.inputs["Distance"].default_value = 0.012
        L.new(h, bump.inputs["Height"])
        L.new(bump.outputs[0], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m


def ripple_height(nt):
    """Výška hladiny: tri kvapky v strede posunuté o periódu -> bezšvová slučka."""
    L = nt.links
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    vlen = nt.nodes.new("ShaderNodeVectorMath")
    vlen.operation = "LENGTH"
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(sep.outputs["X"], comb.inputs["X"])
    L.new(sep.outputs["Y"], comb.inputs["Y"])
    L.new(comb.outputs[0], vlen.inputs[0])
    r = vlen.outputs["Value"]
    # čas v sekundách v rámci slučky (driver na snímku)
    tval = nt.nodes.new("ShaderNodeValue")
    tval.name = "time"
    fc = tval.outputs[0].driver_add("default_value")
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = f"((frame - 1) % {RIPPLE_FRAMES}) / 24.0"
    period = RIPPLE_FRAMES / 24.0
    speed, wl = 0.16, 0.045  # m/s, vlnová dĺžka
    total = None
    for k in range(3):
        age = nt.nodes.new("ShaderNodeMath")
        age.operation = "ADD"
        age.inputs[1].default_value = k * period
        L.new(tval.outputs[0], age.inputs[0])
        front = nt.nodes.new("ShaderNodeMath")  # polomer čela vlny
        front.operation = "MULTIPLY"
        front.inputs[1].default_value = speed
        L.new(age.outputs[0], front.inputs[0])
        d = nt.nodes.new("ShaderNodeMath")  # vzdialenosť za čelom
        d.operation = "SUBTRACT"
        L.new(front.outputs[0], d.inputs[0])
        L.new(r, d.inputs[1])
        ph = nt.nodes.new("ShaderNodeMath")
        ph.operation = "MULTIPLY"
        ph.inputs[1].default_value = 2 * math.pi / wl
        L.new(d.outputs[0], ph.inputs[0])
        wave = nt.nodes.new("ShaderNodeMath")
        wave.operation = "SINE"
        L.new(ph.outputs[0], wave.inputs[0])
        # obálka: len za čelom (d > 0), útlm za čelom a v čase
        inside = nt.nodes.new("ShaderNodeMapRange")
        inside.inputs["From Min"].default_value = -0.004
        inside.inputs["From Max"].default_value = 0.01
        L.new(d.outputs[0], inside.inputs["Value"])
        trail = nt.nodes.new("ShaderNodeMath")
        trail.operation = "MULTIPLY"
        trail.inputs[1].default_value = -9.0
        L.new(d.outputs[0], trail.inputs[0])
        etr = nt.nodes.new("ShaderNodeMath")
        etr.operation = "EXPONENT"
        L.new(trail.outputs[0], etr.inputs[0])
        tdec = nt.nodes.new("ShaderNodeMath")
        tdec.operation = "MULTIPLY"
        tdec.inputs[1].default_value = -0.55
        L.new(age.outputs[0], tdec.inputs[0])
        etd = nt.nodes.new("ShaderNodeMath")
        etd.operation = "EXPONENT"
        L.new(tdec.outputs[0], etd.inputs[0])
        env = nt.nodes.new("ShaderNodeMath")
        env.operation = "MULTIPLY"
        L.new(inside.outputs[0], env.inputs[0])
        L.new(etr.outputs[0], env.inputs[1])
        env2 = nt.nodes.new("ShaderNodeMath")
        env2.operation = "MULTIPLY"
        L.new(env.outputs[0], env2.inputs[0])
        L.new(etd.outputs[0], env2.inputs[1])
        hk = nt.nodes.new("ShaderNodeMath")
        hk.operation = "MULTIPLY"
        L.new(wave.outputs[0], hk.inputs[0])
        L.new(env2.outputs[0], hk.inputs[1])
        if total is None:
            total = hk.outputs[0]
        else:
            add = nt.nodes.new("ShaderNodeMath")
            add.operation = "ADD"
            L.new(total, add.inputs[0])
            L.new(hk.outputs[0], add.inputs[1])
            total = add.outputs[0]
    return total


# ---------------------------------------------------------------- scéna studne

def build_well(sc, ripples=False):
    stone = mat_wellstone()
    mortar = lib.mat_matte("mortar", hexcol("#3d3f3b"), 0.95)
    ground_m = lib.mat_stone(light="#e2ddd2", dark="#cfc7b8", scale=0.35)
    lib.world(sc, (0.82, 0.89, 0.96), 0.9)

    wall = masonry("wall", R_IN, 0.62, Z_WATER - 0.6, seed=11)
    wall.data.materials.append(stone)
    back = tube("mortar", R_IN + 0.035, 0.6, Z_WATER - 0.6)
    back.data.materials.append(mortar)
    # hlavica: kamenný veniec navrchu
    cap = annulus("cap", R_IN - 0.03, R_IN + 0.30, 0.64)
    sol = cap.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.06
    bev = cap.modifiers.new("bevel", "BEVEL")
    bev.width = 0.012
    bev.segments = 3
    cap.data.materials.append(ground_m)
    ground = annulus("ground", R_IN + 0.24, 9.0, 0.0)
    ground.data.materials.append(ground_m)

    water = lib.plane("water", (2 * R_IN + 0.2, 2 * R_IN + 0.2), (0, 0, Z_WATER))
    water.data.materials.append(mat_well_water(ripples))
    # zrkadlo pre hladinu (planárna sonda)
    pd = bpy.data.lightprobes.new("mirror", "PLANE")
    po = bpy.data.objects.new("mirror", pd)
    sc.collection.objects.link(po)
    po.location = (0, 0, Z_WATER + 0.001)
    po.scale = (R_IN + 0.1, R_IN + 0.1, 1)

    # svetlo: slnko zvonku (lúč do šachty) + mäkké svetlo otvoru
    sun = lib.sun_lamp("sun", (0.42, -0.25, 0.87), 5.5, 0.8, (1.0, 0.96, 0.9))
    top = lib.spot_light("opening", (0, 0, 0.9), (0, 0, -10), power=520, radius=0.45, angle=120, blend=1.0,
                         color=(0.85, 0.92, 1.0))
    # jemná hmla v šachte: viditeľný lúč
    vol_m, nt, out = lib._nodes("haze")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Density"].default_value = 0.035
    pv.inputs["Anisotropy"].default_value = 0.55
    pv.inputs["Color"].default_value = (0.9, 0.95, 1.0, 1)
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=R_IN - 0.02, depth=0.6 - Z_WATER,
                                        location=(0, 0, (0.6 + Z_WATER) / 2))
    haze = bpy.context.active_object
    haze.name = "haze"
    haze.data.materials.append(vol_m)
    return sun, top


def cam_down(sc, z, rot_deg, lens=24):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.02
    cd.clip_end = 60
    ob = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(ob)
    ob.location = (0, 0, z)
    ob.rotation_euler = (0, 0, math.radians(rot_deg))
    sc.camera = ob
    return ob


def smooth(t):
    return t * t * (3 - 2 * t)


def well(w=1080, h=1080, s=48):
    sc = lib.reset()
    eevee(sc, w, h, s)
    build_well(sc)
    cam = cam_down(sc, 2.4, 0)
    sc.frame_start, sc.frame_end = 1, FRAMES
    z0, z1 = 2.4, Z_CAM_END
    for f in range(1, FRAMES + 1):
        t = (f - 1) / (FRAMES - 1)
        e = smooth(t) * 0.75 + t * 0.25
        cam.location.z = z0 + (z1 - z0) * e
        cam.rotation_euler.z = math.radians(-55 * e)
        cam.keyframe_insert("location", index=2, frame=f)
        cam.keyframe_insert("rotation_euler", index=2, frame=f)
    try:
        for fc in cam.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    except Exception:
        pass
    sc.view_settings.exposure = 0.0
    return sc


def ripple(w=1080, h=1080, s=48):
    sc = lib.reset()
    eevee(sc, w, h, s)
    build_well(sc, ripples=True)
    cam_down(sc, Z_CAM_END, -55)
    sc.frame_start, sc.frame_end = 1, RIPPLE_FRAMES
    sc.render.fps = 24
    return sc


ANIMS = {
    "well": well,
    "ripple": ripple,
}


# ---------------------------------------------------------------- Cycles (EEVEE na Inteli zlyháva)

def to_cycles(sc, w, h, s):
    """Prepne hotovú scénu studne na Cycles; hmla a planárna sonda sú len pre EEVEE."""
    for n in ("haze", "mirror"):
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob)
    lib.cycles(sc, w, h, s, denoise=True, threshold=0.03)
    c = sc.cycles
    c.max_bounces = 8
    c.diffuse_bounces = 3
    c.glossy_bounces = 3
    c.transmission_bounces = 2
    c.volume_bounces = 0
    c.caustics_reflective = False
    c.caustics_refractive = False
    return sc


def well_c(w=1024, h=1024, s=24):
    return to_cycles(well(w, h, s), w, h, s)


def bottom_c(w=1024, h=1024, s=64):
    """Pokojná hladina na dne (podklad pre vlnky na webe)."""
    sc = lib.reset()
    eevee(sc, w, h, s)
    build_well(sc)
    cam_down(sc, Z_CAM_END, -55)
    return to_cycles(sc, w, h, s)


ANIMS.update({"well_c": well_c, "bottom_c": bottom_c})
