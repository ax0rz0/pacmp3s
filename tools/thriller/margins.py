"""distance of every arm bone's AIMED direction from its Euler pole over the loop, per rig (before the guard acts): where an arm path passes closer than a threshold"""
import importlib, sys
import numpy as np
import thr_core as tc
from poles import RIGS


def margins(td, tl, thresh=30.0, step=1):
    out = {}
    for key, kind in RIGS:
        rig = tc.rig_for(key)
        sol = tc.Solver(rig, td.style_for(kind))
        rows = {}
        for i in range(0, 481, step):
            sol.solve(tl.pose(i / 30 / td.BEAT))
            for b, ang in sol.margin.items():
                nm = rig.short(b)
                rows.setdefault(nm, []).append((ang, i))
        res = {}
        for nm, lst in rows.items():
            a = np.array([x[0] for x in lst])
            idx = np.where(a < thresh)[0]
            if len(idx):
                # contiguous groups of frames below the threshold -> beats
                groups, start, prev = [], None, None
                for j in idx:
                    f = lst[j][1]
                    if start is None:
                        start = f
                    elif f - prev > 2 * step:
                        groups.append((start, prev, float(a[[k for k, x in enumerate(lst) if start <= x[1] <= prev]].min())))
                        start = f
                    prev = f
                groups.append((start, prev, float(a[[k for k, x in enumerate(lst) if start <= x[1] <= prev]].min())))
                res[nm] = groups
        out[key] = res
    return out


if __name__ == '__main__':
    td = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'thr_dance2')
    th = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    for key, res in margins(td, td.Timeline(), th).items():
        print('==', key)
        for nm in sorted(res):
            print('  %-10s ' % nm + '  '.join('beats %.1f-%.1f (min %.0f)' % (a / 15.0, b / 15.0, m) for a, b, m in res[nm]))
