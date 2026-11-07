"""arm IK on top of thr_core's solver: put a wrist at a world (model frame: +X forward, +Y left, +Z up) position and get the pose parameters of the arm.

thr_core describes an arm by chest-relative numbers (aelev, aazim, flex, froll, wflex, proll, claw); this inverts that description for a two bone arm so a pose can be written as "right wrist here,
elbow towards there" instead.  The shoulder position comes from the solver itself (it depends on pelvis / chest pose, not on the arm), so the hand really ends up where the target is.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\thriller')
sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\emote')
import thr_core as tc
from retarget import arc, norm, source_angles, angles_matrix

X, Z = np.array([1.0, 0, 0]), np.array([0, 0, 1.0])


def R_ypr(yaw, pitch, roll):
    return tc.R_ypr(yaw, pitch, roll)


class Arms:
    def __init__(self, rig, style=None):
        self.rig = rig
        self.style = dict(style or {})
        self.sol = tc.Solver(rig, self.style)
        self.L = {}
        for s, a in rig.arms.items():
            self.L[s] = (float(np.linalg.norm(rig.Wp[a['fa']] - rig.Wp[a['ua']])), float(np.linalg.norm(rig.Wp[a['hd']] - rig.Wp[a['fa']])))

    def chest(self, P):
        st = self.style
        Dpel = R_ypr(P['pyaw'], P['ppitch'], P['proll'])
        Rchest = R_ypr(P['cyaw'], P['cpitch'] + st.get('lean', 0.0), P['croll'])
        return Dpel @ Rchest

    def solved(self, P):
        return self.sol.solve(P)

    def shoulder(self, P, side, solved=None):
        M, trl, AR, AP = solved or self.sol.solve(P)
        return AP[self.rig.arms[side]['ua']].copy()

    def wrist_of(self, P, side):
        M, trl, AR, AP = self.sol.solve(P)
        return AP[self.rig.arms[side]['hd']].copy(), AP[self.rig.arms[side]['fa']].copy(), AP[self.rig.arms[side]['ua']].copy()

    def ik(self, P, side, wrist, pole, wflex=0.0, proll=-40.0, claw=0.5, solved=None, reach=0.985):
        """returns the dict of arm parameters (prefixed l_/r_) that puts the wrist at `wrist` (world), the elbow pushed towards `pole` (a world direction); reports the unreachable distance"""
        pre = 'l_' if side == 'L' else 'r_'
        sg = 1.0 if side == 'L' else -1.0
        S = self.shoulder(P, side, solved)
        L1, L2 = self.L[side]
        v = np.asarray(wrist, float) - S
        d = float(np.linalg.norm(v))
        dmax = (L1 + L2) * reach
        miss = max(0.0, d - dmax)
        dc = min(max(d, abs(L1 - L2) + 1e-3), dmax)
        u0 = v / max(d, 1e-9)
        a = (L1 * L1 - L2 * L2 + dc * dc) / (2 * dc)
        h = math.sqrt(max(L1 * L1 - a * a, 0.0))
        pp = np.asarray(pole, float)
        pp = pp - u0 * float(np.dot(pp, u0))
        pp = norm(pp) if np.linalg.norm(pp) > 1e-6 else norm(np.cross(u0, Z))
        W = S + u0 * dc
        E = S + u0 * a + pp * h
        u = norm(E - S)
        fa = norm(W - E)
        Dc = self.chest(P)
        uc, fc = Dc.T @ u, Dc.T @ fa
        elev = math.degrees(math.acos(max(-1.0, min(1.0, -uc[2]))))
        az = math.degrees(math.atan2(sg * uc[1], uc[0]))
        cf = max(-1.0, min(1.0, float(np.dot(uc, fc))))
        flex = math.degrees(math.acos(cf))
        b0 = norm(arc(-Z, uc) @ X)
        bperp = fc - uc * cf
        if np.linalg.norm(bperp) < 1e-6:
            froll = 0.0
        else:
            b = norm(bperp)
            froll = math.degrees(math.atan2(float(np.dot(b, (-sg) * np.cross(uc, b0))), float(np.dot(b, b0))))
        out = {pre + 'aelev': elev, pre + 'aazim': az, pre + 'flex': flex, pre + 'froll': froll, pre + 'wflex': wflex, pre + 'proll': proll, pre + 'claw': claw}
        return out, miss, dict(S=S, E=E, W=W, d=d)


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp_pose(A, B, t):
    return {k: A[k] + (B[k] - A[k]) * t for k in A}


def euler_for(R):
    """pac Angle(pitch, yaw, roll) of a rotation matrix whose columns are the part's local axes in the parent frame"""
    p, y, r = source_angles(R)
    return float(p), float(y), float(r)
