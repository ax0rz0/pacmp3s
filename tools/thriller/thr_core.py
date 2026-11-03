"""thr_core: a procedural dance (pose parameters per beat) -> ValveBiped-style rigs (player families and the HL2 zombies) -> pac3 custom_animation JSON.

The solver works like tools/emote/retarget.py: every bone gets a desired WORLD rotation and is posed top-down, so each ManipulateBoneAngles value (post-multiplied in the bone's own
base frame:  Wa(b) = Wa(parent) * Lbase(b) * M(b)) is relative to the already posed parent.  Differences:
  * the source is not a mocap clip but a pose (a dict of named numbers, see NEUTRAL) sampled from a keyframe timeline (thr_dance.py)
  * torso / head / clavicle / foot bones get world DELTAS from their base pose (so a hunched zombie base stays hunched), arms are aimed along absolute directions
  * the legs use two-bone IK on the target's own bone lengths, so planted feet stay planted on every rig
  * finger curls are rotations about the bend axis derived from the target's own hand geometry
Frames are the game frame: +X forward, +Y left, +Z up (for the HL2 zombies the model frame, which faces +X as well).
Angles: yaw/pitch/roll in Source order (R = Rz(yaw) Ry(pitch) Rx(roll)): pitch > 0 = nose down, roll > 0 = left side up.
"""
import json
import math
import os
import re
import sys

import numpy as np

