"""thr_dance: the choreography (a 32-beat loop at 120 BPM, stylised zombie dance) as key poses on a beat timeline.

Pose parameters are described in thr_core.neutral(); sides l_ / r_ use outward-positive conventions so that mirror() only has to swap the sides and flip the left-right numbers.
Nothing here copies a recording: it is an approximation of the dance's signature moves (claw hands, head tilts, side steps with hip sway, stomps, head snaps, the arm-up pose)
written from scratch.  The loop is built from four 8-count phrases; tweak the key lists to change the moves.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thr_core as tc

BPM = float(os.environ.get('THRILLER_BPM', '120'))      # tempo of the music the dance is built for (make_thriller.py --bpm sets it before the import)
BEAT = 60.0 / BPM
LOOP_BEATS = 32

NEG = ('py', 'pyaw', 'proll', 'cyaw', 'croll', 'hyaw', 'hroll')
FLIP = ('fyaw',)


def mirror(d):
    """swap left and right"""
    o = dict(d)
    for k, v in d.items():
        if k in NEG:
            o[k] = -v
    o['shl'], o['shr'] = d.get('shr', 0.0), d.get('shl', 0.0)
    for k in tc.ARM_KEYS + tc.LEG_KEYS:
        a, b = 'l_' + k, 'r_' + k
        if a in d or b in d:
            va, vb = d.get(a), d.get(b)
            if vb is not None:
                o[a] = -vb if k in FLIP else vb
            if va is not None:
                o[b] = -va if k in FLIP else va
    return o


def arm(side, elev, az, flex, froll=0.0, wflex=0.0, proll=0.0, claw=0.0):
    pre = 'l_' if side == 'L' else 'r_'
    return {pre + 'aelev': elev, pre + 'aazim': az, pre + 'flex': flex, pre + 'froll': froll, pre + 'wflex': wflex, pre + 'proll': proll, pre + 'claw': claw}


# --- arm shapes (outward-positive azimuth, see Solver.arm_vectors)
def claw_chest(side, **o):
    return arm(side, o.get('elev', 30), o.get('az', 30), o.get('flex', 100), o.get('froll', 0), o.get('wflex', 15), o.get('proll', -75), 1.0)


def claw_up(side, **o):
    return arm(side, o.get('elev', 105), o.get('az', 35), o.get('flex', 110), o.get('froll', 0), o.get('wflex', 30), o.get('proll', -60), 1.0)


def claw_low(side, **o):
    return arm(side, o.get('elev', 22), o.get('az', 30), o.get('flex', 65), o.get('froll', 0), o.get('wflex', 20), o.get('proll', -70), 1.0)


def arm_up(side, **o):
    return arm(side, o.get('elev', 160), o.get('az', 25), o.get('flex', 12), o.get('froll', 0), o.get('wflex', 20), o.get('proll', -40), 1.0)


def arm_hang(side, **o):
    return arm(side, o.get('elev', 14), o.get('az', 60), o.get('flex', 14), 0, 0, o.get('proll', -20), 0.6)


def reach(side, **o):
    return arm(side, o.get('elev', 108), o.get('az', 8), o.get('flex', 22), 0, 10, o.get('proll', -50), 1.0)


def base_pose():
    d = tc.neutral()
    d.update(pz=-2.0, cpitch=14.0, hpitch=6.0)
    d.update(claw_chest('L'))
    d.update(claw_chest('R'))
    d.update({'l_fy': 2.0, 'r_fy': 2.0})
    return d


def P(**kw):
    d = base_pose()
    d.update(kw)
    return d


def weight_right(**kw):
    """weight on the right leg, left foot out on its toe, chest counter-rolled"""
    d = P(py=-3.6, pz=-3.0, proll=-5.0, croll=6.0, l_fy=5.0, l_fpitch=16.0, l_fz=0.4)
    d.update(kw)
    return d


def keys():
    """list of (beat, pose, hit): `hit` = share of the segment used by the move (the rest is hold)"""
    k = []
    # ---------------------------------------------------------------- phrase 1: claw sway (beats 0-7)
    wr = weight_right(hroll=-14.0)
    wr.update(claw_up('R'))
    wr.update(claw_low('L'))
    k.append((0, wr, 0.5))
    k.append((1, dict(wr, pz=-4.2, cpitch=20.0), 0.4))
    wl = mirror(wr)
    k.append((2, wl, 0.5))
    k.append((3, dict(wl, pz=-4.2, cpitch=20.0), 0.4))
    wr2 = weight_right(hroll=-18.0, cyaw=14.0, hyaw=-18.0)
    wr2.update(claw_chest('R', az=45, elev=40))
    wr2.update(claw_chest('L', az=20))
    k.append((4, wr2, 0.5))
    k.append((5, dict(wr2, pz=-4.5, cpitch=22.0, shl=8.0, shr=8.0), 0.4))
    wl2 = mirror(wr2)
    k.append((6, wl2, 0.5))
    k.append((7, dict(wl2, pz=-4.5, cpitch=22.0, shl=8.0, shr=8.0), 0.4))
    # ---------------------------------------------------------------- phrase 2: step and reach (beats 8-15)
    st = P(px=3.0, pz=-5.5, cpitch=26.0, hpitch=2.0, r_fx=7.5, r_fy=4.0, l_fx=-2.0, l_fy=3.0, l_fz=0.5, l_fpitch=14.0)
    st.update(reach('R'))
    st.update(arm('L', 25, -25, 70, 0, 20, -70, 1.0))
    k.append((8, st, 0.45))
    k.append((9, dict(st, pz=-6.5, cpitch=30.0), 0.4))
    ctr = P(pz=-3.0, cpitch=20.0, hroll=10.0)
    k.append((10, ctr, 0.5))
    k.append((11, dict(ctr, pz=-4.5, cpitch=24.0, hroll=-10.0), 0.4))
    st2 = mirror(st)
    k.append((12, st2, 0.45))
    k.append((13, dict(st2, pz=-6.5, cpitch=30.0), 0.4))
    k.append((14, dict(ctr, hroll=-10.0), 0.5))
    k.append((15, dict(ctr, pz=-4.5, cpitch=24.0, hroll=10.0, shl=10.0, shr=10.0), 0.4))
    # ---------------------------------------------------------------- phrase 3: hip thrust, head snaps, twist (beats 16-23)
    th = P(px=4.0, pz=-3.5, ppitch=-7.0, cpitch=8.0, hpitch=-4.0, hyaw=42.0)
    th.update(arm('L', 12, -35, 95, 0, 10, -70, 1.0))
    th.update(arm('R', 12, -35, 95, 0, 10, -70, 1.0))
    k.append((16, th, 0.4))
    bk = P(px=-2.0, pz=-5.0, cpitch=26.0, hpitch=10.0, hyaw=0.0)
    k.append((17, bk, 0.4))
    th2 = dict(th, hyaw=-42.0)
    k.append((18, th2, 0.4))
    k.append((19, bk, 0.4))
    tw = P(pz=-4.0, cyaw=34.0, cpitch=18.0, hyaw=-26.0, pyaw=-10.0)
    tw.update(arm('R', 40, -42, 92, 0, 10, -70, 1.0))
    tw.update(arm('L', 55, 70, 40, 0, 10, -70, 1.0))
    k.append((20, tw, 0.5))
    k.append((21, dict(tw, pz=-5.2), 0.4))
    k.append((22, mirror(tw), 0.5))
    k.append((23, dict(mirror(tw), pz=-5.2), 0.4))
    # ---------------------------------------------------------------- phrase 4: arm-up pose and collapse (beats 24-31)
    up = weight_right(cpitch=4.0, hpitch=-16.0, hroll=-12.0, pz=-4.0)
    up.update(arm_up('R'))
    up.update(arm('L', 40, -20, 85, 0, 20, -70, 1.0))
    k.append((24, up, 0.45))
    k.append((25, dict(up, pz=-5.2), 0.4))
    k.append((26, mirror(up), 0.45))
    k.append((27, dict(mirror(up), pz=-5.2), 0.4))
    both = P(pz=-3.5, cpitch=-4.0, hpitch=-18.0)
    both.update(arm_up('R', az=40, elev=150))
    both.update(arm_up('L', az=40, elev=150))
    k.append((28, both, 0.5))
    k.append((29, dict(both, pz=-5.0), 0.4))
    cl = P(pz=-6.0, cpitch=38.0, hpitch=18.0, hroll=8.0)
    cl.update(arm_hang('R'))
    cl.update(arm_hang('L'))
    k.append((30, cl, 0.5))
    k.append((31, dict(cl, pz=-7.0, cpitch=42.0), 0.4))
    return k


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Timeline:
    def __init__(self, key_list=None):
        self.k = key_list or keys()
        self.k.sort(key=lambda e: e[0])
        self.params = list(self.k[0][1].keys())

    def pose(self, beat):
        b = beat % LOOP_BEATS
        ks = self.k
        i = 0
        while i + 1 < len(ks) and ks[i + 1][0] <= b:
            i += 1
        a = ks[i]
        nxt = ks[(i + 1) % len(ks)]
        t1 = nxt[0] if nxt[0] > a[0] else nxt[0] + LOOP_BEATS
        u = (b - a[0]) / (t1 - a[0])
        hit = nxt[2]
        v = smoothstep((u - (1.0 - hit)) / hit)
        pa, pb = a[1], nxt[1]
        return {key: pa[key] + (pb[key] - pa[key]) * v for key in self.params}


def style_for(kind):
    """per-character modifiers of the solver (see thr_core.Solver.solve)"""
    if kind == 'zombie':
        return {'lean': 10.0, 'head_pitch': 4.0, 'drop': 1.5, 'foot_x': -2.5}
    return {'foot_x': -1.0}
