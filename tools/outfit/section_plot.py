"""mid-plane section of the head package in head-bone coordinates: x up (tilted 10 deg forward), y back, z lateral (z_l).
python section_plot.py out.png [--neck hd_neck_v2.obj] [--zl 0,1,2] [--stage DIR]
draws: hd_* head parts (orange skin, blue extras, purple hair), the neck obj (green, Neck1 bone frame), her own head+neck (gray) and suit (black) for reference"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import adv_scene as asn

HERE = os.path.dirname(os.path.abspath(__file__))


def read_obj(fn):
    V, F = [], []
    for line in open(fn):
        t = line.split()
        if not t:
            continue
        if t[0] == 'v':
            V.append([float(x) for x in t[1:4]])
        elif t[0] == 'f':
            idx = [int(x.split('/')[0]) - 1 for x in t[1:]]
            for i in range(1, len(idx) - 1):
                F.append([idx[0], idx[i], idx[i + 1]])
    return np.array(V), np.array(F)


def section(P, axis, value):
    """triangle soup P (n,3,3); segments (m,2,3) where the plane axis=value cuts the triangles"""
    d = P[:, :, axis] - value
    segs = []
    for t in np.nonzero(~((d > 0).all(1) | (d < 0).all(1)))[0]:
        dd = d[t]
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if (dd[i] > 0) != (dd[j] > 0):
                f = dd[i] / (dd[i] - dd[j])
                pts.append(P[t][i] + (P[t][j] - P[t][i]) * f)
        if len(pts) == 2:
            segs.append(pts)
    return segs


def frames():
    sc = asn.Scene()
    out = {}
    for b in ('Head1', 'Neck1'):
        W = sc.rig.world[sc.rig.bone(b)]
        out[b] = (W[:3, :3], W[:3, 3])
    return sc, out


def soups(stage, neck_file, sc, fr):
    """-> {name: (n,3,3) soup in head-local coordinates}"""
    Rh, oh = fr['Head1']
    Rn, on = fr['Neck1']
    obj_dir = os.path.join(stage, 'obj', 'adv')
    items = {}
    for f in sorted(os.listdir(obj_dir)):
        if f.startswith('hd_') and not f.startswith('hd_neck'):
            V, F = read_obj(os.path.join(obj_dir, f))
            items[f] = V[F]
    if neck_file:
        V, F = read_obj(os.path.join(obj_dir, neck_file))
        Vw = V @ Rn.T + on                      # Neck1 local -> world
        items['hd_neck'] = ((Vw - oh) @ Rh)[F]
    world = sc.tr['pos']
    for name, key in (('her head', 'chau_facemap'), ('her suit', 'suit')):
        m = sc.slot_name == key
        items[name] = ((world[m].reshape(-1, 3) - oh) @ Rh).reshape(-1, 3, 3)
    return items


COL = {'hd_head': 'tab:orange', 'hd_extras': 'tab:blue', 'hd_hair': 'tab:purple', 'hd_neck': 'tab:green', 'her head': '0.55', 'her suit': 'k'}


def draw(ax, items, zl, title, lim=((-9, 5), (-5, 8))):
    for name, P in items.items():
        segs = section(P, 2, zl)
        c = next((v for k, v in COL.items() if name.startswith(k)), 'gray')
        for a, b in segs:
            ax.plot([a[1], b[1]], [a[0], b[0]], color=c, lw=1.0)
    ax.set_aspect('equal')
    ax.set_xlim(*lim[1])
    ax.set_ylim(*lim[0])
    ax.grid(True, alpha=0.3)
    ax.set_title(title, fontsize=9)


if __name__ == '__main__':
    out = sys.argv[1]
    stage = os.path.join(HERE, 'stage_adv')
    neck = None
    zls = [0.0, 1.0, 2.0]
    if '--stage' in sys.argv:
        stage = sys.argv[sys.argv.index('--stage') + 1]
    if '--neck' in sys.argv:
        neck = sys.argv[sys.argv.index('--neck') + 1]
    if '--zl' in sys.argv:
        zls = [float(x) for x in sys.argv[sys.argv.index('--zl') + 1].split(',')]
    sc, fr = frames()
    items = soups(stage, neck, sc, fr)
    fig, axes = plt.subplots(1, len(zls), figsize=(7 * len(zls), 9))
    axes = np.atleast_1d(axes)
    for ax, zl in zip(axes, zls):
        draw(ax, items, zl, 'z_l = %.1f   (x up, y back; orange head, blue extras, purple hair, green neck, gray = her own head)' % zl)
    fig.tight_layout()
    fig.savefig(out, dpi=72)
    print('wrote', out)
