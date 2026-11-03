"""thr_dance2: v2 choreography, a 32-beat loop at 120 BPM built from the signature moves of the zombie dance
(zombie march with shoulder pops, monster pose and sway, werewolf swipes, hip thrusts with claws, side steps, spiral down and shimmy up).

Same parameter vocabulary as thr_core.neutral(); every beat is a key pose on a timeline with easing, plus three layers on top that make it read as a groove:
  * a knee/chest nod on every beat
  * lag: the head and the distal arm joints trail the key poses (follow-through)
  * snap easing (ease-out, optional back overshoot) so hits land on the beat
Nothing here copies a recording; it is an original approximation written from move descriptions.
"""
import bisect
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thr_core as tc
from thr_dance import mirror, arm, BPM, BEAT, LOOP_BEATS, style_for      # noqa: F401  (re-exported)


# ---------------------------------------------------------------------------------------------------------------- arm shapes (outward-positive azimuth)
def chest_claw(s, **o):
    return arm(s, o.get('elev', 30), o.get('az', 30), o.get('flex', 100), o.get('froll', 0), o.get('wflex', 15), o.get('proll', -75), o.get('claw', 1.0))


def march_arm(s, **o):                  # stiff, low diagonal in front, hands drooping (the zombie reach)
    return arm(s, o.get('elev', 55), o.get('az', 14), o.get('flex', 16), o.get('froll', 0), o.get('wflex', 30), o.get('proll', -35), o.get('claw', 0.9))


def monster_arm(s, **o):                # elbow out at shoulder height, forearm up, claw
    return arm(s, o.get('elev', 82), o.get('az', 62), o.get('flex', 130), o.get('froll', 66), o.get('wflex', 28), o.get('proll', -50), o.get('claw', 1.0))


def hip_arm(s, **o):                    # hand on the hip
    return arm(s, o.get('elev', 26), o.get('az', 85), o.get('flex', 118), o.get('froll', -60), o.get('wflex', -10), o.get('proll', -20), o.get('claw', 0.35))


def face_claw(s, **o):                  # claw beside the face
    return arm(s, o.get('elev', 70), o.get('az', 28), o.get('flex', 136), o.get('froll', 10), o.get('wflex', 30), o.get('proll', -70), o.get('claw', 1.0))


def out_claw(s, **o):                   # arm out to the side, claw spread
    return arm(s, o.get('elev', 84), o.get('az', 95), o.get('flex', 20), o.get('froll', 60), o.get('wflex', 25), o.get('proll', -55), o.get('claw', 1.0))


def limp(s, **o):                       # arm raised forward, hand dangling (zombie hands)
    return arm(s, o.get('elev', 74), o.get('az', 10), o.get('flex', 14), o.get('froll', 0), o.get('wflex', 58), o.get('proll', -30), o.get('claw', 0.6))


def hang(s, **o):
    return arm(s, o.get('elev', 14), o.get('az', 60), o.get('flex', 14), 0, 0, o.get('proll', -20), o.get('claw', 0.6))


def base():
    d = tc.neutral()
    d.update(pz=-2.0, cpitch=14.0, hpitch=6.0, l_fy=2.0, r_fy=2.0)
    d.update(chest_claw('L'))
    d.update(chest_claw('R'))
    return d


def P(**kw):
    d = base()
    d.update(kw)
    return d


# ---------------------------------------------------------------------------------------------------------------- reusable body poses
def march(**kw):
    """left knee up, weight on the right leg, left shoulder popped to the ear, head dropped to it; right arm forward, left arm back"""
    d = P(px=1.0, py=-3.2, pz=-1.0, proll=3.0, croll=-5.0, cpitch=17.0, shl=8.0, hroll=-15.0, hpitch=9.0,
          l_fz=6.5, l_fx=5.5, l_fy=0.5, l_fpitch=22.0, r_fy=3.0)
    d.update(march_arm('R', elev=66, az=10))
    d.update(march_arm('L', elev=38, az=16))
    d.update(kw)
    return d


