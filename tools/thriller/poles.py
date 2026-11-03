"""pole report: principal pitch of every bone's manipulation over the loop for all rigs; flags bones above a threshold with the beat where it happens"""
import importlib, sys, time
import numpy as np
import thr_core as tc
from retarget import source_angles

RIGS = (('ethics', 'player'), ('classd', 'player'), ('isd', 'player'), ('medic', 'player'), ('zombie', 'zombie'))


def report(td, tl, thresh=70.0, step=2, rigs=RIGS, quiet=False):
    bad = {}
    for key, kind in rigs:
        rig = tc.rig_for(key)
        sol = tc.Solver(rig, td.style_for(kind))
        worst = {}
        for i in range(0, 481, step):
            M, trl, AR, AP = sol.solve(tl.pose(i / 30 / td.BEAT))
            for b, Mb in M.items():
                a = source_angles(Mb)
                nm = rig.short(b)
                if nm not in worst or abs(a[0]) > abs(worst[nm][0]):
                    worst[nm] = (a[0], i / 15.0)
        rows = sorted([(abs(p), nm, p, beat) for nm, (p, beat) in worst.items() if abs(p) > thresh], reverse=True)
        bad[key] = rows
        if not quiet:
            print('%-7s max |pitch|: %s' % (key, ', '.join('%s %.0f@%.1f' % (nm, p, beat) for _, nm, p, beat in rows) if rows else 'all below %.0f' % thresh))
    return bad


if __name__ == '__main__':
    td = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'thr_dance2')
    t0 = time.time()
    report(td, td.Timeline(), float(sys.argv[2]) if len(sys.argv) > 2 else 70.0)
    print('%.1fs' % (time.time() - t0))