EMOTE = r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\emote'
OUTFIT = r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\outfit'
for _p in (EMOTE, OUTFIT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import mdl_anim as ma                                   # noqa: E402
import vpk_tools as vt                                  # noqa: E402
from retarget import norm, arc, axis_rot, source_angles, angles_matrix, continuous, palm_normal   # noqa: E402

I3 = np.eye(3)
rad = math.radians


def R_ypr(yaw=0.0, pitch=0.0, roll=0.0):
    return angles_matrix((pitch, yaw, roll))


# ------------------------------------------------------------------------------------------------------------------------------ rigs
MODELS = {
    'ethics': ('scp', 'models/jericho/citizens/female_04.mdl'),
    'classd': ('scp', 'models/player/kerry/class_d_7.mdl'),
    'isd': ('scp', 'models/frostbyte/ia/internalsecurity_erdim.mdl'),
    'medic': ('scp', 'models/frostbyte/cn_s65_combatmedic.mdl'),
    'zombie': ('hl2', 'models/zombie/classic.mdl'),
    'fast': ('hl2', 'models/zombie/fast.mdl'),
}
_vpk = {}
_gma = {}


def _hl2(path):
    if 't' not in _vpk:
        _vpk['t'], _vpk['base'] = vt.entries(ma.HL2_VPK)
    t = _vpk['t']
    return vt.read(ma.HL2_VPK, t, _vpk['base'], path), (vt.read(ma.HL2_VPK, t, _vpk['base'], path[:-4] + '.ani') if (path[:-4] + '.ani') in t else None)


class Rig:
    """a ValveBiped-style skeleton in its base pose (sequence 0, frame 0 = what the entity shows before pac manipulates a bone)"""

    def __init__(self, key):
        self.key = key
        src, path = MODELS[key]
        if src == 'hl2':
            b, ani = _hl2(path)
        else:
            if 'g' not in _gma:
                _gma['g'] = ma.Gma(ma.SCP_GMA)
            b, ani = _gma['g'].get(path), None
        m = ma.Mdl(b)
        self.m = m
        label, a0 = m.seq_info(0)
        self.seq0 = label
        loc, _, _, _ = m.anim_frame(a0, 0, ani)
        self.n = m.n
        self.names = m.names
        self.parent = m.parent
        self.idx = m.index
        self.Lr = [l[0] for l in loc]
        self.Lp = [l[1] for l in loc]
        W = m.fk(loc)
        self.Wr = [w[0] for w in W]
        self.Wp = [w[1] for w in W]
        self.pel = self.b('Pelvis')
        self.spine = [self.b(s) for s in ('Spine', 'Spine1', 'Spine2', 'Spine4') if self.b(s) is not None]
        self.head_chain = [self.b(s) for s in ('Neck1', 'Head1') if self.b(s) is not None]
        self.zombie_head = False
        if not self.head_chain and self.b('HC_Body_Bone') is not None:      # the classic zombie has no neck / head bones: the headcrab rides the top spine bone
            self.head_chain = [self.b('HC_Body_Bone')]
            self.zombie_head = True
        self.legs = {}
        for s in ('L', 'R'):
            th, ca, ft, toe = [self.b('%s_%s' % (s, x)) for x in ('Thigh', 'Calf', 'Foot', 'Toe0')]
            if None in (th, ca, ft):
                continue
            L1 = float(np.linalg.norm(self.Wp[ca] - self.Wp[th]))
            L2 = float(np.linalg.norm(self.Wp[ft] - self.Wp[ca]))
            self.legs[s] = dict(th=th, ca=ca, ft=ft, toe=toe, L1=L1, L2=L2, ankle_z=float(self.Wp[ft][2]))
        L = self.legs['L']
        self.hip_dz = float(self.Wp[L['th']][2] - self.Wp[self.pel][2])
        self.z_straight = L['ankle_z'] + L['L1'] + L['L2'] - self.hip_dz        # pelvis height with straight legs
        self.arms = {}
        for s in ('L', 'R'):
            names = ['%s_%s' % (s, x) for x in ('Clavicle', 'UpperArm', 'Forearm', 'Hand')]
            ids = [self.b(x) for x in names]
            if None in ids:
                continue
            self.arms[s] = dict(cl=ids[0], ua=ids[1], fa=ids[2], hd=ids[3], mid=self.b('%s_Finger2' % s))
        # fingers: chains whose root is a child of the hand
        self.fingers = {}
        for s in ('L', 'R'):
            if s not in self.arms:
                continue
            hd = self.arms[s]['hd']
            chains = {}
            for i in range(self.n):
                if self.parent[i] == hd and re.match(r'ValveBiped\.Bip01_%s_Finger\d$' % s, self.names[i]):
                    fid = int(self.names[i][-1])
                    chain = [i]
                    while True:
                        kids = [j for j in range(self.n) if self.parent[j] == chain[-1] and re.match(r'ValveBiped\.Bip01_%s_Finger\d+$' % s, self.names[j])]
                        if not kids:
                            break
                        chain.append(kids[0])
                    chains[fid] = chain
            self.fingers[s] = chains
        # palm normals of the base pose (same geometry formula as the retargeter, anatomical side on every rig)
        self.palm0 = {}
        for s, sign in (('R', 1.0), ('L', -1.0)):
            if s not in self.arms:
                continue
            hand = self.arms[s]['hd']
            mid = self.b('%s_Finger2' % s)
            for a, bb in (('Finger1', 'Finger4'), ('Finger0', 'Finger1')):
                ia, ib = self.b('%s_%s' % (s, a)), self.b('%s_%s' % (s, bb))
                if mid is not None and ia is not None and ib is not None:
                    self.palm0[s] = palm_normal(self.Wp[hand], self.Wp[mid], self.Wp[ia], self.Wp[ib], sign)
                    break

    def b(self, short):
        for pre in ('ValveBiped.Bip01_', 'ValveBiped.'):
            i = self.idx.get(pre + short)
            if i is not None:
                return i
        return None

    def short(self, i):
        return self.names[i].replace('ValveBiped.Bip01_', '').replace('ValveBiped.', '')


_rigs = {}


def rig_for(key):
    if key not in _rigs:
        _rigs[key] = Rig(key)
    return _rigs[key]


# ------------------------------------------------------------------------------------------------------------------------------ pose parameters
ARM_KEYS = ('aelev', 'aazim', 'flex', 'froll', 'wflex', 'proll', 'claw')
LEG_KEYS = ('fx', 'fy', 'fz', 'fyaw', 'fpitch', 'kn')
GLOBAL_KEYS = ('px', 'py', 'pz', 'pyaw', 'ppitch', 'proll', 'cyaw', 'cpitch', 'croll', 'hyaw', 'hpitch', 'hroll', 'shl', 'shr')


def neutral():
    """stand with arms hanging, a little knee bend, feet 'stance' apart"""
    d = {k: 0.0 for k in GLOBAL_KEYS}
    for s in ('l', 'r'):
        d.update({s + '_aelev': 8.0, s + '_aazim': 80.0, s + '_flex': 12.0, s + '_froll': 0.0, s + '_wflex': 0.0, s + '_proll': 0.0, s + '_claw': 0.15})
        d.update({s + '_fx': 0.0, s + '_fy': 0.0, s + '_fz': 0.0, s + '_fyaw': 0.0, s + '_fpitch': 0.0, s + '_kn': 0.0})
    return d


STANCE_Y = 7.5          # nominal half distance between the ankles
DROP0 = 3.0             # nominal knee bend: the pelvis sits this far below the straight-leg height
SPINE_W = {1: [1.0], 2: [0.45, 1.0], 3: [0.25, 0.6, 1.0], 4: [0.15, 0.35, 0.65, 1.0]}
HEAD_W = {1: [1.0], 2: [0.4, 1.0]}


def leg_ik(H, A, L1, L2, pole):
    """knee position of a two-bone leg from hip H to ankle A (clamped to reach), knee pushed towards `pole`"""
    v = A - H
    d = float(np.linalg.norm(v))
    d = min(max(d, abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3)
    u = norm(v)
    c = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
    ang = math.acos(max(-1.0, min(1.0, c)))
    pp = pole - u * float(np.dot(pole, u))
    if np.linalg.norm(pp) < 1e-6:
        pp = np.array([1.0, 0, 0]) - u * u[0]
    return H + (u * math.cos(ang) + norm(pp) * math.sin(ang)) * L1


def pole_angle(d, pole):
    """angle (degrees) between d and the nearer of +-pole"""
    c = abs(float(np.dot(d, pole)))
    return math.degrees(math.acos(min(1.0, c)))


def guard_dir(d, pole, a0=48.0, a1=27.0):
    """Euler pole guard: a bone aimed within a0 degrees of +-pole (its parent's local Z axis, where the manipulation's pitch reaches 90 and yaw/roll become ill-defined)
    is pushed away along the great circle so that it stays at least a1 degrees from it (smooth: unchanged beyond a0)"""
    s = 1.0 if float(np.dot(d, pole)) >= 0.0 else -1.0
    pz = s * pole
    c = float(np.clip(np.dot(d, pz), -1.0, 1.0))
    ang = math.degrees(math.acos(c))
    if ang >= a0:
        return d
    x = ang / a0
    new = a1 + (a0 - a1) * (x * x * (3.0 - 2.0 * x))
    perp = d - c * pz
    if np.linalg.norm(perp) < 1e-6:
        perp = np.array([1.0, 0, 0]) - pz * pz[0]
        if np.linalg.norm(perp) < 1e-6:
            perp = np.array([0, 1.0, 0]) - pz * pz[1]
    perp = norm(perp)
    t = math.radians(new)
    return math.cos(t) * pz + math.sin(t) * perp


class Solver:
    """pose dict -> manipulations for one rig"""

    def __init__(self, rig, style=None):
        self.r = rig
        self.style = dict(style or {})

    # -- helpers
    def arm_vectors(self, P, s, Dc):
        """chest-relative arm description -> world directions (upper arm, forearm, hand, palm normal)"""
        pre = 'l_' if s == 'L' else 'r_'
        sg = 1.0 if s == 'L' else -1.0
        e, az = rad(P[pre + 'aelev']), rad(P[pre + 'aazim'])
        u = np.array([math.sin(e) * math.cos(az), sg * math.sin(e) * math.sin(az), -math.cos(e)])
        X, Z = np.array([1.0, 0, 0]), np.array([0, 0, 1.0])
        if self.style.get('bend_ref', 'swing') == 'swing':
            b0 = norm(arc(-Z, u) @ X)               # the forward axis swung along with the arm from hanging: smooth everywhere except straight up
        else:                                        # old reference (forward axis projected): flips when the arm points forward
            b0 = X - u * float(np.dot(X, u))
            if np.linalg.norm(b0) < 0.25:
                b0 = Z - u * float(np.dot(Z, u))
            b0 = norm(b0)
        fr = rad(P[pre + 'froll'])
        b = norm(math.cos(fr) * b0 + math.sin(fr) * (-sg) * np.cross(u, b0))
        fl = rad(P[pre + 'flex'])
        fa = norm(u * math.cos(fl) + b * math.sin(fl))
        bw = b * math.cos(fl) - u * math.sin(fl)        # d(fa)/d(flex): the bend plane's continuation (the old b - fa(b.fa) vanished and flipped sign at flex = 90)
        w = rad(P[pre + 'wflex'])
        h = norm(fa * math.cos(w) + bw * math.sin(w))
        inward = np.array([0, -sg, 0.0])
        nr = inward - h * float(np.dot(inward, h))
        if np.linalg.norm(nr) < 0.2:
            nr = Z - h * float(np.dot(Z, h))
        nr = norm(nr)
        n = axis_rot(h, -sg * rad(P[pre + 'proll'])) @ nr
        return Dc @ u, Dc @ fa, Dc @ h, Dc @ n

    def solve(self, P):
        r = self.r
        st = self.style
        n = r.n
        AR = [None] * n
        AP = [None] * n
        M = {}
        trans_local = np.zeros(3)
        # ---- pelvis / chest / head world deltas
        lean = st.get('lean', 0.0)                      # extra forward lean of the whole torso (zombie hunch), degrees
        guard = st.get('pole_guard', (48.0, 27.0))          # Euler pole guard for the arm bones (None = off)
        self.margin = {}
        self.swing = {}
        twist_of = {}
        for s_, a_ in r.arms.items():
            twist_of[a_['ua']] = st.get('tw_ua', {}).get(s_, 0.0)
            twist_of[a_['fa']] = st.get('tw_fa', {}).get(s_, 0.0)
        Dpel = R_ypr(P['pyaw'], P['ppitch'], P['proll'])
        Rchest = R_ypr(P['cyaw'], P['cpitch'] + lean, P['croll'])
        Dc = Dpel @ Rchest
        Rhead = R_ypr(P['hyaw'], P['hpitch'] + st.get('head_pitch', 0.0), P['hroll'])
        # nominal pelvis position and feet
        drop = DROP0 + st.get('drop', 0.0)
        pel_p = np.array([P['px'], P['py'], r.z_straight - drop + P['pz']])
        trans_world = pel_p - r.Wp[r.pel]
        spine_w = SPINE_W[min(len(r.spine), 4)] if r.spine else []
        head_w = HEAD_W[min(len(r.head_chain), 2)] if r.head_chain else []
        rows = {}
        rows[r.pel] = ('delta', Dpel)
        for k, b in enumerate(r.spine):
            rows[b] = ('delta', Dpel @ R_ypr(*(np.array([P['cyaw'], P['cpitch'] + lean, P['croll']]) * spine_w[k])[[0, 1, 2]]))
        for k, b in enumerate(r.head_chain):
            rows[b] = ('delta', Dc @ R_ypr(*(np.array([P['hyaw'], P['hpitch'] + st.get('head_pitch', 0.0), P['hroll']]) * head_w[k])[[0, 1, 2]]))
        arm_dirs = {s: self.arm_vectors(P, s, Dc) for s in r.arms}
        for s, a in r.arms.items():
            pre = 'l_' if s == 'L' else 'r_'
            sh = P['shl'] if s == 'L' else P['shr']
            rows[a['cl']] = ('delta', Dc @ R_ypr(0, 0, sh if s == 'L' else -sh))
            u, fa, h, nrm = arm_dirs[s]
            rows[a['ua']] = ('swing', a['fa'], u)
            rows[a['fa']] = ('swing', a['hd'], fa)
            rows[a['hd']] = ('palm', a['mid'], h, nrm, s)
        # legs: handled in the loop (IK needs the achieved hip)
        leg_by_bone = {}
        for s, lg in r.legs.items():
            leg_by_bone[lg['th']] = (s, 'th')
            leg_by_bone[lg['ca']] = (s, 'ca')
            pre = 'l_' if s == 'L' else 'r_'
            yaw_f = P[pre + 'fyaw']
            Df = R_ypr(yaw_f, P[pre + 'fpitch'], 0)
            rows[lg['ft']] = ('delta', Df)
            if lg['toe'] is not None:
                rows[lg['toe']] = ('delta', Df)
        ankle = {}
        for s, lg in r.legs.items():
            pre = 'l_' if s == 'L' else 'r_'
            sg = 1.0 if s == 'L' else -1.0
            xa = st.get('foot_x', -1.0)
            ankle[s] = np.array([xa + P[pre + 'fx'], sg * (STANCE_Y + P[pre + 'fy']), lg['ankle_z'] + P[pre + 'fz']])        # fy: + = wider (outward) on both feet
        knee_pt = {}
        for b in range(n):
            p = r.parent[b]
            PR = AR[p] if p >= 0 else I3
            PP = AP[p] if p >= 0 else np.zeros(3)
            Wd = None
            if b in leg_by_bone:
                s, which = leg_by_bone[b]
                lg = r.legs[s]
                pre = 'l_' if s == 'L' else 'r_'
                sg = 1.0 if s == 'L' else -1.0
                W0 = PR @ r.Lr[b]
                if which == 'th':
                    H = PP + PR @ r.Lp[b] + (trans_world if b == r.pel else 0)
                    pole = np.array([1.0, sg * (0.25 + 0.03 * P[pre + 'kn']), 0.0])
                    knee_pt[s] = leg_ik(H, ankle[s], lg['L1'], lg['L2'], pole)
                    d = norm(knee_pt[s] - H)
                    c = lg['ca']
                else:
                    P0 = PP + PR @ r.Lp[b]
                    d = norm(ankle[s] - P0)
                    c = lg['ft']
                u = r.Wr[b].T @ norm(r.Wp[c] - r.Wp[b])
                Wd = arc(W0 @ u, d) @ W0
            elif b in rows:
                row = rows[b]
                if row[0] == 'delta':
                    Wd = row[1] @ r.Wr[b]
                elif row[0] == 'swing':
                    c, dvec = row[1], row[2]
                    W0 = PR @ r.Lr[b]
                    u = r.Wr[b].T @ norm(r.Wp[c] - r.Wp[b])
                    self.margin[b] = pole_angle(dvec, W0[:, 2])
                    if guard:
                        dvec = guard_dir(dvec, W0[:, 2], *guard)
                    self.swing[b] = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(W0 @ u, dvec))))))
                    Wd = arc(W0 @ u, dvec) @ W0
                    tw = twist_of.get(b)
                    if tw:
                        Wd = axis_rot(dvec, rad(tw)) @ Wd
                else:                                   # palm
                    _, c, dvec, nvec, s = row
                    W0 = PR @ r.Lr[b]
                    self.margin[b] = pole_angle(dvec, W0[:, 2])
                    if guard and st.get('guard_hand', True):
                        dvec = guard_dir(dvec, W0[:, 2], *guard)
                    if c is not None:
                        u = r.Wr[b].T @ norm(r.Wp[c] - r.Wp[b])
                        self.swing[b] = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(W0 @ u, dvec))))))
                        S = arc(W0 @ u, dvec) @ W0
                    else:
                        S = W0
                    if s in r.palm0:
                        n_local = r.Wr[b].T @ r.palm0[s]
                        n_s = S @ n_local
                        ang = math.atan2(float(np.dot(dvec, np.cross(n_s, nvec))), float(np.dot(n_s, nvec)))
                        Wd = axis_rot(dvec, ang) @ S
                    else:
                        Wd = S
            if Wd is not None:
                Mb = r.Lr[b].T @ PR.T @ Wd
                M[b] = Mb
            else:
                Mb = I3
            AR[b] = PR @ r.Lr[b] @ Mb
            AP[b] = PP + PR @ r.Lp[b] + (trans_world if b == r.pel else 0)
            if b == r.pel:
                trans_local = PR.T @ trans_world
        # ---- fingers: curl about the bend axis of the base pose, relative to the hand (so they ride the hand)
        for s, chains in r.fingers.items():
            pre = 'l_' if s == 'L' else 'r_'
            claw = float(np.clip(P[pre + 'claw'], 0.0, 1.5))
            nrm0 = r.palm0.get(s)
            if nrm0 is None:
                continue
            for fid, chain in chains.items():
                total = claw * (45.0 if fid == 0 else 125.0)
                for k, bidx in enumerate(chain):
                    child = chain[k + 1] if k + 1 < len(chain) else None
                    if child is not None:
                        f = norm(r.Wp[child] - r.Wp[bidx])
                    elif k > 0:
                        f = norm(r.Wp[bidx] - r.Wp[chain[k - 1]])
                    else:
                        continue
                    a = -norm(np.cross(f, nrm0))
                    w = (0.3, 0.4, 0.3)[min(k, 2)]
                    Mf = axis_rot(r.Wr[bidx].T @ a, rad(total * w * (1.0 if fid else 1.0)))
                    M[bidx] = Mf
                    p = r.parent[bidx]
                    AR[bidx] = AR[p] @ r.Lr[bidx] @ Mf
        return M, trans_local, AR, AP


