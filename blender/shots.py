"""Zábery pre web HLBINA. Každá funkcia postaví celú scénu a vráti ju.

Verzia 2: fľaše stoja na pieskovcovom balvane na hrane lúky v Myjavskej pahorkatine
(krajina v land.py), za nimi dolina s oparom a kopce. Pôvodné štúdiové zábery sú
v test/shots_studio_v1.py.
"""
import bpy

import land
import lib


def bottle_mats():
    return {
        "glass_b75": lib.mat_glass("b75"),
        "glass_b33": lib.mat_glass("b33"),
        "water": lib.mat_water(),
        "wood": lib.mat_wood(),
    }


def outdoor(sc, w, h, samples):
    lib.cycles(sc, w, h, samples, threshold=0.015)
    c = sc.cycles
    c.max_bounces = 24
    c.diffuse_bounces = 3
    c.glossy_bounces = 8
    c.transmission_bounces = 20
    c.caustics_reflective = False
    c.caustics_refractive = False


def hero(variant="d", w=1920, h=1080, samples=256, mood="morning"):
    sc = lib.reset()
    outdoor(sc, w, h, samples)
    land.build(sc, mood)
    lib.bottle("b75", (0, 0, 0), 0.0, bottle_mats(), seg=256)
    if variant == "d":
        lib.camera(sc, (0.0, -1.15, 0.18), (-0.135, 0, 0.16), lens=50, fstop=8, focus=1.15)
    else:  # na výšku, fľaša dole, hore obloha na text
        lib.camera(sc, (0.0, -1.42, 0.306), (0.0, 0, 0.239), lens=50, fit="VERTICAL", fstop=8, focus=1.42)
    return sc


def detail(variant="d", w=1920, h=1080, samples=256):
    """Detail pásu kopcov vypieskovaného do skla, za ním skutočné kopce v rozmazaní."""
    sc = lib.reset()
    outdoor(sc, w, h, samples)
    land.build(sc, "morning")
    lib.bottle("b75", (0, 0, 0), 0.0, bottle_mats(), seg=320)
    if variant == "d":
        lib.camera(sc, (0.0, -0.62, 0.055), (0.054, 0, 0.07), lens=70, fstop=11, focus=0.58)
    else:
        lib.camera(sc, (0.0, -0.62, 0.06), (0.0, 0, 0.095), lens=70, fit="VERTICAL", fstop=11, focus=0.58)
    return sc


def duo(variant="d", w=1920, h=1080, samples=256):
    """Obe veľkosti vedľa seba."""
    sc = lib.reset()
    outdoor(sc, w, h, samples)
    land.build(sc, "morning")
    mats = bottle_mats()
    lib.bottle("b75", (0.055, 0.02, 0), 0.0, mats, seg=256)
    lib.bottle("b33", (-0.06, -0.045, 0), 0.0, mats, seg=256)
    if variant == "d":
        lib.camera(sc, (0.0, -1.1, 0.17), (0.0, 0, 0.15), lens=50, fstop=8, focus=1.1)
    else:
        lib.camera(sc, (0.0, -1.40, 0.29), (0.0, 0, 0.225), lens=50, fit="VERTICAL", fstop=8, focus=1.40)
    return sc


SHOTS = {
    "hero": lambda w, h, s: hero("d", w, h, s),
    "hero_m": lambda w, h, s: hero("m", w, h, s),
    "dusk": lambda w, h, s: hero("d", w, h, s, mood="dusk"),
    "dusk_m": lambda w, h, s: hero("m", w, h, s, mood="dusk"),
    "detail": lambda w, h, s: detail("d", w, h, s),
    "detail_m": lambda w, h, s: detail("m", w, h, s),
    "duo": lambda w, h, s: duo("d", w, h, s),
    "duo_m": lambda w, h, s: duo("m", w, h, s),
}
