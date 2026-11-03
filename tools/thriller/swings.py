"""swing angle (minimal arc from the bone's rest direction, in the posed parent's frame, to the aimed direction): near 180 the arc flips (antipodal ambiguity) -> twist jumps"""
import importlib, sys
import numpy as np
import thr_core as tc
from poles import RIGS


def swings(td, tl, thresh=140.0, step=1):
    out = {}
    for key, kind in RIGS:
        rig = tc.rig_for(key)
        sol = tc.Solver(rig, td.style_for(kind))
        rows = {}
        for i in range(0, 481, step):
            sol.solve(tl.pose(i / 30 / td.BEAT))
            for b, ang in sol.swing.items():
                rows.setdefault(rig.short(b), []).append(ang)
        out[key] = {nm: (max(v), int(np.argmax(v)) * step / 15.0) for nm, v in rows.items()}
    return out


if __name__ == '__main__':
    td = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'thr_dance2')
    th = float(sys.argv[2]) if len(sys.argv) > 2 else 140.0
    for key, d in swings(td, td.Timeline(arm_scale=0.75, lead_arm=0.28), th).items():
        print('%-7s' % key, '  '.join('%s %.0f@%.1f' % (nm, a, b) for nm, (a, b) in sorted(d.items(), key=lambda kv: -kv[1][0]) if a > 100 and ('Arm' in nm or 'Hand' in nm)))
