"""Source rig -> ValveBiped retargeter producing pac3 custom_animation data.

Sources: MixamoSource (FBX skeleton), ValveAnimSource (animations already on the Valve skeleton, e.g. the wOS Fortnite taunt models).

Frames
  game world : +X forward, +Y left, +Z up (what pac / GMod bone matrices are in when the player yaw is 0)
  mixamo     : +X character-left, +Y up, +Z forward;  GAME_FROM_MIX maps mixamo vectors to game vectors.

Engine facts this relies on (all field- or source-verified):
  * pac custom_animation applies each bone's delta through ManipulateBoneAngles: the manipulation rotation is
    POST-multiplied in the bone's own base frame:  Wa(b) = Wa(parent) * Lbase(b) * M(b)
  * a ManipulateBonePosition vector is added to the bone's local position in PARENT space (game axes for the pelvis)
  * Angle(p, y, r) = Rz(y) * Ry(p) * Rx(r)   (Source AngleMatrix); JSON fields RR/RU/RF = pitch/yaw/roll
  * 'sequence' animations play on top of the model's local sequence 0 (decoded here as the base pose).
"""
import math
import numpy as np

from fbx_anim import Scene, rot_of, KTIME

GAME_FROM_MIX = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
EPS = 1e-9


# ------------------------------------------------------------------ small math
def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > EPS else v


def arc(a, b):
    """Shortest-arc rotation matrix taking unit vector a to unit vector b."""
    a, b = norm(a), norm(b)
    c = float(np.dot(a, b))
    if c > 1 - 1e-12:
        return np.eye(3)
    if c < -1 + 1e-12:
        ax = norm(np.cross(a, [1.0, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1.0, 0]))
        return 2 * np.outer(ax, ax) - np.eye(3)
    v = np.cross(a, b)
    s2 = float(np.dot(v, v))
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / s2)


def axis_rot(axis, ang):
    a = norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


def source_angles(M):
    """3x3 -> (pitch, yaw, roll) degrees per Source MatrixAngles (M = Rz(yaw) Ry(pitch) Rx(roll))."""
    xy = math.hypot(M[0, 0], M[1, 0])
    if xy > 1e-4:
        yaw = math.atan2(M[1, 0], M[0, 0]); pitch = math.atan2(-M[2, 0], xy); roll = math.atan2(M[2, 1], M[2, 2])
    else:
        yaw = math.atan2(-M[0, 1], M[1, 1]); pitch = math.atan2(-M[2, 0], xy); roll = 0.0
    return np.array([math.degrees(pitch), math.degrees(yaw), math.degrees(roll)])


def angles_matrix(pyr):
    p, y, r = [math.radians(x) for x in pyr]
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def continuous(prev, cur):
    """Pick the Euler triple equivalent to `cur` that is closest to `prev` (unwrap 360s, try the pitch-flip branch)."""
    def unwrap(a, ref):
        return a + 360.0 * np.round((ref - a) / 360.0)
    c1 = unwrap(cur, prev)
    alt = np.array([180.0 - cur[0], cur[1] + 180.0, cur[2] + 180.0])
    c2 = unwrap(alt, prev)
    return c1 if np.abs(c1 - prev).sum() <= np.abs(c2 - prev).sum() else c2


