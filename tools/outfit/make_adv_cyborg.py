"""Outfit #4: Ethics Assistant - Protocol Unit (cyborg).  Left half of the face is a chrome endoskeleton (glowing eye lens, exposed steel teeth, piston), neck collar with hoses, a heavy left arm
(pauldron, elbow ball, gauntlet, hand plate) and a back reactor with cooling fins, exhaust vents (steam) and cables.
Console:  pac_proxy cb_theme <0..3>   accent colour: 0 amber, 1 red, 2 cyan, 3 green"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import adv_common as ac
import adv_cyborg as cb
import adv_geom as ag
import adv_panels as pn
import adv_parts as ap
import adv_scene as asn
import pac_write as pw

STAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
OUT_DIR = os.path.join(STAGE_DIR, 'outfits')
FILE = 'ethics asst protocol unit'
TITLE = 'Ethics Assistant - Protocol Unit (cyborg)'
PALETTE = [(1.0, 0.58, 0.12), (1.0, 0.16, 0.10), (0.15, 0.85, 1.0), (0.30, 1.0, 0.35)]


def build(stage_dir=STAGE_DIR, write=True):
    ap.reset_uids()
    sc = asn.Scene()
    rig = sc.rig
    parts, ctx = cb.build_cyborg(sc)
    st = ap.Stage(stage_dir, 'cb')
    arm = ctx['arm']

    def loc(key, bone):
        return ap.to_bone_local(rig, bone, parts[key]['mesh'])

    url = dict(
        face_chrome=st.obj('face_chrome', loc('face_chrome', 'Head1'), 'left half face: chrome plates, steel teeth, bolts', smooth_deg=42),
        face_dark=st.obj('face_dark', loc('face_dark', 'Head1'), 'left half face: dark mechanism layer', smooth_deg=40),
        face_glow=st.obj('face_glow', loc('face_glow', 'Head1'), 'left half face: lens, LEDs, split line', smooth_deg=60),
        collar=st.obj('collar', loc('collar', 'Neck1'), 'neck collar and hoses', smooth_deg=45),
        upper_chrome=st.obj('upper_chrome', loc('upper_chrome', 'L_UpperArm'), 'pauldron, upper arm plates, elbow ball', smooth_deg=42),
        upper_glow=st.obj('upper_glow', loc('upper_glow', 'L_UpperArm'), 'upper arm glow seams, elbow ring', smooth_deg=60),
        fore_chrome=st.obj('fore_chrome', loc('fore_chrome', 'L_Forearm'), 'forearm gauntlet', smooth_deg=42),
        fore_glow=st.obj('fore_glow', loc('fore_glow', 'L_Forearm'), 'forearm glow seams', smooth_deg=60),
        hand_chrome=st.obj('hand_chrome', loc('hand_chrome', 'L_Hand'), 'hand plate', smooth_deg=42),
        hand_glow=st.obj('hand_glow', loc('hand_glow', 'L_Hand'), 'hand glow lines', smooth_deg=60),
        back_body=st.obj('back_body', loc('back_body', 'Spine2'), 'back reactor housing, fins, vents, cables', smooth_deg=42),
        back_glow=st.obj('back_glow', loc('back_glow', 'Spine2'), 'back reactor core + seams', smooth_deg=60),
    )

    def theme(scale, pulse='1'):
        return ac.theme_expr('cb_theme', PALETTE, scale, pulse)

    pulse = '(0.8 + 0.2*sin(time()*2.4))'
    mats = [
        ap.material3d('cb chrome', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=4.5, phongexponent=64, phongfresnelranges=(0.2, 0.9, 1.0), envmap='env_cubemap',
                      envmaptint=(0.5, 0.52, 0.58)),
        ap.material3d('cb gun', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=3.0, phongexponent=24, phongfresnelranges=(0.2, 0.8, 1.0), envmap='env_cubemap',
                      envmaptint=(0.2, 0.21, 0.24)),
        ap.material3d('cb dark', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=1.0, phongexponent=12, phongfresnelranges=(0.1, 0.5, 1.0)),
    ]
    M = ap.model

    def glow(nm, key, bone, scale=1.0, kids=()):
        return M(nm, url[key], bone, color=PALETTE[0], nolight=True, children=[ap.proxy('cb_theme', 'Color', theme(scale, pulse))] + list(kids))

    head, neck = ap.bone_name('Head1'), ap.bone_name('Neck1')
    ua, fa, ha = ap.bone_name('L_UpperArm'), ap.bone_name('L_Forearm'), ap.bone_name('L_Hand')
    sp2 = ap.bone_name('Spine2')
    face = [
        M('face chrome', url['face_chrome'], head, color=(0.82, 0.85, 0.92), material='cb chrome'),
        M('face mechanism', url['face_dark'], head, color=(0.09, 0.095, 0.11), material='cb dark'),
        glow('face glow', 'face_glow', head),
        M('neck collar', url['collar'], neck, color=(0.26, 0.27, 0.31), material='cb gun'),
    ]
    arm_parts = [
        M('pauldron + upper arm', url['upper_chrome'], ua, color=(0.82, 0.85, 0.92), material='cb chrome'),
        glow('upper arm glow', 'upper_glow', ua),
        M('gauntlet', url['fore_chrome'], fa, color=(0.82, 0.85, 0.92), material='cb chrome'),
        glow('gauntlet glow', 'fore_glow', fa),
        M('hand plate', url['hand_chrome'], ha, color=(0.82, 0.85, 0.92), material='cb chrome'),
        glow('hand glow', 'hand_glow', ha),
    ]
    back = [
        M('reactor housing', url['back_body'], sp2, color=(0.4, 0.41, 0.46), material='cb gun'),
        glow('reactor core', 'back_glow', sp2, scale=1.25),
    ]

    # glow sprites + steam
    def spr(nm, bone_short, p_world, size_xy, alpha):
        return ap.sprite(nm, ap.bone_name(bone_short), tuple(ap.local_point(rig, bone_short, p_world)), (255, 150, 30), size_xy=size_xy, alpha=alpha)

    S = ctx['surf']
    lens_p, _ = S.pt(np.array([1.45]), np.array([65.12]), np.array([0.85]))
    sp = [spr('eye lens glow', 'Head1', lens_p[0], (2.4, 2.4), 0.8),
          spr('reactor glow', 'Spine2', ctx['back_centre'] + np.array([-2.2, 0.0, 0.3]), (7.0, 7.0), 0.75),
          spr('elbow glow', 'L_Forearm', arm['elbow'], (3.2, 3.2), 0.5),
          spr('ear glow', 'Head1', np.array([-0.3, 4.4, 65.2]), (2.6, 2.6), 0.4)]
    sprites = ap.proxy('cb_theme', 'Color', ac.theme_expr('cb_theme', PALETTE, 255.0, pulse), affect_children=True, children=sp)
    steam = []
    for i, vpos in enumerate(ctx['vents']):
        steam.append(ap.particles('exhaust steam %d' % (i + 1), sp2, tuple(ap.local_point(rig, 'Spine2', vpos)), material='particle/smokesprites_0001', start_size=1.4, end_size=6.0, color1=(215, 218, 225),
                                  color2=(215, 218, 225), start_alpha=70, end_alpha=0, die_time=1.7, fire_delay=0.11, number=1, velocity=14.0, gravity=(0, 0, 6), spread=0.25, position_spread=0.3,
                                  additive=False, follow=False))
    root = ap.group(TITLE, [ap.group('materials', mats, expand=False), ap.group('half face + collar', face), ap.group('left arm', arm_parts), ap.group('back reactor', back),
                            ap.group('glow sprites', [sprites]), ap.group('steam', steam)], notes=ap.WM)
    text, tree = ap.finalize(root, 'ethics_adv_cyborg')
    errs, warns, counts = ap.validate(tree, TITLE)
    errs += ap.check_text(text)
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, FILE + '.txt'), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, tree, st, errs, counts


if __name__ == '__main__':
    text, tree, st, errs, counts = build()
    print('%d bytes, %d parts' % (len(text), sum(1 for _ in pw.walk(tree))))
    for fn, (nv, nt, sz) in st.files.items():
        print('  %-22s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