def monster(**kw):
    d = P(px=2.5, pz=-4.5, ppitch=-5.0, cpitch=-1.0, hpitch=-3.0, l_fy=5.0, r_fy=5.0)
    d.update(monster_arm('L'))
    d.update(monster_arm('R'))
    d.update(kw)
    return d


def thrust(**kw):
    d = P(px=5.5, pz=-3.0, ppitch=-13.0, cpitch=3.0, hpitch=-5.0, l_fy=4.0, r_fy=4.0)
    d.update(kw)
    return d


def recoil(**kw):
    d = P(px=-1.5, pz=-5.5, ppitch=7.0, cpitch=22.0, hpitch=10.0, l_fy=4.0, r_fy=4.0)
    d.update(kw)
    return d


def K(beat, pose, hit=0.5, ease='o'):
    return (beat, pose, hit, ease)


def keys():
    k = []
    # ------------------------------------------------------------------ phrase 1: zombie march (beats 0-7)
    m = march()
    for i in range(8):
        d = m if i % 2 == 0 else mirror(m)
        extra = {}
        if i == 3:
            extra = dict(hyaw=34.0)
        if i == 5:
            extra = dict(hyaw=-30.0)
        if i == 6:
            extra = dict(hpitch=18.0)
        if i == 7:
            extra = dict(cpitch=24.0, pz=-4.0)
        k.append(K(i, dict(d, **extra), 0.45, 'o'))
    # ------------------------------------------------------------------ phrase 2a: monster pose + sway (beats 8-11)
    mr = monster(py=-4.5, proll=-5.0, croll=9.0, hroll=-14.0, r_fy=4.0, l_fy=6.0)
    mr.update(monster_arm('R', elev=70, az=66, froll=36))                  # roll / wrist values fitted against the Euler poles of all rigs (see winscan.py)
    mr.update(monster_arm('L', elev=66, az=58, wflex=48))
    k.append(K(8, mr, 0.55, 'b'))
    k.append(K(9, dict(mr, pz=-7.0, cpitch=6.0, shl=7.0, shr=7.0, hpitch=2.0), 0.4, 'o'))
    ml = mirror(mr)
    ml.update(l_froll=66.0, l_wflex=48.0, r_froll=36.0, r_wflex=28.0)
    k.append(K(10, ml, 0.55, 'b'))
    k.append(K(11, dict(ml, pz=-7.0, cpitch=6.0, shl=7.0, shr=7.0, hpitch=2.0), 0.4, 'o'))
    # ------------------------------------------------------------------ phrase 2b: werewolf swipes (beats 12-15)
    wind = P(py=-6.0, pz=-8.0, cpitch=14.0, cyaw=-24.0, hyaw=-18.0, hpitch=6.0, proll=-4.0, croll=6.0, r_fy=9.0, l_fy=1.0)
    wind.update(arm('R', 72, 66, 100, 30, 24, -55, 1.0))                 # claw cocked high at the right side of the head
    wind.update(arm('L', 62, 55, 48, 40, -20, -50, 1.0))                  # left arm out for balance
    swipe = dict(wind, cyaw=30.0, hyaw=22.0, cpitch=20.0, pz=-7.0, py=-4.0, croll=-3.0)
    swipe.update(arm('R', 64, -8, 70, 10, 30, -40, 1.0))                # claw slashes across the face
    swipe.update(arm('L', 36, 40, 90, -10, 15, -70, 1.0))
    k.append(K(12, wind, 0.5, 'o'))
    k.append(K(13, swipe, 0.32, 'b'))
    wind_l = mirror(wind)
    wind_l.update(l_flex=124.0, l_wflex=44.0)                  # left arm values fitted against the zombie's asymmetric Euler poles
    swipe_l = mirror(swipe)
    swipe_l.update(l_flex=78.0, l_froll=-30.0, l_aelev=76.0)
    k.append(K(14, wind_l, 0.5, 'o'))
    k.append(K(15, swipe_l, 0.32, 'b'))
    # ------------------------------------------------------------------ phrase 3: hip thrusts with claws (beats 16-23)
    h1, h2 = thrust(hyaw=26.0), thrust(hyaw=-26.0)
    for d in (h1, h2):
        d.update(hip_arm('L'))
        d.update(hip_arm('R'))
    r1 = recoil()
    r1.update(hip_arm('L'))
    r1.update(hip_arm('R'))
    k.append(K(16, h1, 0.3, 'b'))
    k.append(K(17, dict(r1, hyaw=8.0), 0.5, 'o'))
    k.append(K(18, h2, 0.3, 'b'))
    k.append(K(19, dict(r1, hyaw=-8.0), 0.5, 'o'))
    t1 = thrust(hyaw=0.0, hpitch=-12.0)
    t1.update(out_claw('L', froll=-30, proll=-55))
    t1.update(out_claw('R', froll=30, proll=-55))
    t2 = recoil()
    t2.update(face_claw('L', proll=55))
    t2.update(face_claw('R', proll=55))
    k.append(K(20, t1, 0.3, 'b'))
    k.append(K(21, t2, 0.5, 'o'))
    k.append(K(22, dict(t1, hroll=10.0), 0.3, 'b'))
    k.append(K(23, dict(t2, hroll=-10.0), 0.5, 'o'))
    # ------------------------------------------------------------------ phrase 4: side steps with zombie hands, spiral down, shimmy up (beats 24-31)
    sd = P(pyaw=-26.0, cyaw=-10.0, py=-5.0, pz=-4.0, cpitch=16.0, hpitch=8.0, hroll=12.0, r_fy=8.0, l_fy=1.0)
    sd.update(limp('L'))
    sd.update(limp('R'))
    k.append(K(24, sd, 0.5, 'o'))
    sd2 = dict(sd, py=-2.0, r_fy=2.0, l_fy=2.0, pz=-5.0, hroll=-12.0)
    k.append(K(25, sd2, 0.5, 'o'))
    k.append(K(26, dict(sd, py=-5.0, hroll=12.0), 0.5, 'o'))
    k.append(K(27, dict(sd2, hroll=-12.0, pz=-3.5), 0.5, 'o'))
    s1 = P(pz=-7.0, cyaw=42.0, cpitch=26.0, hpitch=12.0, hyaw=-18.0, pyaw=14.0, l_fy=5.0, r_fy=5.0)
    s1.update(arm('R', 40, 8, 40, 0, 25, -40, 0.8))
    s1.update(arm('L', 70, 56, 56, 50, 30, -60, 1.0))
    s2 = P(pz=-12.0, cyaw=-52.0, cpitch=34.0, hpitch=18.0, hyaw=20.0, pyaw=-16.0, l_fy=6.0, r_fy=6.0)
    s2.update(arm('L', 40, 8, 40, 0, 25, -40, 0.8))
    s2.update(arm('R', 72, 36, 70, 20, 30, -60, 1.0))
    k.append(K(28, s1, 0.6, 's'))
    k.append(K(29, s2, 0.6, 's'))
    up1 = P(pz=-6.0, cpitch=14.0, hpitch=4.0, shl=10.0, shr=-4.0)
    up1.update(face_claw('L', flex=144, froll=-10))
    up1.update(face_claw('R'))
    up2 = dict(up1, shl=-4.0, shr=10.0, pz=-3.0)
    k.append(K(30, up1, 0.5, 'o'))
    k.append(K(30.5, up2, 0.5, 'o'))
    k.append(K(31, dict(up1, pz=-2.5), 0.5, 'o'))
    k.append(K(31.5, dict(up2, shl=-2.0, shr=6.0, pz=-2.0), 0.5, 'o'))
    return k