# ------------------------------------------------------------------------------------------------------------------------------ playback of data (what the engine draws)
def fk_pose(rig, M, trans_local):
    n = rig.n
    AR = [None] * n
    AP = [None] * n
    for b in range(n):
        p = rig.parent[b]
        PR = AR[p] if p >= 0 else I3
        PP = AP[p] if p >= 0 else np.zeros(3)
        Mb = M.get(b, I3)
        AR[b] = PR @ rig.Lr[b] @ Mb
        AP[b] = PP + PR @ (rig.Lp[b] + (trans_local if b == rig.pel else 0))
    return AR, AP


def manip_from_json_frame(rig, frame, interp_with=None, d=1.0):
    """BoneInfo of one JSON frame (optionally blended linearly with the previous frame by d, like pac's 'linear') -> (M dict, trans_local)"""
    M = {}
    trans = np.zeros(3)
    prev = interp_with['BoneInfo'] if interp_with is not None else None
    for name, e in frame['BoneInfo'].items():
        b = rig.idx.get(name)
        if b is None:
            continue
        a1 = np.array([e['RR'], e['RU'], e['RF']])
        if prev is not None and name in prev:
            pe = prev[name]
            a0 = np.array([pe['RR'], pe['RU'], pe['RF']])
            a = a0 + (a1 - a0) * d
        else:
            a = a1
        M[b] = angles_matrix(a)
        if b == rig.pel and 'MF' in e:
            t1 = np.array([e['MF'], -e['MR'], e['MU']])
            if prev is not None and name in prev and 'MF' in prev[name]:
                pe = prev[name]
                t0 = np.array([pe['MF'], -pe['MR'], pe['MU']])
                t1 = t0 + (t1 - t0) * d
            trans = t1
    return M, trans


