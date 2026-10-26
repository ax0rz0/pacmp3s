"""Outfit #5: Ethics Assistant - Neon Seraph (cyber angel).  Segmented data-wings that breathe, flare with running speed and can be flapped / spread on demand, a translucent cyber visor, angular
shoulder fins, a ring of holographic panels spinning round the left forearm, four orbs circling the waist, wing-tip trails and falling light motes.
Console:  pac_proxy sr_theme <0..3>   accent colour: 0 cyan, 1 magenta, 2 gold, 3 violet
          pac_proxy sr_open <0..1>    spread the wings wider
          pac_proxy sr_flap <0..1>    flap the wings (hold at 1)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import adv_common as ac
import adv_geom as ag
import adv_parts as ap
import adv_scene as asn
import adv_seraph as sr
import pac_write as pw

STAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
OUT_DIR = os.path.join(STAGE_DIR, 'outfits')
FILE = 'ethics asst neon seraph'
TITLE = 'Ethics Assistant - Neon Seraph'
PALETTE = [(0.15, 0.85, 1.0), (1.0, 0.2, 0.65), (1.0, 0.76, 0.2), (0.62, 0.4, 1.0)]
SPHERE = 'models/hunter/misc/sphere025x025.mdl'


def stock_model(name, path, bone, **kw):
    p = ap.model(name, path, bone, **kw)
    p['self'].pop('ForceObjUrl', None)
    return p


def build(stage_dir=STAGE_DIR, write=True):
    ap.reset_uids()
    sc = asn.Scene()
    rig = sc.rig
    parts, ctx = sr.build_seraph(sc)
    st = ap.Stage(stage_dir, 'sr')
    root = sr.ROOT
    root_r = root * np.array([1, -1, 1])
    spine4 = ap.bone_name('Spine4')

    def mir(m):
        return ag.mirror_y(m)

    url = {}
    for side, bone, rt, flip in (('l', 'Spine4', root, False), ('r', 'Spine4', root_r, True)):
        w = parts['wing']['mesh'] if not flip else mir(parts['wing']['mesh'])
        g = parts['wing_glow']['mesh'] if not flip else mir(parts['wing_glow']['mesh'])
        url['wing_' + side] = st.obj('wing_' + side, ap.to_bone_local(rig, bone, w, pivot=rt), 'wing %s (origin = the hinge)' % side, smooth_deg=50)
        url['wing_glow_' + side] = st.obj('wing_glow_' + side, ap.to_bone_local(rig, bone, g, pivot=rt), 'wing %s edge lines (origin = the hinge)' % side, smooth_deg=60)
    for side, bone, flip in (('l', 'L_UpperArm', False), ('r', 'R_UpperArm', True)):
        w = parts['shoulder']['mesh'] if not flip else mir(parts['shoulder']['mesh'])
        g = parts['shoulder_glow']['mesh'] if not flip else mir(parts['shoulder_glow']['mesh'])
        url['sh_' + side] = st.obj('shoulder_' + side, ap.to_bone_local(rig, bone, w), 'shoulder fin ' + side, smooth_deg=42)
        url['shg_' + side] = st.obj('shoulder_glow_' + side, ap.to_bone_local(rig, bone, g), 'shoulder fin glow ' + side, smooth_deg=60)
    head = ap.bone_name('Head1')
    url['lens'] = st.obj('lens', ap.to_bone_local(rig, 'Head1', parts['lens']['mesh']), 'visor lens', smooth_deg=50)
    url['vframe'] = st.obj('visor_frame', ap.to_bone_local(rig, 'Head1', parts['visor_frame']['mesh']), 'visor frame + crest', smooth_deg=42)
    url['vglow'] = st.obj('visor_glow', ap.to_bone_local(rig, 'Head1', parts['visor_glow']['mesh']), 'visor glow lines', smooth_deg=60)
    holo_c = ctx['holo_centre']
    url['holo'] = st.obj('holo', ap.to_bone_local(rig, 'L_Forearm', parts['holo']['mesh'], pivot=holo_c), 'hologram panels (origin = forearm axis)', smooth_deg=60)

    def theme(scale, pulse='1'):
        return ac.theme_expr('sr_theme', PALETTE, scale, pulse)

    soft = '(0.85 + 0.15*sin(time()*1.9))'
    mats = [
        ap.material3d('sr pearl', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=2.4, phongexponent=30, phongfresnelranges=(0.12, 0.6, 1.0), rimlight=True, rimlightexponent=4,
                      rimlightboost=0.6),
        ap.material3d('sr chrome', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=4.0, phongexponent=60, phongfresnelranges=(0.2, 0.9, 1.0), envmap='env_cubemap',
                      envmaptint=(0.45, 0.47, 0.52)),
        ap.material3d('sr lens', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=3.0, phongexponent=40, phongfresnelranges=(0.1, 0.7, 1.0)),
    ]
    M = ap.model

    def glow(nm, key, bone, pos=None, scale=1.0, kids=()):
        return M(nm, url[key], bone, color=PALETTE[0], nolight=True, pos=pos, children=[ap.proxy('sr_theme', 'Color', theme(scale, soft))] + list(kids))

    rl = tuple(ap.local_point(rig, 'Spine4', root))
    rr = tuple(ap.local_point(rig, 'Spine4', root_r))

    def wing_proxies(sign):
        s = '' if sign > 0 else '-'
        return [
            ap.proxy('sr_open', 'Angles', '0, 0, %s(min(owner_velocity_length()/250, 1)*18 - min(command("sr_open"), 1)*22)' % s),
            ap.proxy('sr_flap', 'AngleOffset', '%s(4*sin(time()*0.9) + min(command("sr_flap"), 1)*16*sin(time()*8)), 0, 0' % s),
        ]

    wings = []
    for side, pos_, sign in (('left', rl, +1), ('right', rr, -1)):
        k = 'l' if side == 'left' else 'r'
        wings.append(ap.group('%s wing' % side, [
            M('%s wing' % side, url['wing_' + k], spine4, color=(0.93, 0.95, 1.0), material='sr pearl', pos=pos_, children=wing_proxies(sign)),
            M('%s wing edge glow' % side, url['wing_glow_' + k], spine4, color=PALETTE[0], nolight=True, pos=pos_, children=[ap.proxy('sr_theme', 'Color', theme(1.0, soft))] + wing_proxies(sign)),
        ]))
    visor = [
        M('visor frame', url['vframe'], head, color=(0.8, 0.83, 0.9), material='sr chrome'),
        M('visor lens', url['lens'], head, color=(0.25, 0.8, 1.0), material='sr lens', alpha=0.4, translucent=True, children=[ap.proxy('sr_theme', 'Color', theme(0.9, '1'))]),
        glow('visor glow', 'vglow', head),
    ]
    shoulders = []
    for side, bone_short, k in (('left', 'L_UpperArm', 'l'), ('right', 'R_UpperArm', 'r')):
        b = ap.bone_name(bone_short)
        shoulders.append(M('%s shoulder fin' % side, url['sh_' + k], b, color=(0.93, 0.95, 1.0), material='sr pearl'))
        shoulders.append(glow('%s shoulder glow' % side, 'shg_' + k, b))
    holo = glow('hologram ring', 'holo', ap.bone_name('L_Forearm'), pos=tuple(ap.local_point(rig, 'L_Forearm', holo_c)), scale=1.0, kids=[ap.proxy('sr_spin', 'Angles', '0, 0, time()*35')])
    orbs = []
    for k in range(4):
        a = 'time()*0.8 + %.4f' % (k * np.pi / 2)
        orb = stock_model('orb %d' % (k + 1), SPHERE, ap.bone_name('Pelvis'), color=PALETTE[0], nolight=True, size=0.17, material='models/debug/debugwhite', children=[
            ap.proxy('sr_orbit', 'Position', '14*cos(%s), 6 + 2.5*sin(time()*1.3 + %.4f), 14*sin(%s)' % (a, k * np.pi / 2, a)),
            ap.proxy('sr_theme', 'Color', theme(1.0, soft))])
        orbs.append(orb)

    def spr(nm, bone_short, p_world, size_xy, alpha):
        return ap.sprite(nm, ap.bone_name(bone_short), tuple(ap.local_point(rig, bone_short, p_world)), (40, 220, 255), size_xy=size_xy, alpha=alpha)

    S = ctx['surf']
    sp = []
    for sgn, nm in ((+1, 'left'), (-1, 'right')):
        p, n = S.pt(np.array([sgn * 1.45]), np.array([65.1]), np.array([0.5]))
        sp.append(spr('%s eye glow' % nm, 'Head1', p[0], (1.4, 1.4), 0.45))
    sprites = ap.proxy('sr_theme', 'Color', ac.theme_expr('sr_theme', PALETTE, 255.0, soft), affect_children=True, children=sp)
    # orb glows are separate sprite groups (their own parents so they ride the orbit): sprites as children of each orb
    for orb in orbs:
        orb['children'] = dict(orb['children'])
        orb['children'][len(orb['children']) + 1] = ap.sprite('orb glow', ap.bone_name('Pelvis'), (0, 0, 0), (40, 220, 255), size_xy=(3.4, 3.4), alpha=0.8)
    trails = []
    for side, k, rt in (('left', 'l', root), ('right', 'r', root_r)):
        tip_world = rt + (sr.frame_path()[-1] - sr.ROOT) * np.array([1, 1 if k == 'l' else -1, 1]) * sr.WING_SCALE
        tip_local_bone = ap.local_point(rig, 'Spine4', tip_world)
        trails.append(ap.trail('%s wing tip trail' % side, spine4, tuple(tip_local_bone), path='trails/plasma', start_color=(40, 220, 255), end_color=(40, 220, 255), start_size=1.2, end_size=0.0,
                               start_alpha=0.7, end_alpha=0.0, duration=0.8, spacing=0.3, stretch=1.0))
    trail_group = ap.proxy('sr_theme', 'StartColor', ac.theme_expr('sr_theme', PALETTE, 255.0, '1'), affect_children=True, children=trails)
    mote_pos = tuple(ap.local_point(rig, 'Spine4', np.array([-5.0, 0.0, 58.0])))
    motes = ap.proxy('sr_theme', 'Color1', ac.theme_expr('sr_theme', PALETTE, 255.0, '1'), affect_children=True, children=[
        ap.particles('light motes', spine4, mote_pos, material='sprites/light_glow02_add', start_size=0.9, end_size=0.0, color1=(40, 220, 255), color2=(40, 220, 255), start_alpha=230, end_alpha=0,
                     die_time=2.4, fire_delay=0.09, number=1, velocity=3.0, gravity=(0, 0, -6), spread=0.7, position_spread=14.0, additive=True, follow=False)])

    root_group = ap.group(TITLE, [ap.group('materials', mats, expand=False), ap.group('wings', wings), ap.group('visor', visor), ap.group('shoulder fins', shoulders), ap.group('hologram', [holo]),
                                  ap.group('orbs', orbs), ap.group('glow sprites', [sprites]), ap.group('wing tip trails', [trail_group]), ap.group('light motes', [motes])], notes=ap.WM)
    text, tree = ap.finalize(root_group, 'ethics_adv_seraph')
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
        print('  %-24s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
