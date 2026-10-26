"""Netrunner with a donor head (Song So Mi, Cyberpunk 2077: Phantom Liberty, workshop 3283215678): her head is bone-merged onto the Ethics Assistant's head bone, the Ethics Assistant's own head
slots are nulled, and the respirator / implant / headset are re-fitted to HER face.  Hair: her own."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import adv_parts as ap
import adv_scene as asn
import make_adv_net as man
import run_donor_preview as rdp
from ethics_acc import Surface

DONOR_MODEL = 'models/cyberpunk2077rex/songsomirex/song_so_mi_pm.mdl'
# donor material slots (1-based, .mdl texture order): Head 1, EyeL 2, EyeR 3, Cyberware 4, EyeBrows 5, EyeLashes 6, EyeMakeup 7, Body 8, Lipstick 9, Mouth 10, Nails 11, Pimples 12, Port 13, Decals 14,
# PortEmissive 15, PortScrews 16, PortSillicone 17, PortSilliconeShadow 18, Shoes 19, Scalp 20, Hair 21, Suit 22, Deck 23, Emissive 24, DeckMetalBits 25, Screen 26, Clothes 27, Stitches 28, ClothesMetal 29
DONOR_NULL = (8, 11, 14, 19, 22, 23, 24, 25, 26, 27, 28, 29)
PLAYER_HEAD_SLOTS = (1, 2, 3, 4)       # chau_facemap, eyeball_l, eyeball_r, fmouth


def donor_materials_string(n=29):
    s = [''] * n
    for i in DONOR_NULL:
        s[i - 1] = 'null'
    return ';'.join(s)


def build_custom(write=True):
    d, tr, P, N = rdp.load()
    sel = np.isin(tr['slot'], [d.tex.index(n) for n in ('Head', 'Lipstick', 'Mouth', 'Cyberware', 'EyeMakeup', 'Pimples')])
    S_d = Surface(P[sel])
    sc = asn.Scene()
    rig = sc.rig
    head = ap.bone_name('Head1')
    # landmark heights: femsuit -> donor (chin bottom, lip line, nose tip, eye line, forehead)
    v_src = [60.25, 62.3, 63.6, 65.1, 67.5]
    v_dst = [61.0, 62.6, 64.0, 65.36, 67.6]
    kw = dict(head_surface=S_d, axis_xy=(-0.6, 0.0), warp=(v_src, v_dst), cup_x=-1.0, cup_y=4.7, cup_z=64.9, arc_top=72.2, eye_u=-1.33, eye_v=65.12, act_smooth=5, act_dilate=4, max_dev=2.2, inflate=0.4, filter_v=62.7)
    donor = ap.model('Song So Mi head', DONOR_MODEL, head, color=(1, 1, 1), material='', bonemerge=True, extra={'Materials': donor_materials_string()})
    donor['self'].pop('ForceObjUrl', None)
    donor['self'].pop('Material', None)
    # clip the donor's neck flare: everything below a plane through (x -2.5, z 61.2) is hidden (the plane normal is the head bone's X axis = up)
    plane = tuple(ap.local_point(rig, 'Head1', (-2.5, 0.0, 61.2)))
    donor['children'] = {1: ap.clip('neck clip', head, plane, (0, 0, 0))}
    text, tree, st, errs, counts = man.build('custom', head_kw=kw, extra_head_parts=[donor], with_hair=False, null_slots=PLAYER_HEAD_SLOTS, write=write)
    return text, tree, st, errs, counts, kw, S_d


if __name__ == '__main__':
    text, tree, st, errs, counts, kw, S_d = build_custom()
    print('%d bytes' % len(text))
    for fn, (nv, nt, sz) in st.files.items():
        print('  %-24s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