def mat_to_quat(R):
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s])
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = np.array([0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s])
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = np.array([(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s])
    else:
        s = math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = np.array([(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s])
    return q / np.linalg.norm(q)


def quat_to_rot(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp_rot(Ra, Rb, a):
    qa, qb = mat_to_quat(Ra), mat_to_quat(Rb)
    d = float(np.dot(qa, qb))
    if d < 0:
        qb, d = -qb, -d
    if d > 0.9995:
        q = qa + a * (qb - qa)
    else:
        th = math.acos(min(1.0, d)); q = (math.sin((1 - a) * th) * qa + math.sin(a * th) * qb) / math.sin(th)
    return quat_to_rot(q / np.linalg.norm(q))


def palm_normal(hand, mid, idx, pnk, side_sign):
    """Palm-side normal from hand geometry. Same formula on every rig, so the anatomical side agrees between rigs.
    Verified on a Mixamo T-pose: (0,0,-1) (palms down) for both hands."""
    return norm(np.cross(norm(mid - hand), pnk - idx) * side_sign)


# ------------------------------------------------------------------ valve target
class Valve:
    def __init__(self, mdl):
        self.m = mdl
        label, a0 = mdl.seq_info(0)
        self.seq0 = label
        loc, _, _, _ = mdl.anim_frame(a0, 0)
        self.Lr = [l[0] for l in loc]
        self.Lp = [l[1] for l in loc]
        W = mdl.fk(loc)
        self.Wr = [w[0] for w in W]          # base world rotations (game frame)
        self.Wp = [w[1] for w in W]          # base world positions (game frame)
        self.parent = mdl.parent
        self.idx = mdl.index

    def bone(self, short):
        return self.idx['ValveBiped.Bip01_' + short]

    def has(self, short):
        return ('ValveBiped.Bip01_' + short) in self.idx


# ------------------------------------------------------------------ mapping rows
# (valve short, source key, mode, valve child short, source child key)
def body_rows(spine4=False, fingers=False):
    r = lambda v, mode, vc=None: (v, v, mode, vc, vc)
    rows = [r('Pelvis', 'delta'), r('Spine', 'delta'), r('Spine1', 'delta'), r('Spine2', 'delta')]
    if spine4:
        rows.append(r('Spine4', 'delta'))
    rows += [r('Neck1', 'delta'), r('Head1', 'delta')]
    for s in ('R', 'L'):
        rows += [r('%s_Clavicle' % s, 'delta'),
                 r('%s_UpperArm' % s, 'swing', '%s_Forearm' % s),
                 r('%s_Forearm' % s, 'swing', '%s_Hand' % s),
                 r('%s_Hand' % s, 'palm', '%s_Finger2' % s),
                 r('%s_Thigh' % s, 'swing', '%s_Calf' % s),
                 r('%s_Calf' % s, 'swing', '%s_Foot' % s),
                 r('%s_Foot' % s, 'delta'),
                 r('%s_Toe0' % s, 'delta')]
        if fingers:
            for f in ('0', '01', '02', '1', '11', '12', '2', '21', '22', '3', '31', '32', '4', '41', '42'):
                rows.append(r('%s_Finger%s' % (s, f), 'local'))
    return rows


class MixamoSource:
    """Mixamo FBX skeleton. Keys are Valve short names; `names` maps them to mixamorig bones."""

    def __init__(self, scene: Scene):
        self.sc = scene
        names = {'Pelvis': 'Hips', 'Spine': 'Spine', 'Spine1': 'Spine1', 'Spine2': 'Spine2', 'Neck1': 'Neck', 'Head1': 'Head'}
        for s, side in (('R', 'Right'), ('L', 'Left')):
            names.update({'%s_Clavicle' % s: side + 'Shoulder', '%s_UpperArm' % s: side + 'Arm', '%s_Forearm' % s: side + 'ForeArm',
                          '%s_Hand' % s: side + 'Hand', '%s_Finger2' % s: side + 'HandMiddle1', '%s_Finger1' % s: side + 'HandIndex1',
                          '%s_Finger4' % s: side + 'HandPinky1', '%s_Thigh' % s: side + 'UpLeg', '%s_Calf' % s: side + 'Leg',
                          '%s_Foot' % s: side + 'Foot', '%s_Toe0' % s: side + 'ToeBase'})
        self.names = names
        self.rows = body_rows()
        for k, v in names.items():
            if 'mixamorig:' + v not in scene.by_name:
                raise KeyError('mixamo bone missing: ' + v)
        self._rest = self._pose_at(None)
        self.duration = scene.duration()

    def _pose_at(self, t_ticks):
        W = self.sc.world_matrices(t_ticks)
        out = {}
        for k, v in self.names.items():
            M = W[self.sc.by_name['mixamorig:' + v]['id']]
            out[k] = (GAME_FROM_MIX @ rot_of(M) @ GAME_FROM_MIX.T, GAME_FROM_MIX @ M[:3, 3])
        return out

    def rest(self):
        return self._rest

    def pose(self, t):
        return self._pose_at(int(round(t * KTIME)))

    def local_rot(self, t):
        return {}


class ValveAnimSource:
    """An animation that already lives on the Valve skeleton (e.g. wOS Fortnite taunts: model + external .ani)."""

    def __init__(self, anim_mdl, ani_bytes, anim_index, fingers=True):
        self.m, self.ani, self.ai = anim_mdl, ani_bytes, anim_index
        info = anim_mdl.anim_info(anim_index)
        self.fps, self.nframes, self.label = info['fps'], info['frames'], info['name']
        self.duration = (self.nframes - 1) / self.fps
        rows = body_rows(spine4=True, fingers=fingers)
        keys = {k for r in rows for k in (r[1], r[4]) if k}
        for s in ('R', 'L'):
            keys.update(['%s_Finger0' % s, '%s_Finger1' % s, '%s_Finger2' % s, '%s_Finger4' % s, '%s_Hand' % s])
        self.keys = {k for k in keys if ('ValveBiped.Bip01_' + k) in anim_mdl.index}
        self.rows = [r for r in rows if r[1] in self.keys and (r[4] is None or r[4] in self.keys)]
        loc, *_ = anim_mdl.anim_frame(0, 0, ani_bytes)   # 'reference' = rest (game frame, includes the +90 root rotation)
        self._rest = self._pack(anim_mdl.fk(loc))
        self._cache = {}
        self._ikeys = {}

    def _pack(self, W):
        return {k: (W[self.m.index['ValveBiped.Bip01_' + k]][0], W[self.m.index['ValveBiped.Bip01_' + k]][1]) for k in self.keys}

    def rest(self):
        return self._rest

    def _local(self, f):
        if f not in self._cache:
            self._cache[f], *_ = self.m.anim_frame(self.ai, f, self.ani)
        return self._cache[f]

    def _frame(self, t):
        """Locals interpolated between the two surrounding source frames (rotations slerped), like the engine samples an animation."""
        x = min(max(t * self.fps, 0.0), self.nframes - 1.0)
        f0 = int(math.floor(x)); f1 = min(f0 + 1, self.nframes - 1); a = x - f0
        key = (f0, round(a, 4))
        if key not in self._ikeys:
            L0, L1 = self._local(f0), self._local(f1)
            if a < 1e-6 or f0 == f1:
                loc = L0
            else:
                loc = [(slerp_rot(L0[i][0], L1[i][0], a), L0[i][1] * (1 - a) + L1[i][1] * a) for i in range(self.m.n)]
            self._ikeys = {key: (self._pack(self.m.fk(loc)), {k: loc[self.m.index['ValveBiped.Bip01_' + k]][0] for k in self.keys})}
        return self._ikeys[key]

    def pose(self, t):
        return self._frame(t)[0]

    def local_rot(self, t):
        return self._frame(t)[1]


# ------------------------------------------------------------------ the solver
class Retargeter:
    def __init__(self, source, valve: Valve, root_motion=False, root_scale=None, root_frame='parent', root_axes='full'):
        self.src, self.v = source, valve
        self.rows = [r for r in source.rows if valve.has(r[0]) and (r[3] is None or valve.has(r[3]))]
        self.root_motion = root_motion
        self.root_frame = root_frame      # 'parent': vector added to the bone's local position in parent (game) space
        self.root_axes = root_axes        # 'full' | 'vertical'
        self.rest = source.rest()
        self.hips_rest = self.rest['Pelvis'][1]
        self.root_scale = root_scale if root_scale is not None else valve.Wp[valve.bone('Pelvis')][2] / self.hips_rest[2]
        self.order = list(range(valve.m.n))
        self.n_valve, self.n_src_rest = {}, {}
        for s, sign in (('R', 1.0), ('L', -1.0)):
            hand, mid, idx, pnk, thumb = ['%s_%s' % (s, k) for k in ('Hand', 'Finger2', 'Finger1', 'Finger4', 'Finger0')]
            # side vector runs from the thumb side to the pinky side; models with 3-finger hands fall back to thumb -> index
            for a, b in ((idx, pnk), (thumb, idx)):
                keys = [hand, mid, a, b]
                if all(valve.has(k) for k in keys) and all(k in self.rest for k in keys):
                    pn = lambda P: palm_normal(P(hand), P(mid), P(a), P(b), sign)
                    self.n_valve[s] = pn(lambda k: valve.Wp[valve.bone(k)])
                    self.n_src_rest[s] = pn(lambda k: self.rest[k][1])
                    break

    def solve(self, t):
        """t in seconds. Returns (manip dict valve_bone_index -> 3x3 M, pelvis translation or None,
        achieved world (R list, P list), wanted world rotations)."""
        v = self.v
        cur = self.src.pose(t)
        locs = self.src.local_rot(t)
        rest = self.rest
        rows = {v.bone(r[0]): r for r in self.rows}
        Wa_R = [None] * v.m.n
        Wa_P = [None] * v.m.n
        M = {}
        want = {}
        for b in self.order:
            p = v.parent[b]
            PR = Wa_R[p] if p >= 0 else np.eye(3)
            PP = Wa_P[p] if p >= 0 else np.zeros(3)
            if b in rows:
                vs, sk, mode, vc, sc = rows[b]
                if mode == 'local':
                    Mb = v.Lr[b].T @ locs[sk]            # engine-equivalent: the animation's absolute local rotation
                    Wd = PR @ v.Lr[b] @ Mb
                else:
                    Rm_a, _ = cur[sk]
                    Rm_r, _ = rest[sk]
                    if mode == 'delta':
                        Wd = (Rm_a @ Rm_r.T) @ v.Wr[b]
                    else:
                        c = v.bone(vc)
                        d_m = norm(cur[sc][1] - cur[sk][1])
                        W0 = PR @ v.Lr[b]                      # orientation if this bone were left alone (given the posed parent)
                        u = v.Wr[b].T @ norm(v.Wp[c] - v.Wp[b])  # aim direction in the bone's own frame
                        S = arc(W0 @ u, d_m) @ W0              # minimal swing from the parent-induced pose: no 180 degree flips
                        if mode == 'palm' and vs[0] in self.n_valve:
                            side = vs[0]
                            n_local = v.Wr[b].T @ self.n_valve[side]
                            n_s = S @ n_local
                            n_m = (Rm_a @ Rm_r.T) @ self.n_src_rest[side]
                            ang = math.atan2(float(np.dot(d_m, np.cross(n_s, n_m))), float(np.dot(n_s, n_m)))
                            Wd = axis_rot(d_m, ang) @ S
                        else:
                            Wd = S
                    Mb = v.Lr[b].T @ PR.T @ Wd
                want[b] = Wd
                M[b] = Mb
            else:
                Mb = np.eye(3)
            Wa_R[b] = PR @ v.Lr[b] @ Mb
            Wa_P[b] = PP + PR @ v.Lp[b]
        trans = None
        if self.root_motion:
            pel = v.bone('Pelvis')
            dp = (cur['Pelvis'][1] - self.hips_rest) * self.root_scale
            if self.root_axes == 'vertical':
                dp = np.array([0.0, 0.0, dp[2]])
            trans = dp if self.root_frame == 'parent' else v.Lr[pel].T @ dp
        return M, trans, (Wa_R, Wa_P), want

    def frame_angles(self, t, prev=None):
        M, trans, achieved, want = self.solve(t)
        out = {}
        for b, Mb in M.items():
            a = source_angles(Mb)
            if prev is not None and b in prev:
                a = continuous(prev[b], a)
            out[b] = a
        return out, trans, achieved, want


def bone_name(v, b):
    return v.m.names[b]
