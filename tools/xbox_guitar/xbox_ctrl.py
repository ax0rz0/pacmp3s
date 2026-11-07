"""the controller you hold in the Xbox pac: models/maxofs2d/button_06.mdl (a flat slab, x +-4, y +-8, z 0..4.5 in model units, 228 vertices; the long axis y is the controller's width).
It is scaled to controller size (Size), attached to the chest bone ('spine 4') and held in front of the belly: the left hand has it from the first frame (chest relative, so it stays put
while you lean in to press the power button) and the right hand comes back and takes the other end.  Grips are fitted with the same hand fit as the guitar."""
import itertools
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik
from guitar_anim import fit_hand

MODEL = 'models/maxofs2d/button_06.mdl'
SIZE = 0.45                                           # 16 model units -> 7.2 units wide (the Ethics Assistant's hand is about 7 units long)
LOCAL_CENTER = np.array([0.0, 0.0, 1.8])              # middle of the slab, model units
HALF = np.array([4.0, 8.0, 4.52])                     # extents (x +-, y +-, z 0..top) for drawing
TILT_DEG = 32.0                                       # the top face looks up and back at the player: the front edge is raised
C_WORLD = np.array([10.0, 0.0, 40.5])                 # centre of the controller in the player's model frame at the watch posture (shoulders are at z 53, the pelvis at 33)
LEFT_POLE = np.array([0.05, 0.60, -0.80])             # elbows out and down (not back: the forearms come from the sides of the belly)
RIGHT_POLE = np.array([0.05, -0.60, -0.80])
WRIST_OFF = np.array([-9.0, 1.0, -1.5])               # wrist relative to the middle of the fingertip targets (controller-local units; y is mirrored for the right hand): behind the slab


def frame():
    a = math.radians(TILT_DEG)
    z = np.array([-math.sin(a), 0.0, math.cos(a)])
    y = np.array([0.0, 1.0, 0.0])
    x = np.cross(y, z)
    return np.stack([x, y, z], axis=1)


R_C = frame()
ORIGIN = C_WORLD - R_C @ (LOCAL_CENTER * SIZE)


def c2w(local):
    return ORIGIN + R_C @ (np.asarray(local, float) * SIZE)


def grip_targets(s):
    """controller-local fingertip targets for the hand on the +y end (s = +1, the left hand) or the -y end (s = -1, the right hand), the way a pad is held: the hands come from behind (towards the
    player, local -x), the thumb rests on the top face near the end, index and middle curl under the slab towards the front edge"""
    return {0: np.array([-0.3, s * 5.6, 2.8]), 1: np.array([1.8, s * 5.0, -0.6]), 2: np.array([-0.2, s * 5.9, -0.7])}


class Ctx:
    """what fit_hand needs: the arm solver and the fingertip positions of a posed rig"""
    def __init__(self, rig, arms):
        self.rig, self.arms = rig, arms

    def tips(self, P, side, solved=None):
        M, trl, AR, AP = solved or self.arms.solved(P)
        out = {}
        for fid, chain in self.rig.fingers[side].items():
            out[fid] = AP[chain[-1]] + (AP[chain[-1]] - AP[chain[-2]]) * 0.9
        return out


def local_in_chest(arms, P):
    """the controller's position / rotation in the frame of the chest bone at posture P: what the model2 part's Position / Angles are"""
    rig = arms.rig
    sp4 = rig.spine[-1]
    M, trl, AR, AP = arms.solved(P)
    Rb, pb = AR[sp4], AP[sp4]
    return Rb.T @ (ORIGIN - pb), Rb.T @ R_C


def fit_grip(arms, P, side, wrist_off=WRIST_OFF, claw=0.8, fm=None, iters=110, phi_w=0.02):
    G = Ctx(arms.rig, arms)
    s = 1.0 if side == 'L' else -1.0
    tg = grip_targets(s)
    c = np.mean(list(tg.values()), axis=0)
    off = np.array([wrist_off[0], s * wrist_off[1], wrist_off[2]])
    wrist = c2w(c + off)
    targets = {fid: c2w(loc) for fid, loc in tg.items()}
    pole = LEFT_POLE if side == 'L' else RIGHT_POLE
    Q, rms, x, miss = fit_hand(G, P, side, wrist, pole, targets, claw=claw, fm=fm if fm is not None else {0: 0.3}, iters=iters, phi_w=phi_w)
    pre = 'l_' if side == 'L' else 'r_'
    return {k: v for k, v in Q.items() if k.startswith(pre)}, rms, miss


if __name__ == '__main__':
    import thr_core as tc
    from xbox_anim import calm, STYLE
    rig = tc.rig_for('ethics')
    arms = ik.Arms(rig, STYLE)
    P = calm(cpitch=6.0, hpitch=24.0, hroll=2.0, py=-0.8, proll=-1.0, croll=1.0)
    res = []
    for ox, oy, oz in itertools.product((-18.0, -15.0, -12.0), (1.0, 3.0, 5.0), (-1.5, 1.0, 3.5)):
        for side in ('L', 'R'):
            q, rms, miss = fit_grip(arms, P, side, wrist_off=np.array([ox, oy, oz]), iters=70)
            res.append((rms, side, ox, oy, oz, miss))
            print('%s off (%.0f %.0f %.0f) rms %.2f miss %.2f' % (side, ox, oy, oz, rms, miss), flush=True)
    for side in ('L', 'R'):
        best = sorted(r for r in res if r[1] == side)[:3]
        print('best', side, [(round(b[0], 2), b[2], b[3], b[4]) for b in best])
