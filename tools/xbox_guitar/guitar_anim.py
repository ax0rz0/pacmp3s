"""'me playing the guitar' for the player: two layers that play together.

 layer A  (loops, one pattern = 4 MIDI beats): the body sways and the head nods, the right wrist hovers over the sound hole and the right hand's thumb and fingers pluck the arpeggio
 layer B  (long, sparse keyframes, only the LEFT arm): the left hand moves along the neck / changes shape with the chords of the song (chord roots read from the MIDI's bass track)

pac adds the bone manipulations of animations that play at the same time, and the two layers never touch the same bone, so they simply combine.  The guitar prop (a model2 on the 'spine 4' bone)
rides with the chest, so hands (solved against the chest) and guitar stay together however the body sways.
"""
import itertools
import json
import math
import os
import sys

import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik
import thr_core as tc
import guitar_scene as gs
import midi_guitar as mg
from ik import smooth

STYLE = {'foot_x': -1.0}
PATTERN_BEATS = 4
PLUCK_BEATS = [(0.0, (0, 3)), (1.0, (1,)), (1.5, (2,)), (2.0, (0,)), (2.5, (3,)), (3.0, (1,))]     # (beat in the pattern, fingers that pluck: 0 thumb, 1 index, 2 middle, 3 ring)
ARM_BONES_L = ('L_Clavicle', 'L_UpperArm', 'L_Forearm', 'L_Hand', 'L_Finger', 'Anim_Attachment_LH')


def nominal(**kw):
    P = tc.neutral()
    P.update(pz=-3.0, cpitch=10.0, ppitch=3.0, px=1.0, hpitch=16.0, hyaw=-6.0)
    P.update(kw)
    return P


class Rigged:
    def __init__(self, key='ethics'):
        self.key = key
        self.rig = tc.rig_for(key)
        self.arms = ik.Arms(self.rig, STYLE)
        self.sp4 = self.rig.spine[-1]
        self.local_pos, self.local_R = self.guitar_local(nominal())

    def guitar_local(self, P):
        """the guitar's transform in the frame of the chest bone (what the model2 part's Position / Angles are), from the design pose in the model frame at posture P"""
        M, trl, AR, AP = self.arms.solved(P)
        Rb, pb = AR[self.sp4], AP[self.sp4]
        return Rb.T @ (gs.ORIGIN - pb), Rb.T @ gs.R_G

    def guitar_world(self, P, solved=None):
        M, trl, AR, AP = solved or self.arms.solved(P)
        Rb, pb = AR[self.sp4], AP[self.sp4]
        return pb + Rb @ self.local_pos, Rb @ self.local_R

    def to_world(self, P, local, solved=None):
        o, R = self.guitar_world(P, solved)
        return o + R @ (np.asarray(local, float) * gs.SIZE)

    def tips(self, P, side, solved=None):
        M, trl, AR, AP = solved or self.arms.solved(P)
        out = {}
        for fid, chain in self.rig.fingers[side].items():
            out[fid] = AP[chain[-1]] + (AP[chain[-1]] - AP[chain[-2]]) * 0.9
        return out


def rot_about(v, axis, deg):
    from retarget import axis_rot
    return axis_rot(axis, math.radians(deg)) @ v


def fit_hand(G, P, side, wrist, pole0, targets, claw, fm, start=(0.0, 0.0, -40.0), iters=140, phi_w=0.002):
    """search the elbow swing, wrist flexion and palm roll that put the fingertips nearest to `targets` (fid -> world point); returns the arm parameters and the rms error"""
    pre = 'l_' if side == 'L' else 'r_'
    arms = G.arms
    S = arms.shoulder(P, side)
    axis = ik.norm(np.asarray(wrist, float) - S)

    def build(x):
        phi, wf, pr = x
        pole = rot_about(pole0, axis, phi)
        out, miss, info = arms.ik(P, side, wrist, pole, wflex=float(np.clip(wf, -50, 70)), proll=float(pr), claw=claw)
        Q = dict(P)
        Q.update(out)
        for fid, m in fm.items():
            Q[pre + 'fm%d' % fid] = m
        return Q, miss

    def cost(x):
        Q, miss = build(x)
        tips = G.tips(Q, side)
        e = 0.0
        n = 0
        for fid, tgt in targets.items():
            if fid in tips:
                e += float(np.sum((tips[fid] - tgt) ** 2))
                n += 1
        pen = phi_w * (x[0] ** 2) + 0.0005 * (x[1] ** 2)
        return e / max(n, 1) + pen + 50.0 * miss * miss

    grid = sorted((cost(np.array(g, float)), g) for g in itertools.product((-80.0, -50.0, -20.0, 10.0, 40.0, 70.0), (-20.0, 10.0, 40.0, 70.0), range(-180, 180, 45)))
    starts = [start, (30.0, 10.0, -20.0), (-30.0, 10.0, -60.0), (0.0, 30.0, 0.0)] + [g for _, g in grid[:4]]
    best = None
    for s0 in starts:
        r = minimize(cost, np.array(s0, float), method='Nelder-Mead', options=dict(maxiter=iters, xatol=0.3, fatol=1e-3))
        if best is None or r.fun < best.fun:
            best = r
    Q, miss = build(best.x)
    tips = G.tips(Q, side)
    use = [(f, t) for f, t in targets.items() if f in tips]
    rms = math.sqrt(sum(float(np.sum((tips[f] - t) ** 2)) for f, t in use) / max(len(use), 1))
    return Q, rms, best.x, miss


if __name__ == '__main__':
    G = Rigged('ethics')
    P = nominal()
    print('guitar in the chest bone frame: position', G.local_pos.round(2), 'angles', ik.euler_for(G.local_R))
