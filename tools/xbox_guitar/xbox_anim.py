"""the 'turn on the Xbox' gesture for the player: lean to the console, press the power button with the right hand, stand back and watch the TV (holds that pose until toggled off)."""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik
import thr_core as tc
import xbox_scene as sc
from ik import lerp_pose, smooth

FPS = 30
HAND_DIR = np.array([0.80, 0.30, -0.52])           # wrist -> fingertip while pressing (forward, a little to the left, down)
HAND_DIR = HAND_DIR / np.linalg.norm(HAND_DIR)
FINGER = 5.2                                       # wrist to the fingertip with the index out
STYLE = {'foot_x': -1.0}


def calm(**kw):
    P = tc.neutral()
    P.update(pz=-2.0, cpitch=4.0, hpitch=3.0)
    P.update(kw)
    return P


def with_arm(arms, P, side, wrist, pole, **kw):
    out, miss, info = arms.ik(P, side, wrist, pole, **kw)
    Q = dict(P)
    Q.update(out)
    return Q, miss


def fingertip(arms, P, side):
    rig = arms.rig
    M, trl, AR, AP = arms.solved(P)
    chain = rig.fingers[side][2]
    return AP[chain[-1]] + (AP[chain[-1]] - AP[chain[-2]]) * 0.9


def reach_tip(arms, P, side, tip_target, pole, iters=6, **kw):
    """IK for the wrist iterated until the middle fingertip of the solved pose sits on tip_target"""
    wrist = np.asarray(tip_target, float) - HAND_DIR * FINGER
    for _ in range(iters):
        Q, miss = with_arm(arms, P, side, wrist, pole, **kw)
        err = np.asarray(tip_target, float) - fingertip(arms, Q, side)
        if np.linalg.norm(err) < 0.15:
            break
        wrist = wrist + err
    return Q, miss, float(np.linalg.norm(np.asarray(tip_target, float) - fingertip(arms, Q, side)))


def keys(arms):
    """list of (time s, pose dict); the right arm of the reaching poses is solved by IK against the console's power button"""
    B = sc.BUTTON
    wrist_press = B - HAND_DIR * FINGER
    pole = np.array([-0.35, -0.55, -0.75])         # elbow out to the right and down
    K = []
    K.append((0.00, calm()))
    # start leaning in, hand coming up
    P1 = calm(cpitch=14.0, hpitch=9.0, px=1.5, ppitch=3.0)
    P1, m1, e1 = reach_tip(arms, P1, 'R', B + np.array([-6.0, 3.0, 9.0]), pole, wflex=10.0, proll=-45.0, claw=0.3)
    K.append((0.45, P1))
    # reach: committed forward lean and a small crouch, fingertip a hand's width from the button
    body = dict(cpitch=33.0, ppitch=9.0, pz=-5.0, px=6.0, hpitch=22.0, cyaw=-6.0, croll=-3.0)
    P2 = calm(**body)
    P2, m2, e2 = reach_tip(arms, P2, 'R', B - HAND_DIR * 3.4, pole, wflex=8.0, proll=-50.0, claw=0.2)
    K.append((0.95, P2))
    P3 = dict(P2)
    P3, m3, e3 = reach_tip(arms, P3, 'R', B + np.array([0.3, 0.0, 0.0]), pole, wflex=8.0, proll=-50.0, claw=0.2)      # press (the tip a touch into the button)
    K.append((1.20, P3))
    K.append((1.40, dict(P3)))                                                                      # hold the press
    P5 = dict(P2)
    P5, m5, e5 = reach_tip(arms, P5, 'R', B - HAND_DIR * 4.0, pole, wflex=8.0, proll=-50.0, claw=0.2)   # release
    K.append((1.65, P5))
    # stand back, arm comes down, head up to the screen
    P6 = calm(cpitch=10.0, hpitch=16.0, px=1.0, ppitch=2.0, hyaw=-4.0)
    P6.update({'r_aelev': 22.0, 'r_aazim': 40.0, 'r_flex': 40.0, 'r_froll': 20.0, 'r_wflex': 5.0, 'r_proll': -30.0, 'r_claw': 0.35})
    K.append((2.35, P6))
    P7 = calm(cpitch=6.0, hpitch=24.0, hroll=2.0, py=-0.8, proll=-1.0, croll=1.0)
    P7.update({'r_claw': 0.2, 'l_claw': 0.2})
    K.append((3.20, P7))
    K.append((3.60, dict(P7)))
    return K, (m1, m2, m3, m5, e1, e2, e3, e5)


def pose_at(K, t):
    if t <= K[0][0]:
        return dict(K[0][1])
    for (ta, A), (tb, B) in zip(K, K[1:]):
        if ta <= t <= tb:
            return lerp_pose(A, B, smooth((t - ta) / (tb - ta)))
    return dict(K[-1][1])


def build(rigkey='ethics', fps=FPS):
    rig = tc.rig_for(rigkey)
    arms = ik.Arms(rig, STYLE)
    K, misses = keys(arms)
    T = K[-1][0]
    n = int(round(T * fps))
    times = [i / fps for i in range(n + 1)]
    frames = tc.build_frames(rig, lambda t: pose_at(K, t), times, STYLE)
    js = tc.to_json(rig, frames, fps, name='xbox_%s' % rigkey, restart=n + 1)        # RestartFrame = the last frame: the final pose is held until the event is toggled off
    return rig, arms, K, js, misses


if __name__ == '__main__':
    rig, arms, K, js, misses = build()
    print('IK keys: unreachable units %s | fingertip error to target %s' % ([round(m, 2) for m in misses[:4]], [round(e, 2) for e in misses[4:]]))
    print('frames', len(js['FrameData']), 'bones', len(js['FrameData'][0]['BoneInfo']))
