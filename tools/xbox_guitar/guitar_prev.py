import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\thriller')
import thr_core as tc
import thr_fig as tf
import guitar_scene as gs

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(OUT, exist_ok=True)
_pts = None


def finger_lines(rig, AP):
    L = []
    for side, chains in rig.fingers.items():
        a = rig.arms[side]
        for fid, chain in chains.items():
            pts = [AP[a['hd']]] + [AP[b] for b in chain]
            pts.append(pts[-1] + (pts[-1] - pts[-2]) * 0.9)
            L.append(np.array(pts))
    return L


def draw_pose(ax, rig, AR, AP, G, P, view, targets=None, zoom=None, guitar=True):
    global _pts
    f = tf.PROJ[view]
    if guitar:
        if _pts is None:
            pos = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guitar_pos.npy'))
            rng = np.random.default_rng(3)
            _pts = pos[rng.choice(len(pos), 2600, replace=False)]
        o, R = G.guitar_world(P, (None, None, AR, AP))
        w = np.array([o + R @ (p * gs.SIZE) for p in _pts])
        q = np.array([f(x) for x in w])
        ax.plot(q[:, 0], q[:, 1], '.', color='#b5835a', ms=1.2, alpha=0.55)
    tf.draw(ax, rig, AR, AP, view, '#2b6cb0', (0, 0), lw=2.6)
    for pts in finger_lines(rig, AP):
        q = np.array([f(x) for x in pts])
        ax.plot(q[:, 0], q[:, 1], '-', color='#c05621', lw=1.6)
    if targets:
        for t in targets:
            x, y = f(t)
            ax.plot([x], [y], 'x', color='#e53e3e', ms=5, mew=1.5)
    ax.set_aspect('equal')
    if zoom:
        ax.set_xlim(*zoom[0]); ax.set_ylim(*zoom[1])
    ax.set_xticks([]); ax.set_yticks([])


def grid(path, items, views=('side', 'front', 'q'), zoom=None, size=(3.2, 3.0), title=''):
    """items: list of (label, rig, AR, AP, G, P, targets)"""
    nr, nc = len(items), len(views)
    fig, axes = plt.subplots(nr, nc, figsize=(size[0] * nc, size[1] * nr), squeeze=False)
    for r, (label, rig, AR, AP, G, P, targets) in enumerate(items):
        for c, v in enumerate(views):
            z = zoom[v] if zoom else None
            draw_pose(axes[r][c], rig, AR, AP, G, P, v, targets, z)
            axes[r][c].set_title('%s  %s' % (label, v), fontsize=7, pad=2)
    if title:
        fig.suptitle(title, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.985 if title else 1))
    fig.savefig(path, dpi=80)
    plt.close(fig)
