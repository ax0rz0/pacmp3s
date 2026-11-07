"""CPU-only preview: the skeleton read back from the animation JSON, with the scene props drawn as wireframes (matplotlib, no GPU)"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\thriller')
import thr_core as tc
import thr_fig as tf
import xbox_scene as sc

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(OUT, exist_ok=True)


def pose_from_json(rig, js, i):
    M, trl = tc.manip_from_json_frame(rig, js['FrameData'][i])
    return tc.fk_pose(rig, M, trl)


def draw_boxes(ax, parts, view, lw=0.9):
    f = tf.PROJ[view]
    for p in parts:
        if p['kind'] == 'box':
            cs = sc.box_corners(p['pos'], p['size'])
            col = np.clip(np.array(p['color']) * 1.6 + 0.12, 0, 1)
            for a, b in sc.EDGES:
                q = np.array([f(cs[a]), f(cs[b])])
                ax.plot(q[:, 0], q[:, 1], '-', color=col, lw=lw)
        elif p['kind'] == 'screen':
            R = p['R']
            h = np.array([0.0, 0.0, 0.0])
            pts = []
            for sx, sy in ((-1, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)):
                local = np.array([sx * p['size'][0] / 2, sy * p['size'][1] / 2, 0.0])
                pts.append(np.array(p['pos']) + R @ local)
            q = np.array([f(x) for x in pts])
            ax.plot(q[:, 0], q[:, 1], '-', color='#3fa34d', lw=1.6)
        elif p['kind'] == 'points':
            q = np.array([f(x) for x in p['pts']])
            ax.plot(q[:, 0], q[:, 1], '.', color=p.get('color', '#996633'), ms=0.6, alpha=0.5)


def sheet(path, rig, js, parts, times, fps, views=('side', 'q'), title='', xr=(-25, 62), yr=(-3, 72), size=(3.4, 3.0), extra=None):
    nr, nc = len(times), len(views)
    fig, axes = plt.subplots(nr, nc, figsize=(size[0] * nc, size[1] * nr), squeeze=False)
    for r, t in enumerate(times):
        i = min(int(round(t * fps)), len(js['FrameData']) - 1)
        AR, AP = pose_from_json(rig, js, i)
        for c, v in enumerate(views):
            ax = axes[r][c]
            draw_boxes(ax, parts, v)
            tf.draw(ax, rig, AR, AP, v, '#2b6cb0', (0, 0), lw=3.0)
            if extra:
                extra(ax, v, AR, AP, t)
            ax.set_aspect('equal')
            ax.set_xlim(*(xr if v != 'front' else (-45, 45)))
            ax.set_ylim(*yr)
            ax.plot(ax.get_xlim(), [0, 0], '-', color='0.6', lw=1)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title('t=%.2fs %s' % (t, v), fontsize=7, pad=2)
    if title:
        fig.suptitle(title, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.985 if title else 1))
    fig.savefig(path, dpi=80)
    plt.close(fig)
