"""Spoločné stavebné kamene pre zábery HLBINA (Blender 5.2, Cycles)."""
import math
import os

import bpy
from mathutils import Vector

from spec import BOTTLES

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- scéna

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    return sc


DEVICE = os.environ.get("HLBINA_DEVICE", "CPU")


def cycles(sc, w, h, samples=256, denoise=True, threshold=0.01):
    sc.render.engine = "CYCLES"
    c = sc.cycles
    if DEVICE == "CUDA":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "CUDA"
        c.device = "GPU"
    else:
        c.device = "CPU"
        sc.render.threads_mode = "AUTO"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = threshold
    c.use_denoising = denoise
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.max_bounces = 32
    c.diffuse_bounces = 4
    c.glossy_bounces = 12
    c.transmission_bounces = 32
    c.transparent_max_bounces = 16
    c.volume_bounces = 1
    c.caustics_reflective = True
    c.caustics_refractive = True
    c.blur_glossy = 0.6
    c.sample_clamp_indirect = 8.0
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"


def world(sc, color=(0.9, 0.93, 0.95), strength=0.5):
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*color, 1)
    bg.inputs[1].default_value = strength
    return w


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def camera(sc, loc, target, lens=85, fit="AUTO", fstop=None, focus=None, shift=(0, 0)):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cd.sensor_width = 36
    cd.sensor_fit = fit
    cd.shift_x, cd.shift_y = shift
    cd.clip_start = 0.01
    cd.clip_end = 60000
    ob = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus if focus else (Vector(target) - Vector(loc)).length
    sc.camera = ob
    return ob


def area_light(name, loc, target, size=(1, 1), power=100, color=(1, 1, 1), spread=180):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size
    ld.energy = power
    ld.color = color
    ld.spread = math.radians(spread)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


def spot_light(name, loc, target, power=500, radius=0.02, angle=40, blend=0.3, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "SPOT")
    ld.energy = power
    ld.shadow_soft_size = radius
    ld.spot_size = math.radians(angle)
    ld.spot_blend = blend
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