# ---------------------------------------------------------------------------------------------------------------- timeline: key poses -> spring followers
# Every key is a target pose requested LEAD beats before its beat; each parameter then follows its targets like a (mostly critically damped) spring with its own stiffness,
# so snaps are fast but never teleport (bounded speed at 30 fps), heavy parts (pelvis, legs) trail light ones (head, wrists), and the periodic steady state closes the loop exactly.
LEAD = 0.22
DYN = {'px': (15, 1.0), 'py': (15, 1.0), 'pz': (16, 1.0), 'pyaw': (15, 1.0), 'ppitch': (16, 1.0), 'proll': (15, 1.0),
       'cyaw': (19, 0.9), 'cpitch': (19, 0.9), 'croll': (19, 0.9),
       'hyaw': (27, 0.65), 'hpitch': (27, 0.65), 'hroll': (27, 0.65),
       'shl': (30, 0.6), 'shr': (30, 0.6)}
ARM_DYN = {'aelev': (21, 0.85), 'aazim': (21, 0.85), 'flex': (23, 0.8), 'froll': (23, 0.8), 'wflex': (28, 0.7), 'proll': (26, 0.8), 'claw': (22, 1.0)}
LEG_DYN = {'fx': (26, 0.9), 'fy': (26, 0.9), 'fz': (26, 0.9), 'fyaw': (24, 0.9), 'fpitch': (24, 0.9), 'kn': (20, 1.0)}
ARM_SCALE = 0.75                           # arm springs a little softer than the body's (bounded joint speed at 30 fps)
LEAD_ARM = 0.28                            # ... and requested a little earlier so the arms still land on the beat
NOD = 1.3                                  # knee dip on every beat (units)
NOD_CHEST = 2.4                            # chest nod on every beat (degrees)


