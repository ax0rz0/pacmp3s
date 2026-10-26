"""Outfit #1: Ethics Assistant - Netrunner (respirator face cover + right-eye cyber implant + headset, custom silver hair with a swinging neon-tipped ponytail, cyber gloves + vambraces).
Console:  pac_proxy nr_theme <0..3>   accent colour: 0 magenta, 1 cyan, 2 toxic green, 3 orange
          pac_proxy nr_hair <0..3>    hair colour: 0 silver, 1 black, 2 white, 3 pink
build(variant) -> 'normal' (the player's own head) or 'custom' (a donor head, see make_adv_net_custom.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import adv_common as ac
import adv_geom as ag
import adv_net as net
import adv_net_arms as arms
import adv_net_hair as hair
import adv_panels as pn
import adv_parts as ap
import adv_scene as asn
import pac_write as pw

STAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
OUT_DIR = os.path.join(STAGE_DIR, 'outfits')
HAND_SLOTS = (6, 8)             # femsuit_04 material slots (1-based): handfemale, citizen_sheet (the hands)
N_SLOTS = 21


def world_meshes(sc, head_kw=None, with_hair=True):
    parts, ctx = net.build_head(sc, **(head_kw or {}))
    out = dict(black=parts['black']['mesh'], gray=parts['gray']['mesh'], gun=parts['gun']['mesh'], glow=parts['glow']['mesh'])
    tie = None
    if with_hair:
        hp, hctx = hair.build_hair(sc, ctx)
        out['black'] = ag.merge([out['black'], hp['under']['mesh'], hp['tie']['mesh']])
        out['glow'] = ag.merge([out['glow'], hp['tips']['mesh'], hp['tie_glow']['mesh']])
        out['hair'] = hp['hair']['mesh']
        out['pony'] = hp['pony']['mesh']
        out['pony_tips'] = hp['pony_tips']['mesh']
        tie = hctx['tie']
    return out, ctx, tie


def build(variant='normal', stage_dir=STAGE_DIR, write=True, name=None, head_kw=None, extra_head_parts=None, hands=True, with_hair=True, file=None, title=None, null_slots=(), head_ctx=None,
          extra_materials=()):
    ap.reset_uids()
    sc = asn.Scene()
    rig = sc.rig
    meshes, ctx, tie = world_meshes(sc, head_kw, with_hair)
    S = ctx['surf']
    st = ap.Stage(stage_dir, 'net' if variant == 'normal' else 'netc')
    head = ap.bone_name('Head1')

    def loc(key):
        return ap.to_bone_local(rig, 'Head1', meshes[key])

    url = {}
    for k in ('black', 'gray', 'gun', 'glow'):
        url[k] = st.obj(k, loc(k), 'respirator / headset / implant: ' + k, smooth_deg=55 if k == 'glow' else 42)
    if with_hair:
        url['hair'] = st.obj('hair', loc('hair'), 'static hair', smooth_deg=60)
        url['pony'] = st.obj('pony', ap.to_bone_local(rig, 'Head1', meshes['pony'], pivot=tie), 'ponytail (origin = the tie)', smooth_deg=60)
        url['pony_tips'] = st.obj('pony_tips', ap.to_bone_local(rig, 'Head1', meshes['pony_tips'], pivot=tie), 'ponytail neon tips (origin = the tie)', smooth_deg=65)
        tie_local = tuple(ap.local_point(rig, 'Head1', tie))

    # ---- arms: left built in world space, right is the mirror image
    am, actx = arms.build_arm(sc)
    for side, bone_f, bone_h in (('l', 'L_Forearm', 'L_Hand'), ('r', 'R_Forearm', 'R_Hand')):
        for key, bone in (('armor_f', bone_f), ('glow_f', bone_f), ('armor_h', bone_h), ('glow_h', bone_h)):
            m = am[key] if side == 'l' else ag.mirror_y(am[key])
            url['%s_%s' % (key, side)] = st.obj('%s_%s' % (key, side), ap.to_bone_local(rig, bone, m), '%s %s' % (key, side), smooth_deg=45)

    # ---- materials
    mats = [
        ap.material3d('nr matte', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=1.2, phongexponent=14, phongfresnelranges=(0.1, 0.5, 1.0)),
        ap.material3d('nr gunmetal', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=3.2, phongexponent=20, phongfresnelranges=(0.2, 0.8, 1.0), envmap='env_cubemap',
                      envmaptint=(0.16, 0.17, 0.2)),
        ap.material3d('nr hair', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=1.6, phongexponent=26, phongfresnelranges=(0.1, 0.5, 1.0), rimlight=True, rimlightexponent=4,
                      rimlightboost=0.35),
        ap.material3d('nr glove', 'models/debug/debugwhite', color=(0.05, 0.05, 0.06), halflambert=True, phong=True, phongboost=2.6, phongexponent=38, phongfresnelranges=(0.1, 0.6, 1.0)),
    ]
    mats = mats + list(extra_materials)
    M = ap.model
    theme = lambda scale, pulse: ac.theme_expr('nr_theme', ac.PALETTE_NEON, scale, pulse)
    hair_expr = ac.theme_expr('nr_hair', ac.PALETTE_HAIR, 1.0, '1')

    def glow_part(nm, u, bone, pos=None):
        return M(nm, u, bone, color=ac.PALETTE_NEON[0], nolight=True, pos=pos, children=[ap.proxy('nr_theme', 'Color', theme(1.0, ac.PULSE_VOICE))])

    slots = [''] * N_SLOTS
    for s in HAND_SLOTS:
        slots[s - 1] = 'nr glove'
    for s in null_slots:
        slots[s - 1] = 'null'
    parts = []
    parts.append(ap.group('materials', mats, expand=False))
    if hands or null_slots:
        parts.append(ap.entity2('Ethics Assistant body (gloves%s)' % (', head hidden' if null_slots else ''), materials=';'.join(slots), modifiers='', extra=None))
    mask = [
        M('mask black', url['black'], head, color=(0.07, 0.07, 0.09), material='nr matte'),
        M('mask graphite', url['gray'], head, color=(0.2, 0.21, 0.26), material='nr gunmetal'),
        M('mask metal', url['gun'], head, color=(0.42, 0.44, 0.5), material='nr gunmetal'),
        glow_part('mask glow', url['glow'], head),
    ]
    if extra_head_parts:
        mask = list(extra_head_parts) + mask
    parts.append(ap.group('face cover + headset', mask))
    if with_hair:
        hair_parts = [
            M('hair', url['hair'], head, color=ac.PALETTE_HAIR[0], material='nr hair', children=[ap.proxy('nr_hair', 'Color', hair_expr)]),
            ap.jiggle('ponytail', head, pos=tie_local, strain=0.5, speed=1.0, children=[
                M('ponytail', url['pony'], head, color=ac.PALETTE_HAIR[0], material='nr hair', children=[ap.proxy('nr_hair', 'Color', hair_expr)]),
                M('ponytail tips', url['pony_tips'], head, color=ac.PALETTE_NEON[0], nolight=True, children=[ap.proxy('nr_theme', 'Color', theme(1.0, ac.PULSE_VOICE))]),
            ]),
        ]
        parts.append(ap.group('hair', hair_parts))
    arm_parts = []
    for side, bone_f, bone_h, label in (('l', 'L_Forearm', 'L_Hand', 'left'), ('r', 'R_Forearm', 'R_Hand', 'right')):
        bf, bh = ap.bone_name(bone_f), ap.bone_name(bone_h)
        arm_parts.append(ap.group('%s arm' % label, [
            M('%s vambrace' % label, url['armor_f_' + side], bf, color=(0.16, 0.17, 0.21), material='nr gunmetal'),
            glow_part('%s vambrace glow' % label, url['glow_f_' + side], bf),
            M('%s hand plate' % label, url['armor_h_' + side], bh, color=(0.16, 0.17, 0.21), material='nr gunmetal'),
            glow_part('%s hand glow' % label, url['glow_h_' + side], bh),
        ]))
    parts.append(ap.group('cyber arms', arm_parts))

    # ---- soft glow sprites (all follow the accent colour through one proxy that drives its children) + fingertip trails
    def spr(nm, bone_short, p_world, size_xy, alpha):
        return ap.sprite(nm, ap.bone_name(bone_short), tuple(ap.local_point(rig, bone_short, p_world)), (255, 40, 140), size_xy=size_xy, alpha=alpha)

    sp = []
    # right-eye implant, headset cups, mouth slit, side filters, hair tie
    cu, cv = -1.42, 65.12
    p, n = S.pt(np.array([cu]), np.array([cv]), np.array([0.75]))
    sp.append(spr('implant glow', 'Head1', p[0], (1.5, 1.5), 0.8))
    cup_y = (head_kw or {}).get('cup_y', 3.75)
    cup_z = (head_kw or {}).get('cup_z', 65.2)
    cup_x = (head_kw or {}).get('cup_x', -0.3)
    for sgn, nm in ((+1, 'left'), (-1, 'right')):
        sp.append(spr('%s cup glow' % nm, 'Head1', np.array([cup_x, sgn * (cup_y + 0.9), cup_z]), (3.0, 3.0), 0.4))
    pm, nm_ = S.pt(np.array([0.0]), np.array([61.4]), np.array([net.top_off(0.0, 61.4) + 0.2]))
    sp.append(spr('mouth glow', 'Head1', pm[0], (4.4, 0.9), 0.55))
    for sgn, nm in ((+1, 'left'), (-1, 'right')):
        fv = (head_kw or {}).get('filter_v', 61.9)
        pf, nf, tuf, tvf = pn.frame_at(S, sgn * 4.25, fv, net.top_off(4.25, fv) - 0.1)
        d = ag.unit(nf + np.array([0.35, 0.0, 0.0]))
        sp.append(spr('%s filter glow' % nm, 'Head1', pf + d * 1.12, (1.5, 1.5), 0.7))
    if with_hair:
        sp.append(spr('tie glow', 'Head1', tie + ag.unit(np.array([-0.85, 0.0, 0.5])) * 1.0, (1.8, 1.8), 0.6))
    for side, pre in (('left', 'L'), ('right', 'R')):
        for tip, parent, nm in (('Finger02', 'Finger01', 'thumb'), ('Finger12', 'Finger11', 'index'), ('Finger22', 'Finger21', 'middle')):
            pw_ = ac.tip_position(rig, pre + '_' + parent, pre + '_' + tip, 0.45)
            sp.append(spr('%s %s tip' % (side, nm), pre + '_' + tip, pw_, (0.8, 0.8), 0.9))
    parts.append(ap.group('glow sprites', [ap.proxy('nr_theme', 'Color', ac.theme_expr('nr_theme', ac.PALETTE_NEON, 255.0, ac.PULSE_SOFT), affect_children=True, children=sp)]))

    trails = []
    for side, pre in (('left', 'L'), ('right', 'R')):
        for tip, parent, nm in (('Finger12', 'Finger11', 'index'), ('Finger22', 'Finger21', 'middle')):
            pw_ = ac.tip_position(rig, pre + '_' + parent, pre + '_' + tip, 0.45)
            trails.append(ap.trail('%s %s trail' % (side, nm), ap.bone_name(pre + '_' + tip), tuple(ap.local_point(rig, pre + '_' + tip, pw_)), path='trails/laser',
                                   start_color=(255, 40, 140), end_color=(255, 40, 140), start_size=0.55, end_size=0.0, start_alpha=0.85, end_alpha=0.0, duration=0.5, spacing=0.3, stretch=1.0))
    parts.append(ap.group('fingertip trails', [ap.proxy('nr_theme', 'StartColor', ac.theme_expr('nr_theme', ac.PALETTE_NEON, 1.0, '1'), affect_children=True, children=trails)]))

    title = title or ('Ethics Assistant - Netrunner' if variant == 'normal' else 'Ethics Assistant - Netrunner (custom head)')
    root = ap.group(title, parts, notes=ap.WM)
    text, tree = ap.finalize(root, 'ethics_adv_net_' + variant)
    errs, warns, counts = ap.validate(tree, title)
    errs += ap.check_text(text)
    file = file or ('ethics asst netrunner' if variant == 'normal' else 'ethics asst netrunner custom head')
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, file + '.txt'), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, tree, st, errs, counts


if __name__ == '__main__':
    text, tree, st, errs, counts = build('normal')
    print('%d bytes, %d parts' % (len(text), sum(1 for _ in pw.walk(tree))))
    for fn, (nv, nt, sz) in st.files.items():
        print('  %-24s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
