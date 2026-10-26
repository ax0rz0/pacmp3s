"""The custom head package for the Ethics Assistant (femsuit_04), shared by every outfit that swaps the head: the Song So Mi head (Cyberpunk 2077: Phantom Liberty, Workshop 3283215678) as plain
GitHub-hosted assets - nothing needs the Workshop addon, pac downloads the meshes and textures itself (see adv_head_obj.py for how they are made).

head_parts(stage) -> (materials, parts): three `material_3d` parts (url textures) and the model parts
  * `neck`          : a neck on the neck bone (adv_neck.py) that borrows a patch of the head texture.  The player's own neck lives in her head slot (1 chau_facemap) and goes with it; the donor head
                      has no neck below the jaw.
  * `head skin`     : hd_head.obj  (the donor's Head slot cut under the skull + the eyeballs)         material `hd skin`   (hd_head.jpg)
  * `face extras`   : hd_extras.obj (lipstick, eye makeup, brows, cyberware, lashes, nape port)        material `hd extras` (hd_extras.png, translucent)
  * `hair 1..3`     : hd_hair_a..c.obj (alpha tested cards, no culling)                                material `hd hair`   (hd_hair.png)
All on the head bone in the head bone's own frame (rigid).  The entity2 of the outfit has to hide the player's head slots: HEAD_SLOTS_NULL (1 chau_facemap, 2 eyeball_l, 3 eyeball_r, 4 fmouth).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import adv_head_obj as ho
import adv_neck
import adv_parts as ap
import adv_scene as asn

# legacy (the bone-merged version of the first package): the donor's material slots, 1-based, .mdl texture order
DONOR_MODEL = 'models/cyberpunk2077rex/songsomirex/song_so_mi_pm.mdl'
DONOR_NULL = (8, 11, 14, 19, 22, 23, 24, 25, 26, 27, 28, 29)       # everything that is not head
HEAD_SLOTS_NULL = (1, 2, 3, 4)                                     # the player's chau_facemap (head + neck), eyeball_l, eyeball_r, fmouth
N_SLOTS = 21                                                       # entity2 Materials entries of the player model
TEX_RAW = ap.REPO_RAW + 'tex/adv/'
OBJ_RAW = ap.REPO_RAW + 'obj/adv/'


def head_materials(extra_null=()):
    """entity2 Materials with the player's head slots hidden (and optionally more slots, 1-based)"""
    s = [''] * N_SLOTS
    for i in tuple(HEAD_SLOTS_NULL) + tuple(extra_null):
        s[i - 1] = 'null'
    return ';'.join(s)


def head_parts(stage):
    """-> (materials, parts); the neck, head, extras, eyes and hair OBJs and their textures are written under stage.root (an ap.Stage)"""
    sc = asn.Scene()
    r = ho.build(stage.root)
    for k, fn in r['obj'].items():
        stage.files[fn] = (r['stats'][k][0], r['stats'][k][1], r['stats'][k][2])
    neck = adv_neck.build_neck()
    u0, v0 = r['nape_uv']
    neck.UV = np.column_stack([u0 + 0.012 * (neck.UV[:, 0] - 0.5), v0 + 0.012 * (neck.UV[:, 1] - 0.5)])       # a 12 texel patch of plain skin from the head texture
    neck_url = stage.obj('neck_b', ap.to_bone_local(sc.rig, 'Neck1', neck), 'skin neck for the custom head (uvs: a patch of hd_head.jpg)', smooth_deg=60)          # neck_b: the first hd_neck.obj had no uvs
    tex = {k: TEX_RAW + fn for k, fn in r['tex'].items()}
    obj = {k: OBJ_RAW + fn for k, fn in r['obj'].items()}
    mats = [
        ap.material3d('hd skin', tex['head'], halflambert=True, phong=True, phongboost=0.3, phongexponent=24, phongfresnelranges=(0.1, 0.6, 1.0)),
        ap.material3d('hd extras', tex['extras'], halflambert=True, translucent=True),
        ap.material3d('hd hair', tex['hair'], halflambert=True, alphatest=True, alphatestreference=0.2, nocull=True),
    ]
    head = ap.bone_name('Head1')
    parts = [
        ap.model('neck', neck_url, ap.bone_name('Neck1'), material='hd skin'),
        ap.model('head skin', obj['head'], head, material='hd skin'),
        ap.model('face extras', obj['extras'], head, material='hd extras', translucent=True),
    ]
    hairs = sorted(k for k in obj if k.startswith('hair_'))
    for i, k in enumerate(hairs):
        parts.append(ap.model('hair %d' % (i + 1), obj[k], head, material='hd hair'))
    return mats, parts