def dyn_of(key):
    if key[:2] in ('l_', 'r_'):
        name = key[2:]
        return ARM_DYN[name] if name in ARM_DYN else LEG_DYN[name]
    return DYN[key]


class Timeline:
    def __init__(self, key_list=None, lead=LEAD, hz=240, nod=True, scale=1.0, arm_scale=ARM_SCALE, lead_arm=LEAD_ARM):
        ks = sorted(key_list or keys(), key=lambda e: e[0])
        self.k = ks
        self.params = list(ks[0][1].keys())
        self.nod = nod
        self.hz = hz
        n = int(round(LOOP_BEATS * BEAT * hz))
        self.n = n
        beats = [e[0] for e in ks]
        tg = np.array([[e[1][p] for p in self.params] for e in ks], dtype=float)
        is_arm = np.array([p[:2] in ('l_', 'r_') and p[2:] in ARM_DYN for p in self.params])
        leads = np.where(is_arm, lead if lead_arm is None else lead_arm, lead)
        idx = np.zeros((n, len(self.params)), dtype=int)
        for lv in set(leads.tolist()):
            cols = np.where(leads == lv)[0]
            for s in range(n):
                b = (s / hz / BEAT + lv) % LOOP_BEATS
                j = bisect.bisect_right(beats, b) - 1
                idx[s, cols] = j if j >= 0 else len(ks) - 1
        cols_all = np.arange(len(self.params))
        w = np.array([dyn_of(p)[0] for p in self.params], dtype=float) * scale * np.where(is_arm, arm_scale, 1.0)
        z = np.array([dyn_of(p)[1] for p in self.params], dtype=float)
        dt = 1.0 / hz
        x = tg[idx[0], cols_all].copy()
        v = np.zeros_like(x)
        tab = np.zeros((n + 1, len(self.params)))
        for loop in range(3):
            if loop == 2:
                tab[0] = x
            for s in range(n):
                a = w * w * (tg[idx[s], cols_all] - x) - 2.0 * z * w * v
                v += a * dt
                x += v * dt
                if loop == 2:
                    tab[s + 1] = x
        self.tab = tab
        self.loop_err = float(np.abs(tab[n] - tab[0]).max())

    def pose(self, beat):
        t = (beat % LOOP_BEATS) * BEAT * self.hz
        i = int(t)
        f = t - i
        row = self.tab[i] * (1.0 - f) + self.tab[min(i + 1, self.n)] * f
        p = dict(zip(self.params, row.tolist()))
        if self.nod:
            d = 0.5 + 0.5 * math.cos(2.0 * math.pi * beat)
            p['pz'] -= NOD * d
            p['cpitch'] += NOD_CHEST * d
        return p
