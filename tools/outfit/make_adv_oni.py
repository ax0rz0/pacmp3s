"""Outfit #2: Ethics Assistant - Cyber Oni (robotic oni mask).  Builds the meshes (adv_oni2), stages the OBJs and writes the pac outfit text.

Console commands (all optional):  pac_proxy oni_theme <0..3>   accent colour: 0 orange, 1 cyan, 2 magenta, 3 toxic green
                                  pac_proxy oni_jaw <0..1>     force the jaw open (the jaw also follows the voice meter by itself)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import adv_oni2 as oni
import adv_parts as ap
import adv_scene as asn
import pac_write as pw

STAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
OUT_DIR = os.path.join(STAGE_DIR, 'outfits')
FILE = 'ethics asst cyber oni'
TITLE = 'Ethics Assistant - Cyber Oni'

PALETTE = [(1.0, 0.30, 0.10), (0.08, 0.85, 1.0), (1.0, 0.10, 0.62), (0.45, 1.0, 0.15)]       # orange, cyan, magenta, toxic green


def theme_expr(cmd, scale, pulse):
    """three comma separated components of the accent colour chosen by command(cmd) (a smooth blend between the palette entries), times a pulse factor"""
    comps = []
    for c in range(3):
        terms = ['max(1-abs(command("%s")-%d),0)*%.3f' % (cmd, i, PALETTE[i][c] * scale) for i in range(len(PALETTE))]
        comps.append('(%s)*%s' % (' + '.join(terms), pulse))
    return ', '.join(comps)


def build(stage_dir=STAGE_DIR, write=True):
    ap.reset_uids()
    sc = asn.Scene()
    parts, ctx = oni.build_oni2(sc)
    rig = sc.rig
    S = ctx['surf']
    st = ap.Stage(stage_dir, 'oni')
    bone = ap.bone_name('Head1')

    def loc(key):
        return ap.to_bone_local(rig, 'Head1', parts[key]['mesh'])

    def locj(key):
        return ap.to_bone_local(rig, 'Head1', parts[key]['mesh'], pivot=oni.JAW_PIVOT)

    url = dict(plates=st.obj('plates', loc('white'), 'white lacquer plates'), under=st.obj('under', loc('black'), 'black under layer, trim, horn tips'),
               hardware=st.obj('hardware', loc('gray'), 'gunmetal hardware: ear cups, bolts, hoses, rings'), glow=st.obj('glow', loc('glow'), 'glowing strips (unlit)'),
               teeth=st.obj('teeth', loc('steel'), 'upper fangs'),
               jaw=st.obj('jaw', locj('jaw'), 'jaw plate (origin = hinge)'), jawb=st.obj('jawb', locj('jaw_black'), 'jaw trim (origin = hinge)'),
               jaws=st.obj('jaws', locj('jaw_steel'), 'jaw teeth (origin = hinge)'), jawg=st.obj('jawg', locj('jaw_glow'), 'jaw chevron (unlit, origin = hinge)'))

    pivot_local = ap.local_point(rig, 'Head1', oni.JAW_PIVOT)

    # ---- materials (used by name)
    mats = [
        ap.material3d('oni lacquer', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=2.4, phongexponent=34, phongfresnelranges=(0.12, 0.55, 1.0), rimlight=True,
                      rimlightexponent=5, rimlightboost=0.45),
        ap.material3d('oni gunmetal', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=3.2, phongexponent=18, phongfresnelranges=(0.2, 0.8, 1.0), envmap='env_cubemap',
                      envmaptint=(0.18, 0.19, 0.22)),
        ap.material3d('oni matte', 'models/debug/debugwhite', halflambert=True, phong=True, phongboost=0.9, phongexponent=10, phongfresnelranges=(0.1, 0.4, 1.0)),
    ]

    M = ap.model
    lit = [
        M('plates', url['plates'], bone, color=(0.94, 0.94, 0.96), material='oni lacquer'),
        M('under layer', url['under'], bone, color=(0.085, 0.085, 0.10), material='oni matte'),
        M('hardware', url['hardware'], bone, color=(0.30, 0.31, 0.37), material='oni gunmetal'),
        M('fangs', url['teeth'], bone, color=(0.88, 0.90, 0.96), material='oni gunmetal'),
    ]
    glow = M('glow strips', url['glow'], bone, color=PALETTE[0], nolight=True, material='models/debug/debugwhite', children=[
        ap.proxy('oni_theme', 'Color', theme_expr('oni_theme', 1.0, '(0.84 + 0.16*sin(time()*2.2) + min(voice_volume()*1.5, 0.6))'))])
    jaw_expr = '0, -(min(command("oni_jaw"),1)*24 + min(voice_volume()*2.5,1)*14), 0'
    jaw = [
        M('jaw plate', url['jaw'], bone, color=(0.94, 0.94, 0.96), material='oni lacquer', pos=tuple(pivot_local), children=[ap.proxy('oni_jaw', 'Angles', jaw_expr)]),
        M('jaw trim', url['jawb'], bone, color=(0.085, 0.085, 0.10), material='oni matte', pos=tuple(pivot_local), children=[ap.proxy('oni_jaw', 'Angles', jaw_expr)]),
        M('jaw teeth', url['jaws'], bone, color=(0.88, 0.90, 0.96), material='oni gunmetal', pos=tuple(pivot_local), children=[ap.proxy('oni_jaw', 'Angles', jaw_expr)]),
        M('jaw glow', url['jawg'], bone, color=PALETTE[0], nolight=True, pos=tuple(pivot_local), children=[
            ap.proxy('oni_jaw', 'Angles', jaw_expr),
            ap.proxy('oni_theme', 'Color', theme_expr('oni_theme', 1.0, '(0.84 + 0.16*sin(time()*2.2) + min(voice_volume()*1.5, 0.6))'))]),
    ]

    # ---- soft glow sprites (additive materials): visor slits, third eye, ear rings
    def spr(name, p_world, size_xy, alpha):
        return ap.sprite(name, bone, tuple(ap.local_point(rig, 'Head1', p_world)), (255, 90, 40), size_xy=size_xy, alpha=alpha, path='sprites/light_glow02_add')

    sp = []
    for side, nm in ((+1, 'left'), (-1, 'right')):
        p, n = S.pt(np.array([side * 1.55]), np.array([float(oni.sline(1.55))]), np.array([oni.UNDER + 0.7]))
        sp.append(spr('eye glow ' + nm, p[0], (3.2, 1.2), 0.55))
        pe = np.array([-0.3, 3.75 * side + side * 0.9, 65.4])
        sp.append(spr('ear glow ' + nm, pe, (3.4, 3.4), 0.35))
    p3, n3 = S.pt(np.array([0.0]), np.array([67.75]), np.array([oni.TOP + 0.5]))
    sp.append(spr('third eye glow', p3[0], (1.6, 1.6), 0.7))
    sprite_group = ap.proxy('oni_theme', 'Color', theme_expr('oni_theme', 255.0, '(0.9 + 0.1*sin(time()*2.2))'), affect_children=True, children=sp)

    kids = mats + lit + [glow] + jaw + [sprite_group]
    root = ap.group(TITLE, kids, notes=ap.WM)
    text, tree = ap.finalize(root, 'ethics_adv_oni')
    errs, warns, counts = ap.validate(tree, TITLE)
    errs += ap.check_text(text)
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, FILE + '.txt'), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, tree, st, errs


if __name__ == '__main__':
    text, tree, st, errs = build()
    print('%d bytes, %d parts' % (len(text), sum(1 for _ in pw.walk(tree))))
    for fn, (nv, nt, sz) in st.files.items():
        print('  %-20s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
