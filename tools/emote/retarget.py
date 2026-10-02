"""Mixamo -> ValveBiped retargeter producing pac3 custom_animation data.

Frames
  game world : +X forward, +Y left, +Z up (what pac / GMod bone matrices are in when the player yaw is 0)
  mixamo     : +X character-left, +Y up, +Z forward
  GAME_FROM_MIX maps mixamo vectors to game vectors.

Engine facts this relies on (all field- or source-verified):
  * pac custom_animation applies each bone's delta through ManipulateBoneAngles: the manipulation rotation is
    POST-multiplied in the bone's own base frame:  Wa(b) = Wa(parent) * Lbase(b) * M(b)
  * Angle(p, y, r) = Rz(y) * Ry(p) * Rx(r)   (Source AngleMatrix);  JSON fields RR/RU/RF = pitch/yaw/roll
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
        # 180 degrees: pick any perpendicular axis
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


# ------------------------------------------------------------------ valve target
class Valve:
    def __init__(self, mdl):
        from mdl_anim import angle_between  # noqa
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


# ------------------------------------------------------------------ mapping
# (valve short, mixamo name, mode, aim child valve short, aim child mixamo)
def mapping():
    rows = [
        ('Pelvis', 'Hips', 'delta', None, None),
        ('Spine', 'Spine', 'delta', None, None),
        ('Spine1', 'Spine1', 'delta', None, None),
        ('Spine2', 'Spine2', 'delta', None, None),
        ('Neck1', 'Neck', 'delta', None, None),
        ('Head1', 'Head', 'delta', None, None),
    ]
    for s, side in (('R', 'Right'), ('L', 'Left')):
        rows += [
            ('%s_Clavicle' % s, side + 'Shoulder', 'delta', None, None),
            ('%s_UpperArm' % s, side + 'Arm', 'swing', '%s_Forearm' % s, side + 'ForeArm'),
            ('%s_Forearm' % s, side + 'ForeArm', 'swing', '%s_Hand' % s, side + 'Hand'),
            ('%s_Hand' % s, side + 'Hand', 'palm', '%s_Finger2' % s, side + 'HandMiddle1'),
            ('%s_Thigh' % s, side + 'UpLeg', 'swing', '%s_Calf' % s, side + 'Leg'),
            ('%s_Calf' % s, side + 'Leg', 'swing', '%s_Foot' % s, side + 'Foot'),
            ('%s_Foot' % s, side + 'Foot', 'delta', None, None),
            ('%s_Toe0' % s, side + 'ToeBase', 'delta', None, None),
        ]
    return rows


class Retargeter:
    def __init__(self, scene: Scene, valve: Valve, root_motion=False, root_scale=None, root_frame='parent'):
        self.sc, self.v = scene, valve
        self.rows = mapping()
        self.mx = {}
        for r in self.rows:
            nm = 'mixamorig:' + r[1]
            if nm not in scene.by_name:
                raise KeyError('mixamo bone missing: ' + nm)
        self.rest_W = scene.world_matrices(None)
        self.root_motion = root_motion
        self.root_frame = root_frame   # 'parent' = vector added to the bone's local position in parent (game) space; 'bone' = rotated by the bone's base frame
        hips_rest = self.rest_W[scene.by_name['mixamorig:Hips']['id']][:3, 3]
        self.hips_rest = GAME_FROM_MIX @ hips_rest
        self.root_scale = root_scale if root_scale is not None else valve.Wp[valve.bone('Pelvis')][2] / self.hips_rest[2]
        # valve bone order, parents first
        self.order = list(range(valve.m.n))

    def mix_pose(self, W):
        """dict mixamo short name -> (R_game, p_game)"""
        out = {}
        for r in self.rows:
            for nm in (r[1], r[4]):
                if nm and nm not in out:
                    M = W[self.sc.by_name['mixamorig:' + nm]['id']]
                    out[nm] = (GAME_FROM_MIX @ rot_of(M) @ GAME_FROM_MIX.T, GAME_FROM_MIX @ M[:3, 3])
        return out

    def solve(self, t_ticks):
        """Return (manip dict valve_bone_index -> 3x3 M, pelvis_local_translation or None, achieved world (R list, P list), wanted world rotations)."""
        v = self.v
        W = self.sc.world_matrices(t_ticks)
        cur = self.mix_pose(W)
        rest = self.mix_pose(self.rest_W)
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
                vs, mx, mode, vc, mc = rows[b]
                Rm_a, _ = cur[mx]
                Rm_r, _ = rest[mx]
                if mode == 'delta':
                    Wd = (Rm_a @ Rm_r.T) @ v.Wr[b]
                else:
                    c = v.bone(vc)
                    d_m = norm(cur[mc][1] - cur[mx][1])
                    W0 = PR @ v.Lr[b]                      # orientation if this bone were left alone (given the posed parent)
                    u = v.Wr[b].T @ norm(v.Wp[c] - v.Wp[b])  # aim direction in the bone's own frame
                    S = arc(W0 @ u, d_m) @ W0              # minimal swing from the parent-induced pose: no 180 degree flips
                    if mode == 'palm':
                        # spin about the hand direction so the palm normals agree. Mixamo T-pose palms face the floor;
                        # the matching Valve palm normal is whatever becomes 'down' after the shortest swing to the
                        # T-pose hand direction (palm-inward on an A-pose arm).
                        n_rest = np.array([0.0, 0.0, -1.0])
                        d_m_rest = norm(rest[mc][1] - rest[mx][1])
                        d_v = norm(v.Wp[c] - v.Wp[b])
                        n_local = v.Wr[b].T @ (arc(d_m_rest, d_v) @ n_rest)
                        n_s = S @ n_local
                        n_m = (Rm_a @ Rm_r.T) @ n_rest
                        ang = math.atan2(float(np.dot(d_m, np.cross(n_s, n_m))), float(np.dot(n_s, n_m)))
                        Wd = axis_rot(d_m, ang) @ S
                    else:
                        Wd = S
                want[b] = Wd
                Mb = v.Lr[b].T @ PR.T @ Wd
                M[b] = Mb
            else:
                Mb = np.eye(3)
            Wa_R[b] = PR @ v.Lr[b] @ Mb
            Wa_P[b] = PP + PR @ v.Lp[b]
        trans = None
        if self.root_motion:
            pel = v.bone('Pelvis')
            dp = (cur['Hips'][1] - self.hips_rest) * self.root_scale
            trans = dp if self.root_frame == 'parent' else v.Lr[pel].T @ dp
        return M, trans, (Wa_R, Wa_P), want

    def frame_angles(self, t_ticks, prev=None):
        M, trans, achieved, want = self.solve(t_ticks)
        out = {}
        for b, Mb in M.items():
            a = source_angles(Mb)
            if prev is not None and b in prev:
                a = continuous(prev[b], a)
            out[b] = a
        return out, trans, achieved, want


def bone_name(v, b):
    return v.m.names[b]
