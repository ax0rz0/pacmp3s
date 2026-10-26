"""Outfit #3: Ethics Assistant - Spectral Archivist (ghost / transparent humanoid).
The body is re-skinned with an additive, rim-lit ghost material (eyes and mouth hidden), hovers and bobs; a porcelain veil mask with glowing slit eyes, a hood with tattered veil strips, a glowing
inner anatomy (spine, ribs, core with gyro rings), a ragged shroud and spectral chains (the loose cloth sways through jiggle parts), fingertip glows, plasma trails and soul motes.
Console:  pac_proxy gh_theme <0..3>   0 ice cyan, 1 violet, 2 soul green, 3 ember red"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import adv_common as ac
import adv_geom as ag
import adv_ghost as gh
import adv_parts as ap
import adv_scene as asn
import pac_write as pw

STAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
OUT_DIR = os.path.join(STAGE_DIR, 'outfits')
FILE = 'ethics asst ghost'
TITLE = 'Ethics Assistant - Spectral Archivist'
PALETTE = [(0.45, 0.85, 1.0), (0.66, 0.42, 1.0), (0.35, 1.0, 0.62), (1.0, 0.36, 0.26)]
# femsuit_04 material slots (1-based): face, eyeball_l, eyeball_r, mouth, suit, hands (handfemale), skirt, hands (citizen_sheet)
SLOTS_BODY = {1: 'gh body', 2: 'null', 3: 'null', 4: 'null', 5: 'gh body', 6: 'gh body', 7: 'gh body', 8: 'gh body'}
N_SLOTS = 21


def build(stage_dir=STAGE_DIR, write=True):
    ap.reset_uids()
    sc = asn.Scene()
    rig = sc.rig
    parts, ctx = gh.build_ghost(sc)
    st = ap.Stage(stage_dir, 'gh')
    head = ap.bone_name('Head1')
    spine2 = ap.bone_name('Spine2')
    pelvis = ap.bone_name('Pelvis')
    core_c = ctx['core']
    shroud_pivot = np.array([0.1, 0.0, 41.5])
    head_origin = rig.world[rig.idx['ValveBiped.Bip01_Head1']][:3, 3]
    chain_o = ctx['chain_origin']
    url = {}
    url['mask'] = st.obj('mask', ap.to_bone_local(rig, 'Head1', parts['mask']['mesh']), 'porcelain veil mask', smooth_deg=50)
    url['eyes'] = st.obj('eyes', ap.to_bone_local(rig, 'Head1', parts['eyes']['mesh']), 'glowing slit eyes', smooth_deg=60)
    url['hood'] = st.obj('hood', ap.to_bone_local(rig, 'Head1', parts['hood']['mesh']), 'draped hood (cloth)', smooth_deg=55)
    url['veil'] = st.obj('veil', ap.to_bone_local(rig, 'Head1', parts['veil']['mesh'], pivot=head_origin), 'veil strips (origin = head bone)', smooth_deg=60)
    url['anatomy'] = st.obj('anatomy', ap.to_bone_local(rig, 'Spine2', parts['anatomy']['mesh']), 'spine, ribs, sternum, clavicles', smooth_deg=55)
    url['core'] = st.obj('core', ap.to_bone_local(rig, 'Spine2', parts['core']['mesh'], pivot=core_c), 'core orb (origin = its centre)', smooth_deg=60)
    url['rings'] = st.obj('rings', ap.to_bone_local(rig, 'Spine2', parts['rings']['mesh'], pivot=core_c), 'gyro rings (origin = the core)', smooth_deg=60)
    url['shroud'] = st.obj('shroud', ap.to_bone_local(rig, 'Pelvis', parts['shroud']['mesh'], pivot=shroud_pivot), 'tattered shroud (origin = waist)', smooth_deg=60)
    url['chain_l'] = st.obj('chain_l', ap.to_bone_local(rig, 'L_Hand', parts['chain_l']['mesh'], pivot=chain_o), 'spectral chain, left (origin = wrist)', smooth_deg=55)
    chain_r_world = ag.mirror_y(parts['chain_l']['mesh'])
    chain_o_r = chain_o * np.array([1, -1, 1])
    url['chain_r'] = st.obj('chain_r', ap.to_bone_local(rig, 'R_Hand', chain_r_world, pivot=chain_o_r), 'spectral chain, right (origin = wrist)', smooth_deg=55)

    # ring spin: world up in the spine bone's local frame is its X axis -> roll
    R2 = rig.world[rig.idx['ValveBiped.Bip01_Spine2']][:3, :3]
    up_local = R2.T @ np.array([0, 0, 1.0])
    assert abs(up_local[0]) > 0.95, up_local

    def theme(scale, pulse='1'):
        return ac.theme_expr('gh_theme', PALETTE, scale, pulse)

    soft = '(0.85 + 0.15*sin(time()*1.7))'

    mats = [
        ap.material3d('gh body', 'models/debug/debugwhite', additive=True, halflambert=True, rimlight=True, rimlightexponent=2.5, rimlightboost=2.2),
        ap.material3d('gh cloth', 'models/debug/debugwhite', additive=True, nocull=True, halflambert=True, rimlight=True, rimlightexponent=3, rimlightboost=1.5),
        ap.material3d('gh mask', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=2.2, phongexponent=30, phongfresnelranges=(0.12, 0.6, 1.0), rimlight=True, rimlightexponent=4,
                      rimlightboost=0.8),
    ]
    slots = [''] * N_SLOTS
    for k, v in SLOTS_BODY.items():
        slots[k - 1] = v
    body = ap.entity2('Ethics Assistant (spectral body)', materials=';'.join(slots), modifiers='', alpha=0.85, color=PALETTE[0], translucent=True, children=[
        ap.proxy('gh_theme', 'Color', theme(0.8, soft)),
        ap.proxy('gh_hover', 'PositionOffset', '0, 0, 3.4 + sin(time()*1.4)*0.9')])
    M = ap.model

    def glow(nm, u, bone, pos=None, scale=1.0, kids=()):
        return M(nm, u, bone, color=PALETTE[0], nolight=True, pos=pos, children=[ap.proxy('gh_theme', 'Color', theme(scale, soft))] + list(kids))

    core_local = tuple(ap.local_point(rig, 'Spine2', core_c))
    chain_local_l = tuple(ap.local_point(rig, 'L_Hand', chain_o))
    chain_local_r = tuple(ap.local_point(rig, 'R_Hand', chain_o_r))
    shroud_local = tuple(ap.local_point(rig, 'Pelvis', shroud_pivot))

    face = [
        M('veil mask', url['mask'], head, color=(0.9, 0.94, 1.0), material='gh mask'),
        glow('mask eyes', url['eyes'], head),
        M('hood', url['hood'], head, color=PALETTE[0], material='gh cloth', children=[ap.proxy('gh_theme', 'Color', theme(0.55, soft))]),
        ap.jiggle('veil sway', head, strain=0.45, speed=1.0, children=[M('veil strips', url['veil'], head, color=PALETTE[0], material='gh cloth', children=[ap.proxy('gh_theme', 'Color', theme(0.5, soft))])]),
    ]
    inner = [
        glow('anatomy', url['anatomy'], spine2, scale=0.9),
        glow('core', url['core'], spine2, pos=core_local, scale=1.3, kids=[ap.proxy('gh_core', 'Size', '1 + 0.14*sin(time()*3.1)')]),
        glow('gyro rings', url['rings'], spine2, pos=core_local, scale=1.0, kids=[ap.proxy('gh_ring', 'Angles', '0, 0, time()*75')]),
    ]
    cloth = [
        ap.jiggle('shroud sway', pelvis, pos=shroud_local, strain=0.5, speed=1.0, children=[
            M('shroud', url['shroud'], pelvis, color=PALETTE[0], material='gh cloth', children=[ap.proxy('gh_theme', 'Color', theme(0.5, soft))])]),
    ]
    chains = []
    for side, bone_short, pos_ in (('left', 'L_Hand', chain_local_l), ('right', 'R_Hand', chain_local_r)):
        b = ap.bone_name(bone_short)
        chains.append(ap.jiggle('%s chain sway' % side, b, pos=pos_, strain=0.4, speed=1.2, children=[glow('%s chain' % side, url['chain_l' if side == 'left' else 'chain_r'], b, scale=0.9)]))

    # sprites: eyes, core, fingertips
    def spr(nm, bone_short, p_world, size_xy, alpha):
        return ap.sprite(nm, ap.bone_name(bone_short), tuple(ap.local_point(rig, bone_short, p_world)), (110, 215, 255), size_xy=size_xy, alpha=alpha)

    sp = []
    S = ctx['surf']
    for sgn, nm in ((+1, 'left'), (-1, 'right')):
        p, n = S.pt(np.array([sgn * 1.45]), np.array([65.1]), np.array([1.2]))
        sp.append(spr('%s eye glow' % nm, 'Head1', p[0], (1.5, 2.4), 0.85))
    sp.append(spr('core glow', 'Spine2', core_c, (7.0, 7.0), 0.8))
    for side, pre in (('left', 'L'), ('right', 'R')):
        for tip, parent, nm in (('Finger02', 'Finger01', 'thumb'), ('Finger12', 'Finger11', 'index'), ('Finger22', 'Finger21', 'middle')):
            pw_ = ac.tip_position(rig, pre + '_' + parent, pre + '_' + tip, 0.45)
            sp.append(spr('%s %s tip' % (side, nm), pre + '_' + tip, pw_, (0.9, 0.9), 0.9))
    sprites = ap.proxy('gh_theme', 'Color', ac.theme_expr('gh_theme', PALETTE, 255.0, soft), affect_children=True, children=sp)

    trails = []
    for side, pre in (('left', 'L'), ('right', 'R')):
        pw_ = ac.tip_position(rig, pre + '_Finger21', pre + '_Finger22', 0.45)
        trails.append(ap.trail('%s hand trail' % side, ap.bone_name(pre + '_Finger22'), tuple(ap.local_point(rig, pre + '_Finger22', pw_)), path='trails/plasma', start_color=(110, 215, 255),
                               end_color=(110, 215, 255), start_size=1.1, end_size=0.0, start_alpha=0.8, end_alpha=0.0, duration=0.9, spacing=0.3, stretch=1.0))
    trail_group = ap.proxy('gh_theme', 'StartColor', ac.theme_expr('gh_theme', PALETTE, 255.0, '1'), affect_children=True, children=trails)

    feet_local = tuple(ap.local_point(rig, 'Pelvis', (0.0, 0.0, 6.0)))
    chest_local = tuple(ap.local_point(rig, 'Spine2', (1.0, 0.0, 50.0)))
    head_local = tuple(ap.local_point(rig, 'Head1', (0.0, 0.0, 70.0)))
    emitters = [
        ap.particles('soul motes', spine2, chest_local, material='sprites/light_glow02_add', start_size=1.0, end_size=0.0, color1=(110, 215, 255), color2=(110, 215, 255), start_alpha=230,
                     end_alpha=0, die_time=2.6, fire_delay=0.1, number=1, velocity=5.0, gravity=(0, 0, 10), spread=0.8, position_spread=6.5, additive=True, follow=False),
        ap.particles('floor mist', pelvis, feet_local, material='sprites/light_glow02_add', start_size=6.0, end_size=11.0, color1=(110, 215, 255), color2=(110, 215, 255), start_alpha=40,
                     end_alpha=0, die_time=1.8, fire_delay=0.16, number=1, velocity=2.0, gravity=(0, 0, 1), spread=0.3, position_spread=7.5, additive=True, follow=True),
        ap.particles('head embers', head, head_local, material='sprites/light_glow02_add', start_size=0.7, end_size=0.0, color1=(110, 215, 255), color2=(110, 215, 255), start_alpha=220,
                     end_alpha=0, die_time=2.0, fire_delay=0.18, number=1, velocity=4.0, gravity=(0, 0, 8), spread=0.6, position_spread=3.2, additive=True, follow=False),
    ]
    particle_group = ap.proxy('gh_theme', 'Color1', ac.theme_expr('gh_theme', PALETTE, 255.0, '1'), affect_children=True, children=emitters)

    root = ap.group(TITLE, [ap.group('materials', mats, expand=False), body, ap.group('veil mask + hood', face), ap.group('inner light', inner), ap.group('shroud', cloth), ap.group('chains', chains),
                            ap.group('glow sprites', [sprites]), ap.group('trails', [trail_group]), ap.group('soul motes', [particle_group])], notes=ap.WM)
    text, tree = ap.finalize(root, 'ethics_adv_ghost')
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
        print('  %-20s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
