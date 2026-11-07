"""checks and preview of the Xbox gesture with the controller: the pad stays in the left hand and clear of the table, the right hand ends on it; key pose sheet (CPU matplotlib)"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik  # noqa: F401
import xbox_anim as xa
import xbox_anim2 as xa2
import xbox_ctrl as xc
import xbox_scene as sc
import scene_prev as sp
import thr_fig as tf

EDGES = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
CORNERS = np.array([[sx * xc.HALF[0], sy * xc.HALF[1], sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (0.0, xc.HALF[2])])


def slab_world(rig, AR, AP, lp, lR):
    sp4 = rig.spine[-1]
    Rb, pb = AR[sp4], AP[sp4]
    o = pb + Rb @ lp
    R = Rb @ lR
    return o, R, np.array([o + R @ (c * xc.SIZE) for c in CORNERS])


def box_distance(o, R, p):
    local = R.T @ (np.asarray(p, float) - o) / xc.SIZE
    lo = np.array([-xc.HALF[0], -xc.HALF[1], 0.0])
    hi = np.array([xc.HALF[0], xc.HALF[1], xc.HALF[2]])
    d = np.maximum(np.maximum(lo - local, local - hi), 0.0)
    return float(np.linalg.norm(d)) * xc.SIZE


def tips(rig, AP, side):
    return [AP[ch[-1]] + (AP[ch[-1]] - AP[ch[-2]]) * 0.9 for ch in rig.fingers[side].values()]


def main():
    rig, arms, K, js, misses, info = xa2.build()
    lp, lR = xc.local_in_chest(arms, xa.calm(**xa2.P_WATCH))
    n = len(js['FrameData'])
    fps = xa.FPS
    worst_left, minz, minz_t = 0.0, 1e9, 0.0
    for i in range(n):
        AR, AP = sp.pose_from_json(rig, js, i)
        o, R, cs = slab_world(rig, AR, AP, lp, lR)
        over_table = cs[cs[:, 0] > sc.TABLE_X0]
        if len(over_table) and over_table[:, 2].min() < minz:
            minz, minz_t = float(over_table[:, 2].min()), i / fps
        worst_left = max(worst_left, max(box_distance(o, R, t) for t in tips(rig, AP, 'L')))
    AR, AP = sp.pose_from_json(rig, js, n - 1)
    o, R, cs = slab_world(rig, AR, AP, lp, lR)
    right_end = [box_distance(o, R, t) for t in tips(rig, AP, 'R')]
    print('controller in the chest frame: Position %s, Angles %s' % (np.round(lp, 2), np.round(ik.euler_for(lR), 1)))
    print('left fingertips: at most %.2f units from the slab over the whole animation' % worst_left)
    print('right fingertips at the end: %s units from the slab' % [round(d, 2) for d in right_end])
    print('lowest slab corner above the table (x > %.0f): z %.1f at t=%.2f s (table top z %.1f)' % (sc.TABLE_X0, minz, minz_t, sc.TABLE_TOP))

    def extra(ax, v, AR, AP, t):
        o, R, cs = slab_world(rig, AR, AP, lp, lR)
        f = tf.PROJ[v]
        for a, b in EDGES:
            q = np.array([f(cs[a]), f(cs[b])])
            ax.plot(q[:, 0], q[:, 1], '-', color='#2f855a', lw=1.2)

    out = os.path.join(HERE, 'out', 'xbox_keys2.png')
    sp.sheet(out, rig, js, sc.all_parts(), [0.0, 0.45, 0.95, 1.20, 1.65, 2.35, 3.20], fps, views=('side', 'q'),
             title='Xbox gesture with the controller (ethics rig): left hand holds the pad, right hand presses power, then both hold it', extra=extra)
    print('wrote', out)
    return rig, js


if __name__ == '__main__':
    main()
