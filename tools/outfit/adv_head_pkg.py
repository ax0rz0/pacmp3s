"""The donor head package (Song So Mi, Cyberpunk 2077: Phantom Liberty, workshop 3283215678) for the Ethics Assistant (femsuit_04), shared by every outfit that swaps the head.

head_parts(stage) -> (materials, parts): the `neck skin` material part and three model parts
  * `neck`           : a skin coloured neck (adv_neck.py, OBJ on the neck bone).  The player's own neck is part of her head skin slot (1 chau_facemap) and goes with it; the donor's own neck is
                       a wide flat flange that ends in two pointed wings.
  * `Song So Mi head`: the donor, bone-merged on the head bone; every slot but the head slots is null, the hair slots too; a clip2 cuts the flange away with a plane that passes under the chin
                       and rises towards the back of the head (the neck column flares up to meet it).
  * `Song So Mi hair`: a second bone-merged copy that only draws Scalp + Hair, NOT clipped, so the bob hangs to its natural length.
The entity2 of the outfit has to hide the player's head slots: HEAD_SLOTS_NULL (1 chau_facemap, 2 eyeball_l, 3 eyeball_r, 4 fmouth).
The $color2 tints of the donor's materials (hair 2.5, lipstick a dark rose, cyberware 0.1) are applied by the game itself.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adv_neck
import adv_parts as ap
import adv_scene as asn

DONOR_MODEL = 'models/cyberpunk2077rex/songsomirex/song_so_mi_pm.mdl'
# donor material slots (1-based, .mdl texture order): Head 1, EyeL 2, EyeR 3, Cyberware 4, EyeBrows 5, EyeLashes 6, EyeMakeup 7, Body 8, Lipstick 9, Mouth 10, Nails 11, Pimples 12, Port 13, Decals 14,
# PortEmissive 15, PortScrews 16, PortSillicone 17, PortSilliconeShadow 18, Shoes 19, Scalp 20, Hair 21, Suit 22, Deck 23, Emissive 24, DeckMetalBits 25, Screen 26, Clothes 27, Stitches 28, ClothesMetal 29
DONOR_SLOTS = 29
DONOR_NULL = (8, 11, 14, 19, 22, 23, 24, 25, 26, 27, 28, 29)       # everything that is not head
HAIR_SLOTS = (20, 21)                                              # Scalp, Hair
HEAD_SLOTS_NULL = (1, 2, 3, 4)                                     # the player's chau_facemap (head + neck), eyeball_l, eyeball_r, fmouth
N_SLOTS = 21                                                       # entity2 Materials entries of the player model
SKIN = (0.52, 0.40, 0.34)                                          # mean of the donor's Head_c texture on the jaw / neck stump
CLIP_X = -1.5                                                      # head-local height of the cut under the skull at the clip's Position (head bone X = up, tilted 10 deg forward)
CLIP_Y = -2.0                                                      # ... which sits this far from the middle of the head (- = towards the face)
CLIP_YAW = -15.0                                                   # a negative yaw tilts the plane so that it rises towards the back of the head


def head_materials(extra_null=()):
    """entity2 Materials with the player's head slots hidden (and optionally more slots, 1-based)"""
    s = [''] * N_SLOTS
    for i in tuple(HEAD_SLOTS_NULL) + tuple(extra_null):
        s[i - 1] = 'null'
    return ';'.join(s)


def donor_materials(null, keep=None):
    s = [''] * DONOR_SLOTS
    if keep is not None:
        s = ['null'] * DONOR_SLOTS
        for i in keep:
            s[i - 1] = ''
    for i in null:
        s[i - 1] = 'null'
    return ';'.join(s)


def donor_model(name, materials, clip=False):
    head = ap.bone_name('Head1')
    m = ap.model(name, DONOR_MODEL, head, color=(1, 1, 1), material='', bonemerge=True, extra={'Materials': materials})
    m['self'].pop('ForceObjUrl', None)
    m['self'].pop('Material', None)
    if clip:
        m['children'] = {1: ap.clip('neck clip', head, (CLIP_X, CLIP_Y, 0.0), (0, CLIP_YAW, 0))}
    return m


def head_parts(stage):
    """-> (materials, parts); the neck OBJ is written into `stage` (an ap.Stage)"""
    sc = asn.Scene()
    neck_url = stage.obj('neck', ap.to_bone_local(sc.rig, 'Neck1', adv_neck.build_neck()), 'skin neck for the donor head swap', smooth_deg=60)
    mats = [ap.material3d('neck skin', 'models/debug/debugwhite', color=SKIN, halflambert=True, phong=True, phongboost=0.4, phongexponent=12, phongfresnelranges=(0.1, 0.5, 1.0))]
    neck = ap.model('neck', neck_url, ap.bone_name('Neck1'), color=(1, 1, 1), material='neck skin')
    head = donor_model('Song So Mi head', donor_materials(null=tuple(DONOR_NULL) + tuple(HAIR_SLOTS)), clip=True)
    hair = donor_model('Song So Mi hair', donor_materials(null=(), keep=HAIR_SLOTS))
    return mats, [neck, head, hair]
