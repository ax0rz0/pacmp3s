"""scan arm parameters of chosen keys for the best minimum pole margin of that arm over a beat window, on all rigs"""
import itertools, sys
import numpy as np
import thr_core as tc, thr_dance2 as td
from poles import RIGS

PRE = {'L': 'l_', 'R': 'r_'}
_sols = {k: (tc.rig_for(k), tc.Solver(tc.rig_for(k), td.style_for(kind))) for k, kind in RIGS}


def modify(keys, side, beats, **params):
    out = []
    for b, pose, hit, ease in keys:
        if b in beats:
            pose = dict(pose)
            for k, v in params.items():
                pose[PRE[side] + k] = v
        out.append((b, pose, hit, ease))
    return out


def window_margin(keys, side, b0, b1, bones=('ua', 'fa', 'hd'), rigs=None, step=1):
    tl = td.Timeline(keys)
    worst, where = 999.0, ''
    for i in range(int(b0 * 15), int(b1 * 15) + 1, step):
        P = tl.pose(i / 15.0)
        for k, (rig, sol) in _sols.items():
            if rigs and k not in rigs:
                continue
            sol.solve(P)
            a = rig.arms[side]
            for nm in bones:
                m = sol.margin.get(a[nm], 999.0)
                if m < worst:
                    worst, where = m, '%s.%s@%.1f' % (k, nm, i / 15.0)
    return worst, where


def scan(keys, side, groups, grid, b0, b1, **kw):
    """groups: list of (beats, [param names]) ; grid: dict param -> candidate values (same for each beat group member). returns best list"""
    names = [n for _, ps in groups for n in ps]
    cands = []
    for combo in itertools.product(*[grid[n] for n in names]):
        ks = keys
        j = 0
        for beats, ps in groups:
            vals = {p: combo[j + t] for t, p in enumerate(ps)}
            j += len(ps)
            ks = modify(ks, side, beats, **vals)
        m, where = window_margin(ks, side, b0, b1, **kw)
        dev = sum(abs(c - base[n]) / s for c, n, base, s in [(combo[i], names[i], None, 1) for i in range(len(names))]) if False else 0
        cands.append((m, combo, where))
    cands.sort(key=lambda x: -x[0])
    return names, cands


STEPS = {'aelev': 6, 'aazim': 8, 'flex': 8, 'froll': 10, 'wflex': 10, 'proll': 15}


def wfit(keys, side, beats, params, window, target=30.0, lam=0.6, maxit=25, rigs=None, bones=('ua', 'fa', 'hd')):
    """coordinate descent on the window margin over `params` of the arm `side` in the keys at `beats` (all kept equal); returns (best values dict, margin, where)"""
    pre = PRE[side]
    base = {p: next(pose[pre + p] for b, pose, h, e in keys if b in beats) for p in params}
    cur = dict(base)
    ks = modify(keys, side, beats, **cur)
    m, where = window_margin(ks, side, *window, bones=bones, rigs=rigs)
    for _ in range(maxit):
        if m >= target:
            break
        best = None
        for p in params:
            for sgn in (-1, 1):
                cand = dict(cur)
                cand[p] = cur[p] + sgn * STEPS[p]
                ks2 = modify(keys, side, beats, **cand)
                m2, w2 = window_margin(ks2, side, *window, bones=bones, rigs=rigs)
                dev = sum(abs(cand[q] - base[q]) / STEPS[q] for q in params)
                sc = -min(m2, target) + lam * dev - 0.02 * m2
                if best is None or sc < best[0]:
                    best = (sc, cand, m2, w2)
        if best[2] <= m + 0.05:
            break
        cur, m, where = best[1], best[2], best[3]
    return cur, m, where, base