# ------------------------------------------------------------------------------------------------------------------------------ JSON
def build_frames(rig, pose_fn, times, style=None):
    """sample pose_fn(t) -> pose dict at `times`; returns list of (angles dict bone->xyz, trans_local)"""
    sol = Solver(rig, style)
    frames = []
    prev = None
    for t in times:
        M, tl, AR, AP = sol.solve(pose_fn(t))
        ang = {}
        for b, Mb in M.items():
            a = source_angles(Mb)
            if prev is not None and b in prev:
                if style and style.get('branch_flip', False):
                    a = continuous(prev[b], a)
                else:                                   # principal branch only (the pole guard keeps |pitch| well below 90): unwrap the 360s, never flip branches
                    a = a + 360.0 * np.round((prev[b] - a) / 360.0)
            ang[b] = a
        prev = ang
        frames.append((ang, tl))
    return frames


def to_json(rig, frames, fps, ease_in=0.25, restart=2, name='thriller', dec=1, interp='linear', skip_still=0.0):
    """pac custom_animation data; frames[0] gets FrameRate 1/ease_in (it blends in from the base pose), RestartFrame 2 loops cleanly"""
    names = {}
    # bones that never move (all-zero manipulations) are left out
    ever = {}
    for ang, tl in frames:
        for b, a in ang.items():
            ever[b] = max(ever.get(b, 0.0), float(np.abs(a).max()))
    data = []
    for i, (ang, tl) in enumerate(frames):
        info = {}
        for b, a in ang.items():
            if ever[b] <= skip_still:
                continue
            e = {'RR': round(float(a[0]), dec) + 0.0, 'RU': round(float(a[1]), dec) + 0.0, 'RF': round(float(a[2]), dec) + 0.0}      # + 0.0 turns -0.0 into 0.0
            if b == rig.pel:
                e['MF'] = round(float(tl[0]), dec) + 0.0
                e['MR'] = round(float(-tl[1]), dec) + 0.0
                e['MU'] = round(float(tl[2]), dec) + 0.0
            info[rig.names[b]] = e
        data.append({'FrameRate': (1.0 / ease_in if (i == 0 and ease_in > 0) else float(fps)), 'BoneInfo': info})
    js = {'Type': 'sequence', 'Interpolation': interp, 'FrameData': data, 'Name': name, 'Notes': 'claude skill made by ax0rz0'}
    if restart:
        js['RestartFrame'] = restart
    return js
