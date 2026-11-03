"""per key pose: principal pitch of the arm bones on every rig (R and L), to see which key causes a near-pole bone"""
import importlib, sys
import numpy as np
import thr_core as tc
from retarget import source_angles
from poles import RIGS


def key_report(td, thresh=62.0, keys=None):
    keys = keys or td.keys()
    sols = {k: (tc.rig_for(k), tc.Solver(tc.rig_for(k), td.style_for(kind))) for k, kind in RIGS}
    out = []
    for beat, pose, hit, ease in keys:
        row = {}
        for k, (rig, sol) in sols.items():
            M, trl, AR, AP = sol.solve(pose)
            for b, Mb in M.items():
                nm = rig.short(b)
                if not any(s in nm for s in ('UpperArm', 'Forearm', 'Hand', 'Thigh', 'Calf', 'Spine', 'Foot', 'Pelvis', 'Clavicle', 'Neck', 'Head', 'HC_')):
                    continue
                p = abs(source_angles(Mb)[0])
                if p > thresh:
                    row.setdefault(nm, {})[k] = round(p)
        if row:
            out.append((beat, row))
    return out


if __name__ == '__main__':
    td = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'thr_dance2')
    for beat, row in key_report(td, float(sys.argv[2]) if len(sys.argv) > 2 else 62.0):
        print('beat %5.1f' % beat, '; '.join('%s %s' % (nm, ','.join('%s:%d' % (r[:3], v) for r, v in d.items())) for nm, d in row.items()))
