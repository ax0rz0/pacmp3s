"""thr_fig: abstract stick figures of a posed ValveBiped-style rig (matplotlib, CPU only).  Bones as thick rounded lines, a ring for the head, small discs at the joints.
The figure is built from the rig's own joint positions after the manipulations (what the engine would draw), so it shows the data, not the intent."""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thr_core as tc

PROJ = {'front': (lambda p: (p[1], p[2])),            # screen right = character left
        'side': (lambda p: (p[0], p[2])),             # screen right = forward
        'top': (lambda p: (-p[1], p[0])),             # forward is up, character left is on the left
        'q': (lambda p: (-p[0] * 0.57 + p[1] * 0.82, p[2]))}      # 3/4 view from the front left


def joints(rig, AR, AP):
    """named polylines (in world coordinates)"""
    L = {}
    chain = [rig.pel] + rig.spine
    head = None
    if rig.head_chain:
        chain += rig.head_chain
        head = rig.head_chain[-1]
    pts = [AP[b] for b in chain]
    if head is not None:
        hb = rig.b('HC_Head_Bone')
        if rig.zombie_head and hb is not None:
            pts.append(AP[hb])
            top = AP[hb]
        else:
            top = AP[head] + AR[head][:, 0] * 7.0       # head bone: X axis = up
            pts.append(top)
        L['head_c'] = top
    L['spine'] = np.array(pts)
    for s, a in rig.arms.items():
        arm = [AP[rig.spine[-1]] if rig.spine else AP[rig.pel], AP[a['cl']], AP[a['ua']], AP[a['fa']], AP[a['hd']]]
        ch = rig.fingers.get(s, {}).get(2) or []
        if ch:
            tip = AP[ch[-1]] + (AP[ch[-1]] - AP[ch[-2]]) * 0.9 if len(ch) > 1 else AP[ch[-1]]
            arm.append(tip)
        L['arm' + s] = np.array(arm)
    for s, lg in rig.legs.items():
        leg = [AP[rig.pel], AP[lg['th']], AP[lg['ca']], AP[lg['ft']]]
        if lg['toe'] is not None:
            leg.append(AP[lg['toe']])
        L['leg' + s] = np.array(leg)
    return L


def draw(ax, rig, AR, AP, view, color, offset=(0.0, 0.0), lw=4.0, yaw=0.0):
    c, s = np.cos(np.radians(yaw)), np.sin(np.radians(yaw))
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    off = np.array([offset[0], offset[1], 0.0])
    f = PROJ[view]
    J = joints(rig, AR, AP)
    base = np.array(matplotlib.colors.to_rgb(color))
    for k, pts in J.items():
        if k == 'head_c':
            continue
        col = base
        if k.endswith('L'):
            col = base * 0.55 + 0.45          # left limbs lighter
        elif k.endswith('R'):
            col = base * 0.72                 # right limbs darker
        q = np.array([f(R @ p + off) for p in pts])
        ax.plot(q[:, 0], q[:, 1], '-', color=col, lw=lw, solid_capstyle='round', solid_joinstyle='round', alpha=0.97)
        if k.startswith('arm'):
            ax.plot(q[-1:, 0], q[-1:, 1], 'o', color=col, ms=lw * 1.5)
    for k, pts in J.items():
        if k == 'head_c':
            hx, hy = f(R @ pts + off)
            ax.add_patch(plt.Circle((hx, hy), 4.2 if not rig.zombie_head else 3.4, fill=False, ec=color, lw=lw * 0.6))
    return J


def ground(ax, view, xr):
    if view in ('front', 'side'):
        ax.plot(xr, [0, 0], '-', color='0.55', lw=1)


def sheet(path, entries, times, views=('front', 'side'), title='', size=(2.5, 2.8), xr=None, dpi=80, label_fn=None):
    """entries: list of (rig, solve_fn(t) -> (AR, AP), color, offset, yaw); one row per time, one column per view"""
    nr, nc = len(times), len(views)
    fig, axes = plt.subplots(nr, nc, figsize=(size[0] * nc, size[1] * nr), squeeze=False)
    for r, t in enumerate(times):
        poses = [(rig, fn(t), col, off, yaw) for rig, fn, col, off, yaw in entries]
        for c, v in enumerate(views):
            ax = axes[r][c]
            for rig, (AR, AP), col, off, yaw in poses:
                draw(ax, rig, AR, AP, v, col, off, yaw=yaw)
            ax.set_aspect('equal')
            lim = xr or ((-95, 95) if v in ('front', 'top') else (-48, 48))
            ax.set_xlim(*lim)
            ax.set_ylim((-3, 78) if v != 'top' else (-60, 60))
            ground(ax, v, lim)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title((label_fn(t) if label_fn else 't=%.2fs' % t) + '  ' + v, fontsize=7, pad=2)
    if title:
        fig.suptitle(title, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.985 if title else 1))
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def grid(path, items, view='q', ncols=4, size=(3.0, 3.1), dpi=85, title='', xr=(-105, 105), yr=(-3, 80)):
    """items: list of (label, [(rig, AR, AP, color, offset, yaw), ...]); one cell each"""
    n = len(items)
    nr = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nr, ncols, figsize=(size[0] * ncols, size[1] * nr), squeeze=False)
    for i in range(nr * ncols):
        ax = axes[i // ncols][i % ncols]
        ax.set_xticks([])
        ax.set_yticks([])
        if i >= n:
            ax.axis('off')
            continue
        label, figs = items[i]
        for rig, AR, AP, col, off, yaw in figs:
            draw(ax, rig, AR, AP, view, col, off, yaw=yaw, lw=3.2)
        ax.set_aspect('equal')
        ax.set_xlim(*xr)
        ax.set_ylim(*yr)
        ax.plot(xr, [0, 0], '-', color='0.6', lw=1)
        ax.set_title(label, fontsize=8, pad=2)
    if title:
        fig.suptitle(title, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.985 if title else 1))
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
