"""Netrunner with a donor head (Song So Mi, Cyberpunk 2077: Phantom Liberty, workshop 3283215678): her head is bone-merged onto the Ethics Assistant's head bone, the Ethics Assistant's own head
slots are nulled, and the respirator / implant / headset are re-fitted to HER face.  Hair: her own."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import adv_head_obj as ho
import adv_parts as ap
import adv_scene as asn
import make_adv_net as man
import run_donor_preview as rdp
from ethics_acc import Surface

import adv_head_pkg as hp

DONOR_MODEL = hp.DONOR_MODEL
DONOR_NULL = hp.DONOR_NULL
PLAYER_HEAD_SLOTS = hp.HEAD_SLOTS_NULL


def build_custom(write=True):
    d, tr, P, N = rdp.load()
    sel = np.isin(tr['slot'], [d.tex.index(n) for n in ('Head', 'Lipstick', 'Mouth', 'Cyberware', 'EyeMakeup', 'Pimples')])
    sh = ho.HEAD_SHIFT                                       # the head package sits on her neck: every landmark below moves with it (the numbers are the donor's own, measured unshifted)
    S_d = Surface(P[sel] + sh)
    sc = asn.Scene()
    rig = sc.rig
    head = ap.bone_name('Head1')
    # landmark heights: femsuit -> donor (chin bottom, lip line, nose tip, eye line, forehead)
    v_src = [60.25, 62.3, 63.6, 65.1, 67.5]
    v_dst = [61.0 + sh[2], 62.6 + sh[2], 64.0 + sh[2], 65.36 + sh[2], 67.6 + sh[2]]
    kw = dict(head_surface=S_d, axis_xy=(-0.6 + sh[0], 0.0 + sh[1]), warp=(v_src, v_dst), cup_x=-1.0 + sh[0], cup_y=4.7, cup_z=64.9 + sh[2], arc_top=72.2 + sh[2], eye_u=-1.33, eye_v=65.12 + sh[2],
              act_smooth=5, act_dilate=4, max_dev=2.2, inflate=0.4, filter_v=62.7 + sh[2])
    # the donor head package (skin neck, head clipped under the skull, unclipped hair - see adv_head_pkg.py) replaces the plain bone-merged donor of the first version
    mats, head_parts = hp.head_parts(ap.Stage(man.STAGE_DIR, 'hd'))
    text, tree, st, errs, counts = man.build('custom', head_kw=kw, extra_head_parts=head_parts, extra_materials=mats, with_hair=False, null_slots=hp.HEAD_SLOTS_NULL, write=write)
    return text, tree, st, errs, counts, kw, S_d


if __name__ == '__main__':
    text, tree, st, errs, counts, kw, S_d = build_custom()
    print('%d bytes' % len(text))
    for fn, (nv, nt, sz) in st.files.items():
        print('  %-24s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
