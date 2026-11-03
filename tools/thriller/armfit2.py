"""design-time helper v2: nudge an arm's pose parameters (as little as possible) until the aimed directions of its upper arm / forearm / hand stay >= target degrees from the Euler poles on every rig"""
import importlib, sys
import numpy as np
import thr_core as tc
from poles import RIGS

PRE = {'L': 'l_', 'R': 'r_'}
STEPS = {'aelev': 6, 'aazim': 8, 'flex': 8, 'froll': 10, 'wflex': 10, 'proll': 15}


def sols_for(td):
    return {k: (tc.rig_for(k), tc.Solver(tc.rig_for(k), td.style_for(kind))) for k, kind in RIGS}


def min_margin(pose, side, sols, bones=('ua', 'fa', 'hd')):
    worst, where = 999.0, ''
    for k, (rig, sol) in sols.items():
        sol.solve(pose)
        a = rig.arms[side]
        for nm in bones:
            m = sol.margin.get(a[nm], 999.0)
            if m < worst:
                worst, where = m, '%s.%s' % (k, nm)
    return worst, where


def fit(pose, side, sols, target=32.0, free=('froll', 'flex', 'aelev', 'aazim', 'wflex', 'proll'), maxit=60, lam=1.2, bones=('ua', 'fa', 'hd')):
    pre = PRE[side]
    base = {k: pose[pre + k] for k in STEPS}
    cur = dict(pose)
    m, where = min_margin(cur, side, sols, bones)
    for _ in range(maxit):
        if m >= target:
            break
        best = None
        for k in free:
            for sgn in (-1, 1):
                cand = dict(cur)
                cand[pre + k] = cur[pre + k] + sgn * STEPS[k]
                m2, wh2 = min_margin(cand, side, sols, bones)
                dev = sum(abs(cand[pre + q] - base[q]) / STEPS[q] for q in STEPS)
                sc = -min(m2, target) + lam * dev - 0.02 * m2
                if best is None or sc < best[0]:
                    best = (sc, cand, m2, wh2)
        if best[2] <= m + 0.05:
            break
        cur, m, where = best[1], best[2], best[3]
    return cur, m, where


if __name__ == '__main__':
    td = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'thr_dance2')
    target = float(sys.argv[2]) if len(sys.argv) > 2 else 32.0
    only = set(float(x) for x in sys.argv[3].split(',')) if len(sys.argv) > 3 else None
    sols = sols_for(td)
    for beat, pose, hit, ease in td.keys():
        if only and beat not in only:
            continue
        for side in ('R', 'L'):
            m, where = min_margin(pose, side, sols)
            if m < target:
                new, m2, wh2 = fit(pose, side, sols, target)
                pre = PRE[side]
                diff = {k: (round(pose[pre + k]), round(new[pre + k])) for k in STEPS if abs(pose[pre + k] - new[pre + k]) > 1e-6}
                print('beat %4.1f %s: margin %.0f (%s) -> %.0f (%s)  changes %s' % (beat, side, m, where, m2, wh2, diff))
