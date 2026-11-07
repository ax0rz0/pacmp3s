"""the Xbox gesture with a controller: you hold the pad (models/maxofs2d/button_06.mdl, see xbox_ctrl.py) in front of your belly with the left hand from the first frame, lean in and press the
console's power button with the right hand, then the right hand comes back to the pad and you stand there holding it with both hands, watching the TV (holds that pose until toggled off)."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik
import thr_core as tc
import xbox_anim as xa
import xbox_ctrl as xc
import xbox_scene as sc
from ik import lerp_pose, smooth

WRIST_OFF = np.array([-12.0, 5.0, 3.5])                   # fitted wrist position behind the pad (controller-local units)
P_WATCH = dict(cpitch=6.0, hpitch=24.0, hroll=2.0, py=-0.8, proll=-1.0, croll=1.0)
NAME = 'xbox_ethics_v2'


def holds(arms):
    """arm parameters of both hands holding the pad at the watch posture (chest relative, so they hold at any posture)"""
    P = xa.calm(**P_WATCH)
    ql, rl, ml = xc.fit_grip(arms, P, 'L', wrist_off=WRIST_OFF)
    qr, rr, mr = xc.fit_grip(arms, P, 'R', wrist_off=WRIST_OFF)
    return ql, qr, dict(rms=(rl, rr), miss=(ml, mr))


def keys(arms, ql, qr):
    B = sc.BUTTON
    pole = np.array([-0.35, -0.55, -0.75])         # elbow out to the right and down (as before)

    def calm(**kw):
        P = xa.calm(**kw)
        P.update(ql)                               # the left hand has the pad all the time
        P['r_fm0'] = 1.0                           # same key set as the poses that carry the right hand's grip (so every pose interpolates the same keys)
        return P

    K = []
    K.append((0.00, calm()))
    P1 = calm(cpitch=14.0, hpitch=9.0, px=1.5, ppitch=3.0)
    P1, m1, e1 = xa.reach_tip(arms, P1, 'R', B + np.array([-6.0, 3.0, 9.0]), pole, wflex=10.0, proll=-45.0, claw=0.3)
    K.append((0.45, P1))
    body = dict(cpitch=33.0, ppitch=9.0, pz=-5.0, px=6.0, hpitch=22.0, cyaw=-6.0, croll=-3.0)
    P2 = calm(**body)
    P2, m2, e2 = xa.reach_tip(arms, P2, 'R', B - xa.HAND_DIR * 3.4, pole, wflex=8.0, proll=-50.0, claw=0.2)
    K.append((0.95, P2))
    P3 = dict(P2)
    P3, m3, e3 = xa.reach_tip(arms, P3, 'R', B + np.array([0.3, 0.0, 0.0]), pole, wflex=8.0, proll=-50.0, claw=0.2)
    K.append((1.20, P3))
    K.append((1.40, dict(P3)))
    P5 = dict(P2)
    P5, m5, e5 = xa.reach_tip(arms, P5, 'R', B - xa.HAND_DIR * 4.0, pole, wflex=8.0, proll=-50.0, claw=0.2)
    K.append((1.65, P5))
    # stand back up, the right hand goes back to the pad
    P6 = calm(cpitch=8.0, hpitch=18.0, px=0.5, ppitch=2.0, hyaw=-3.0)
    P6.update(qr)
    K.append((2.35, P6))
    P7 = calm(**P_WATCH)
    P7.update(qr)
    K.append((3.20, P7))
    K.append((3.60, dict(P7)))
    return K, (m1, m2, m3, m5, e1, e2, e3, e5)


def build(rigkey='ethics', fps=xa.FPS):
    rig = tc.rig_for(rigkey)
    arms = ik.Arms(rig, xa.STYLE)
    ql, qr, info = holds(arms)
    K, misses = keys(arms, ql, qr)
    T = K[-1][0]
    n = int(round(T * fps))
    times = [i / fps for i in range(n + 1)]
    frames = tc.build_frames(rig, lambda t: xa.pose_at(K, t), times, xa.STYLE)
    js = tc.to_json(rig, frames, fps, name=NAME, restart=n + 1)
    return rig, arms, K, js, misses, info


if __name__ == '__main__':
    rig, arms, K, js, misses, info = build()
    print('grips: fit rms L %.2f R %.2f, unreachable L %.2f R %.2f' % (info['rms'][0], info['rms'][1], info['miss'][0], info['miss'][1]))
    print('IK keys: unreachable units %s | fingertip error to target %s' % ([round(m, 2) for m in misses[:4]], [round(e, 2) for e in misses[4:]]))
    print('frames', len(js['FrameData']), 'bones', len(js['FrameData'][0]['BoneInfo']), 'json bytes', len(json.dumps(js, separators=(',', ':'))))
