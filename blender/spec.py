# Rozmery fliaš v metroch (bez bpy, používa aj make_labels.py).
# Verzia 2 (11. 11. 2026): ťažké hrubé dno, dlhšie mäkké plecia, kratšie hrdlo,
# dolu vypieskovaný pás kopcov Myjavskej pahorkatiny.
BOTTLES = {
    "b75": dict(
        R=0.0400,       # vonkajší polomer tela
        wall=0.0034,    # hrúbka steny
        base=0.026,     # hrúbka dna (ťažké sklo)
        punt=0.0040,    # výška preliačiny v dne
        h_body=0.184,   # kde začína rameno
        h_sh=0.247,     # kde začína hrdlo
        h_top=0.282,    # vrch hrdla
        r_neck=0.0150,  # vonkajší polomer hrdla
        fill=0.226,     # hladina vody
        size="0,75 l",
        word_h=0.094,   # výška zvislého nápisu
        word_z=0.080,   # spodok zvislého nápisu
        band=0.046,     # stredná výška pásu kopcov
    ),
    "b33": dict(
        R=0.0330,
        wall=0.0030,
        base=0.020,
        punt=0.0035,
        h_body=0.128,
        h_sh=0.176,
        h_top=0.205,
        r_neck=0.0140,
        fill=0.160,
        size="0,33 l",
        word_h=0.060,
        word_z=0.062,
        band=0.036,
    ),
}

LABEL_W = 4096  # šírka masky = celý obvod fľaše