def sun_lamp(name, to_sun, strength=4.0, angle=1.0, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = strength
    ld.angle = math.radians(angle)
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    d = Vector(to_sun).normalized()
    ob.location = d * 3
    look_at(ob, (0, 0, 0))
    return ob


def gobo(center, to_sun, hole=(0.5, 0.42), size=3.0, bars=()):
    """Okno pre slnko: veľká doska s otvorom (a priečkami), vidno ju len v tieňoch.

    bars: zoznam (os, poloha, hrúbka) v rovine okna, os "x" = zvislá priečka.
    """
    n = Vector(to_sun).normalized()
    root = bpy.data.objects.new("gobo", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = center
    root.rotation_euler = n.to_track_quat("Z", "Y").to_euler()
    hw, hh = hole[0] / 2, hole[1] / 2
    rects = [(-size, hh, size, size), (-size, -size, size, -hh), (-size, -hh, -hw, hh), (hw, -hh, size, hh)]
    for ax, pos, th in bars:
        if ax == "x":
            rects.append((pos - th / 2, -hh, pos + th / 2, hh))
        else:
            rects.append((-hw, pos - th / 2, hw, pos + th / 2))
    for i, (x0, y0, x1, y1) in enumerate(rects):
        me = bpy.data.meshes.new(f"gobo{i}")
        me.from_pydata([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new(f"gobo{i}", me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = root
        for a in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter"):
            setattr(ob, a, False)
    return root


def only_light(light_ob, receivers, name):
    """Svetlo osvetľuje len vymenované objekty (light linking)."""
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    for ob in receivers:
        coll.objects.link(ob)
    for co in coll.collection_objects:
        co.light_linking.link_state = "INCLUDE"
    light_ob.light_linking.receiver_collection = coll
    return coll


def only_block(light_names_skip, blockers):
    """Svetlá okrem vymenovaných ignorujú tieň od blockers (shadow linking)."""
    coll = bpy.data.collections.new("gobo_set")
    bpy.context.scene.collection.children.link(coll)
    for ob in blockers:
        coll.objects.link(ob)
    for co in coll.collection_objects:
        co.light_linking.link_state = "EXCLUDE"
    coll.hide_render = False
    for ob in bpy.context.scene.objects:
        if ob.type == "LIGHT" and ob.name not in light_names_skip:
            ob.light_linking.blocker_collection = coll


def caustics(light=None, casters=(), receivers=()):
    """Tieňové kaustiky (MNEE). Názvy vlastností sa medzi verziami menili."""
    def setp(targets, names, val):
        for t in targets:
            for n in names:
                if hasattr(t, n):
                    setattr(t, n, val)
                    break
    if light is not None:
        setp([light.data.cycles, light.data], ["is_caustics_light", "use_shadow_caustics"], True)
    setp([o.cycles for o in casters] + list(casters), ["is_caustics_caster"], True)
    setp([o.cycles for o in receivers] + list(receivers), ["is_caustics_receiver"], True)


def hide_from_camera(ob):
    ob.visible_camera = False


# ---------------------------------------------------------------- geometria

def bez(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        m = 1 - t
        out.append((
            m ** 3 * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t ** 3 * p3[0],
            m ** 3 * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t ** 3 * p3[1],
        ))
    return out


def arc(cx, cz, r, a0, a1, n):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def line(p0, p1, n):
    return [(p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n) for i in range(n + 1)]


def join(*parts):
    """Spojí úseky profilu, vynechá zdvojené body na stykoch. Vráti body + značku úseku."""
    pts, tags = [], []
    for tag, seg in parts:
        for p in seg:
            if pts and abs(pts[-1][0] - p[0]) < 1e-7 and abs(pts[-1][1] - p[1]) < 1e-7:
                continue
            pts.append(p)
            tags.append(tag)
    return pts, tags


def revolve(name, prof, tags=None, seg=192, uv_h=1.0, outer_tag="outer", smooth_angle=32):
    """Otočí profil (r, z) okolo osi Z. Profil proti smeru hodín = normály von.

    Na plochách nastaví UV (u = uhol, v = z / uv_h) a plošný atribút "outer"
    (1 tam, kde je úsek profilu označený outer_tag).
    """
    verts, rows = [], []
    for r, z in prof:
        if r < 1e-7:
            rows.append([len(verts)])
            verts.append((0.0, 0.0, z))
        else:
            row = []
            for s in range(seg):
                a = 2 * math.pi * s / seg
                row.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rows.append(row)
    faces, fuv, fout = [], [], []
    for i in range(len(prof) - 1):
        A, B = rows[i], rows[i + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        za, zb = prof[i][1] / uv_h, prof[i + 1][1] / uv_h
        o = 1.0 if tags and tags[i + 1] == outer_tag and tags[i] == outer_tag else 0.0
        for s in range(seg):
            s2 = (s + 1) % seg
            u0, u1 = s / seg, (s + 1) / seg
            if len(A) == 1:
                faces.append((A[0], B[s2], B[s]))
                fuv.append([((u0 + u1) / 2, za), (u1, zb), (u0, zb)])
            elif len(B) == 1:
                faces.append((A[s], A[s2], B[0]))
                fuv.append([(u0, za), (u1, za), ((u0 + u1) / 2, zb)])
            else:
                faces.append((A[s], A[s2], B[s2], B[s]))
                fuv.append([(u0, za), (u1, za), (u1, zb), (u0, zb)])
            fout.append(o)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    li = 0
    for poly, uvs in zip(me.polygons, fuv):
        for k, li in enumerate(poly.loop_indices):
            uvl.data[li].uv = uvs[k]
    at = me.attributes.new("outer", "FLOAT", "FACE")
    at.data.foreach_set("value", fout)
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    except Exception:
        pass
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bottle_profiles(b):
    """Prierez skla (uzavretý) a vody pre fľašu so špecifikáciou b."""
    R, w, base, punt = b["R"], b["wall"], b["base"], b["punt"]
    hb, hs, ht, rn = b["h_body"], b["h_sh"], b["h_top"], b["r_neck"]
    ri = R - w
    rni = rn - w * 1.05
    fr = 0.0075  # zaoblenie spodnej hrany
    ring = R * 0.72  # na čom fľaša stojí
    k = hs - hb

    # vonkajšok: od stredu dna (preliačina) von, hore, rameno, hrdlo, okraj
    bottom = [(ring * t, punt * (0.5 + 0.5 * math.cos(math.pi * t))) for t in [i / 24 for i in range(25)]]
    o_bottom = bottom + line((ring, 0), (R - fr, 0), 6)[1:]
    o_fillet = arc(R - fr, fr, fr, -90, 0, 14)
    o_wall = line((R, fr), (R, hb), 60)
    o_sh = bez((R, hb), (R, hb + k * 0.40), (rn, hs - k * 0.62), (rn, hs), 80)  # dlhé mäkké plecia
    lip0 = ht - 0.0062
    o_neck = line((rn, hs), (rn, lip0), 10)
    bead = 0.0016
    o_lip = (bez((rn, lip0), (rn + bead, lip0), (rn + bead, lip0 + 0.0008), (rn + bead, lip0 + 0.0018), 8)
             + line((rn + bead, lip0 + 0.0018), (rn + bead, ht - 0.0014), 4)[1:]
             + arc(rn + bead - 0.0014, ht - 0.0014, 0.0014, 0, 90, 8)[1:])
    o_top = line((rn + bead - 0.0014, ht), (rni + 0.0008, ht), 4)
    i_top = arc(rni + 0.0008, ht - 0.0008, 0.0008, 90, 180, 6)
    # vnútro: dole hrdlom, rameno, stena, dno s kupolou
    i_neck = line((rni, ht - 0.0008), (rni, hs + w * 0.4), 14)
    i_sh = bez((rni, hs + w * 0.4), (rni, hs - k * 0.60), (ri, hb + k * 0.42), (ri, hb + w * 0.25), 80)
    fri = 0.006
    i_wall = line((ri, hb + w * 0.25), (ri, base + fri), 60)
    i_fillet = arc(ri - fri, base + fri, fri, 0, -90, 14)
    dome = 0.004
    i_bottom = [((ri - fri) * (1 - t), base + dome * (0.5 - 0.5 * math.cos(math.pi * t))) for t in [i / 20 for i in range(21)]]

    glass, tags = join(
        ("bottom", o_bottom), ("bottom", o_fillet), ("outer", o_wall), ("outer", o_sh),
        ("neck", o_neck), ("neck", o_lip), ("neck", o_top),
        ("in", i_top), ("in", i_neck), ("in", i_sh), ("in", i_wall), ("in", i_fillet), ("in", i_bottom),
    )

    # voda: tesne väčšia než dutina (prekrytie so sklom), hore rovná hladina
    f = b["fill"]
    grow = 0.00025
    water_side = [(r + grow, z) for (r, z) in list(reversed(i_bottom))[:-1] + list(reversed(i_fillet)) + list(reversed(i_wall)) + list(reversed(i_sh))]
    water_side = [(r, z) for (r, z) in water_side if z <= f]
    # dorovnaj presne k hladine
    r_at_f = water_side[-1][0]
    water, wtags = join(
        ("w", [(0.0, base + dome * 0.0 - 0.0001)]),
        ("w", water_side),
        ("w", [(r_at_f, f)]),
        ("w", line((r_at_f, f), (0.0, f), 10)),
    )
    return glass, tags, water


def bottle(key, loc=(0, 0, 0), rot_z=0.0, mats=None, seg=192):
    """Postaví fľašu (sklo + voda + zátka) ako skupinu pod prázdnym objektom."""
    b = BOTTLES[key]
    mats = mats or {}
    root = bpy.data.objects.new(f"{key}_root", None)
    bpy.context.scene.collection.objects.link(root)
    glass_p, tags, water_p = bottle_profiles(b)
    g = revolve(f"{key}_glass", glass_p, tags, seg=seg, uv_h=b["h_top"])
    wtr = revolve(f"{key}_water", water_p, None, seg=seg, uv_h=b["h_top"], smooth_angle=60)
    # zátka: valček v hrdle + hlava s oblým vrchom
    rn, ht = b["r_neck"], b["h_top"]
    rni = rn - b["wall"] * 1.05
    plug_r = rni - 0.0002
    cap_r = rn + 0.0032
    cap_h = 0.024 if key == "b75" else 0.021
    cp = join(
        ("c", [(0.0, ht - 0.019)]),
        ("c", line((plug_r - 0.0006, ht - 0.019), (plug_r, ht - 0.0184), 2)),
        ("c", line((plug_r, ht - 0.0184), (plug_r, ht + 0.0012), 6)),
        ("c", line((plug_r, ht + 0.0012), (cap_r - 0.0012, ht + 0.0012), 4)),
        ("c", arc(cap_r - 0.0012, ht + 0.0024, 0.0012, -90, 0, 6)),
        ("c", line((cap_r, ht + 0.0024), (cap_r, ht + cap_h - 0.006), 10)),
        ("c", arc(cap_r - 0.006, ht + cap_h - 0.006, 0.006, 0, 90, 16)),
        ("c", line((cap_r - 0.006, ht + cap_h), (0.0, ht + cap_h), 6)),
    )[0]
    cap = revolve(f"{key}_cap", cp, None, seg=seg, uv_h=1.0, smooth_angle=40)
    for ob, m in ((g, "glass_" + key), (wtr, "water"), (cap, "wood")):
        if m in mats:
            ob.data.materials.append(mats[m])
        ob.parent = root
    root.location = loc
    root.rotation_euler = (0, 0, rot_z)
    return root, g, wtr, cap


def box(name, size, loc, bevel=0.003, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        m = ob.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = 4
        m.limit_method = "NONE"
    bpy.ops.object.shade_smooth()
    if mat:
        ob.data.materials.append(mat)
    return ob


def cyclorama(name, width=8, depth=4, height=3, radius=0.8, z0=0.0, y_back=1.5, mat=None):
    """Podlaha prechádzajúca oblúkom do steny (fotografické pozadie)."""
    prof = line((-depth, z0), (y_back - radius, z0), 8)
    prof += arc(y_back - radius, z0 + radius, radius, -90, 0, 24)[1:]
    prof += line((y_back, z0 + radius), (y_back, z0 + height), 6)[1:]
    verts, faces = [], []
    nx = 2
    for j, (y, z) in enumerate(prof):
        for i in range(nx):
            x = -width / 2 + width * i / (nx - 1)
            verts.append((x, y, z))
    for j in range(len(prof) - 1):
        a, b = j * nx, (j + 1) * nx
        faces.append((a, a + 1, b + 1, b))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def plane(name, size, loc, rot=(0, 0, 0), mat=None):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    if mat:
        ob.data.materials.append(mat)
    return ob


# ---------------------------------------------------------------- materiály

def _nodes(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def hexcol(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


CAUSTIC_GAIN = 1.15
CAUSTIC_BASE = 0.04
CAUSTIC_POW = 6.0


def mat_glass(key, tint=(0.985, 1.0, 0.996), absorb=(0.90, 0.975, 0.965), density=5.0):
    """Číre sklo s pieskovaným nápisom podľa masky (UV) len na vonkajšej stene."""
    m, nt, out = _nodes("glass_" + key)
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*tint, 1)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["IOR"].default_value = 1.52
    p.inputs["Roughness"].default_value = 0.0
    tex = nt.nodes.new("ShaderNodeTexImage")
    path = os.path.join(HERE, "tex", f"label_{key}.png")
    tex.image = bpy.data.images.load(path)
    tex.image.colorspace_settings.name = "Non-Color"
    tex.interpolation = "Cubic"
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_type = "GEOMETRY"
    att.attribute_name = "outer"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    L.new(tex.outputs["Color"], mul.inputs[0])
    L.new(att.outputs["Fac"], mul.inputs[1])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.0
    rough.inputs["To Max"].default_value = 0.42
    L.new(mul.outputs[0], rough.inputs["Value"])
    L.new(rough.outputs[0], p.inputs["Roughness"])
    frost = nt.nodes.new("ShaderNodeBsdfDiffuse")
    frost.inputs["Color"].default_value = (0.92, 0.95, 0.95, 1)
    fmix = nt.nodes.new("ShaderNodeMath")
    fmix.operation = "MULTIPLY"
    fmix.inputs[1].default_value = 0.32
    L.new(mul.outputs[0], fmix.inputs[0])
    mix = nt.nodes.new("ShaderNodeMixShader")
    L.new(fmix.outputs[0], mix.inputs["Fac"])
    L.new(p.outputs[0], mix.inputs[1])
    L.new(frost.outputs[0], mix.inputs[2])
    # Tieňové lúče: sklo prepúšťa svetlo, stredom fľaše ho "zaostrí" (falošná kaustika),
    # okraje tmavnú. Vnútorné steny sú pre tieň priehľadné.
    lp = nt.nodes.new("ShaderNodeLightPath")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    L.new(lw.outputs["Facing"], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = CAUSTIC_POW
    L.new(inv.outputs[0], pw.inputs[0])
    ma = nt.nodes.new("ShaderNodeMath")
    ma.operation = "MULTIPLY_ADD"
    ma.inputs[1].default_value = CAUSTIC_GAIN
    ma.inputs[2].default_value = CAUSTIC_BASE
    L.new(pw.outputs[0], ma.inputs[0])
    tm = nt.nodes.new("ShaderNodeMix")
    tm.data_type = "FLOAT"
    tm.inputs["A"].default_value = 1.0
    L.new(att.outputs["Fac"], tm.inputs["Factor"])
    L.new(ma.outputs[0], tm.inputs["B"])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    L.new(tm.outputs["Result"], comb.inputs[0])
    L.new(tm.outputs["Result"], comb.inputs[1])
    L.new(tm.outputs["Result"], comb.inputs[2])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    L.new(comb.outputs[0], tr.inputs["Color"])
    smix = nt.nodes.new("ShaderNodeMixShader")
    L.new(lp.outputs["Is Shadow Ray"], smix.inputs["Fac"])
    L.new(mix.outputs[0], smix.inputs[1])
    L.new(tr.outputs[0], smix.inputs[2])
    L.new(smix.outputs[0], out.inputs["Surface"])
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (*absorb, 1)
    vol.inputs["Density"].default_value = density
    L.new(vol.outputs[0], out.inputs["Volume"])
    return m


def mat_water():
    m, nt, out = _nodes("water")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (1, 1, 1, 1)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["IOR"].default_value = 1.333
    p.inputs["Roughness"].default_value = 0.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    sm = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], sm.inputs["Fac"])
    nt.links.new(p.outputs[0], sm.inputs[1])
    nt.links.new(tr.outputs[0], sm.inputs[2])
    nt.links.new(sm.outputs[0], out.inputs["Surface"])
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (0.95, 0.985, 1.0, 1)
    vol.inputs["Density"].default_value = 1.5
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return m


def mat_wood():
    """Dub: letokruhy pozdĺž výšky, jemná textúra."""
    m, nt, out = _nodes("wood")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = 0.52
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (60, 60, 6)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 3.0
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 3.0
    wave.inputs["Detail Scale"].default_value = 1.5
    L.new(mp.outputs[0], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol("#946f48")
    ramp.color_ramp.elements[1].color = hexcol("#bf9a6c")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[1].position = 0.75
    L.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], p.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    L.new(wave.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs[0], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m


def mat_stone(light="#e8e3d9", dark="#d6cebf", scale=1.0):
    """Travertín: jemné pásy, póry, matný povrch."""
    m, nt, out = _nodes("stone")
    L = nt.links
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = 0.58
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.2 * scale, 6 * scale, 6 * scale)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.6
    L.new(mp.outputs[0], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexcol(dark)
    ramp.color_ramp.elements[1].color = hexcol(light)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.62
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    # póry
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 160.0 * scale
    vor.inputs["Randomness"].default_value = 1.0
    L.new(tc.outputs["Object"], vor.inputs["Vector"])
    pr = nt.nodes.new("ShaderNodeMapRange")
    pr.inputs["From Min"].default_value = 0.0
    pr.inputs["From Max"].default_value = 0.09
    pr.inputs["To Min"].default_value = 0.0
    pr.inputs["To Max"].default_value = 1.0
    L.new(vor.outputs["Distance"], pr.inputs["Value"])
    pn = nt.nodes.new("ShaderNodeTexNoise")
    pn.inputs["Scale"].default_value = 18.0 * scale
    L.new(tc.outputs["Object"], pn.inputs["Vector"])
    pm = nt.nodes.new("ShaderNodeMapRange")
    pm.inputs["From Min"].default_value = 0.52
    pm.inputs["From Max"].default_value = 0.62
    L.new(pn.outputs["Fac"], pm.inputs["Value"])
    pores = nt.nodes.new("ShaderNodeMath")  # 1 = bez póru, menej = pór
    pores.operation = "MAXIMUM"
    L.new(pr.outputs[0], pores.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    L.new(pm.outputs[0], inv.inputs[1])
    L.new(inv.outputs[0], pores.inputs[1])
    darken = nt.nodes.new("ShaderNodeMix")
    darken.data_type = "RGBA"
    darken.blend_type = "MULTIPLY"
    L.new(pores.outputs[0], darken.inputs["Factor"])
    darken.inputs["B"].default_value = (1, 1, 1, 1)
    darken.inputs["A"].default_value = hexcol("#b9ad98")
    mix2 = nt.nodes.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    mix2.blend_type = "MULTIPLY"
    mix2.inputs["Factor"].default_value = 1.0
    L.new(ramp.outputs["Color"], mix2.inputs["A"])
    L.new(darken.outputs["Result"], mix2.inputs["B"])
    L.new(mix2.outputs["Result"], p.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.0006
    L.new(pores.outputs[0], bump.inputs["Height"])
    L.new(bump.outputs[0], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m


def mat_matte(name, color, rough=0.9):
    m, nt, out = _nodes(name)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = color if len(color) == 4 else (*color, 1)
    p.inputs["Roughness"].default_value = rough
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    return m


def mat_emit(name, color=(1, 1, 1), strength=1.0):
    m, nt, out = _nodes(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    return m
