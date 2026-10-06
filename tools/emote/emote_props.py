"""Props that ride the animation: 'carrier' bones.

ValveBiped.Anim_Attachment_RH / _LH have no skin weights on the ISD, medic and D-class models (checked in the .vvd files), and their
attachments of the same name hang on them. Moving such a bone through the custom_animation JSON moves a pac part whose `Bone` is
"attach right hand" / "attach left hand" (pac's friendly name for the BONE; pac.BoneNameReplacements: Anim_Attachment -> attach, RH -> right hand,
LH -> left hand, punctuation -> space) without bending any mesh. So a prop can be held, thrown, spun and parked far away with exactly the
timing of the dance, loop-safe, with no event, timer or proxy.

Frames (all verified in earlier sessions): game axes X forward, Y left, Z up; a ManipulateBonePosition vector is added to the bone's local
position in its parent's frame; ManipulateBoneAngles is post-multiplied: Wa(b) = Wa(parent) * Lbase(b) * M(b); JSON MF/MR/MU = (x, -y, z) of that vector.
"""
import numpy as np

from retarget import angles_matrix, source_angles, continuous

FAR = np.array([0.0, 0.0, 1500.0])           # where a hidden prop is parked (straight up, far outside any normal view)
CARRIER_RH = 'ValveBiped.Anim_Attachment_RH'
CARRIER_LH = 'ValveBiped.Anim_Attachment_LH'
PAC_BONE = {CARRIER_RH: 'attach right hand', CARRIER_LH: 'attach left hand'}


def Rz(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


class World:
    """Cached world rotations / positions (game frame, root motion included) of the retargeted skeleton at any source time."""

    def __init__(self, rt):
        self.rt = rt
        self._c = {}

    def at(self, t):
        key = int(round(t * 1e6))
        if key not in self._c:
            M, trans, (WR, WP), _ = self.rt.solve(t)
            tr = trans if trans is not None else np.zeros(3)
            self._c[key] = (WR, [p + tr for p in WP])
        return self._c[key]


def carrier_track(rt, valve, bone_full, times, pose_fn, world=None):
    """pose_fn(t) -> (R_world 3x3, p_world 3). Returns one {RR,RU,RF,MF,MR,MU} per time placing the carrier bone exactly there."""
    world = world or World(rt)
    b = valve.idx[bone_full]
    par = valve.parent[b]
    out, prev = [], None
    for t in times:
        WR, WP = world.at(t)
        PR, PP = WR[par], WP[par]
        R_des, p_des = pose_fn(t)
        manip = PR.T @ (np.asarray(p_des, float) - PP) - valve.Lp[b]
        Mb = valve.Lr[b].T @ PR.T @ R_des
        ang = source_angles(Mb)
        if prev is not None:
            ang = continuous(prev, ang)
        prev = ang
        out.append({'RR': ang[0], 'RU': ang[1], 'RF': ang[2], 'MF': manip[0], 'MR': -manip[1], 'MU': manip[2]})
    return out


def replay_carrier(valve, rt, entries, times, bone_full, t, world=None):
    """World pose of the carrier as pac would build it from the JSON entries (linear interpolation between frames), for verification."""
    world = world or World(rt)
    b = valve.idx[bone_full]
    par = valve.parent[b]
    ts = np.asarray(times)
    i = int(np.clip(np.searchsorted(ts, t, side='right') - 1, 0, len(ts) - 2))
    a = (t - ts[i]) / (ts[i + 1] - ts[i])
    e0, e1 = entries[i], entries[i + 1]
    g = lambda k: (1 - a) * e0[k] + a * e1[k]
    ang = np.array([g('RR'), g('RU'), g('RF')])
    manip = np.array([g('MF'), -g('MR'), g('MU')])
    WR, WP = world.at(t)
    PR, PP = WR[par], WP[par]
    R = PR @ valve.Lr[b] @ angles_matrix(ang)
    p = PP + PR @ (valve.Lp[b] + manip)
    return R, p


# ------------------------------------------------------------------------------------------------------------------------------------------
# Thought I Was Dead: the trumpet (ActMod prop CanineCronutMix; its own placement and throw, ported)
# ------------------------------------------------------------------------------------------------------------------------------------------
# ActMod puts the prop entity on the left hand bone (TypAtta 3, no offset) and sets, on the prop's 'main' bone, position (-2.5, -3.3, -1.0) and angles
# (-16, 103, 0); the prop's animation rotates its root by +90 deg yaw. So prop-model-space -> hand-bone-space is  R_EFF = Rz(90) * Angle(-16, 103, 0),
# T_EFF = Rz(90) * (-2.5, -3.3, -1.0). Verified: with this the mouthpiece (model +X end) sits 1-2 units from the character's mouth from 0.6 s to 3 s.
TRUMPET_R_EFF = Rz(90.0) @ angles_matrix((-16.0, 103.0, 0.0))
TRUMPET_T_EFF = Rz(90.0) @ np.array([-2.5, -3.3, -1.0])
TRUMPET_RELEASE = 3.6                      # ActMod cycle 0.18881118 of the 19.0667 s clip
TRUMPET_FLIGHT = 28.7 ** -1 * 19.0667      # attc = (cycle - 0.18881118) * 28.7  ->  0.664 s from release to landing
# ActMod's quadratic Bezier (player frame, feet origin; hup = 60.565 for the reference male model): up and behind, landing 64.5 units behind at the floor
TRUMPET_P1 = np.array([-(15 + 60.565 * 0.5), 2.0, 20 + 60.565 * 2.4])
TRUMPET_P2 = np.array([-(10 + 60.565 * 0.9), 0.0, 0.2])
TRUMPET_SPIN = np.array([-1.0, 0.1, 0.5]) * 400.0     # added to the release angles, scaled by attc


def trumpet_pose_fn(world, valve):
    Lh = valve.bone('L_Hand')

    def pose(t):
        WR, WP = world.at(t)
        if t < TRUMPET_RELEASE:
            Rh, ph = WR[Lh], WP[Lh]
            return Rh @ TRUMPET_R_EFF, ph + Rh @ TRUMPET_T_EFF
        if t > TRUMPET_RELEASE + TRUMPET_FLIGHT:
            return np.eye(3), FAR
        WR0, WP0 = world.at(TRUMPET_RELEASE)
        p0 = WP0[Lh]
        a = (t - TRUMPET_RELEASE) / TRUMPET_FLIGHT
        Re = angles_matrix(source_angles(WR0[Lh]) + TRUMPET_SPIN * a)
        pos = (1 - a) ** 2 * p0 + 2 * (1 - a) * a * TRUMPET_P1 + a * a * TRUMPET_P2
        return Re @ TRUMPET_R_EFF, pos + Re @ TRUMPET_T_EFF
    return pose


def extra_thoughtiwasdead(rt, valve, times):
    world = World(rt)
    track = carrier_track(rt, valve, CARRIER_LH, times, trumpet_pose_fn(world, valve), world)
    return [{CARRIER_LH: e} for e in track]


EXTRAS = {'thoughtiwasdead': extra_thoughtiwasdead}


# ------------------------------------------------------------------------------------------------------------------------------------------
# I'm a Mystery (EID_VoidRedemption, 'You Don't Know Me'): a glowing orb and hoops, choreographed on the two hand-attachment carriers.
# Timeline read off Epic's shop preview (4nite.site/videos/emotes/im-a-mystery.mp4) at 0.15 s steps; the effects repeat with the 7.333 s dance loop.
# tau = seconds since the dance loop started (source frame 22 of 60 fps = 0.367 s). One orb actor (right carrier) and one hoop actor (left carrier);
# every window below says where the actor is, outside the windows it is parked far away. Hoop radius is baked into the mesh (9.5).
# ------------------------------------------------------------------------------------------------------------------------------------------
MYSTERY_FPS = 60
MYSTERY_LOOP_START = 22
MYSTERY_LOOP_LEN = 440                         # frames at 60 fps (7.333 s)


def _tau(k):
    """Frame index k (60 fps) -> loop time in seconds; negative inside the intro."""
    if k < MYSTERY_LOOP_START:
        return (k - MYSTERY_LOOP_START) / 60.0
    return ((k - MYSTERY_LOOP_START) % MYSTERY_LOOP_LEN) / 60.0


# The windows below are in the labels of my contact sheets (video time minus the 0.367 s intro). The preview video actually starts AT the dance loop
# (silhouette-extent correlation 0.83 at an offset of -0.05 s), so loop time = video time + 0.05 = label + 0.417. _shift converts.
LABEL_SHIFT = 0.417


def _shift(windows):
    return [(a + LABEL_SHIFT, b + LABEL_SHIFT, kind) for a, b, kind in windows]


# (start, end, anchor) in label seconds
ORB_WINDOWS = _shift([(-0.15, 0.22, 'R'), (0.22, 0.62, 'L'), (0.80, 1.12, 'R'), (2.43, 3.03, 'Ldrop'), (4.85, 5.30, 'both')])
RING_WINDOWS = _shift([(0.22, 0.46, 'hoopR'), (1.28, 1.58, 'waist'), (1.60, 1.78, 'ankleR'), (1.78, 2.14, 'kneeR'), (2.16, 2.34, 'ankleL'),
                (2.34, 2.58, 'chest'), (3.22, 3.46, 'ankleL'), (3.52, 3.98, 'waist'), (4.02, 4.34, 'ankleL'), (4.74, 5.02, 'hoopR')])


def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def _ring_frame(axis):
    """Rotation whose local Z is `axis` (the ring mesh's axis), with a smooth, deterministic X."""
    z = _norm(axis)
    ref = np.array([0.0, 0.0, 1.0]) if abs(z[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = _norm(np.cross(ref, z))
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


class Anchors:
    """Anatomical anchor points / axes of the retargeted skeleton at a source time."""

    def __init__(self, world, valve, rt):
        self.w, self.v, self.rt = world, valve, rt

    def bone(self, t, short):
        WR, WP = self.w.at(t)
        b = self.v.bone(short)
        return WR[b], WP[b]

    def palm(self, t, side):
        """Point just above the palm centre and the palm normal (world)."""
        WR, WP = self.w.at(t)
        v = self.v
        b = v.bone(side + '_Hand')
        mid = v.bone(side + '_Finger2')
        d_local = v.Wr[b].T @ _norm(v.Wp[mid] - v.Wp[b])
        n_local = v.Wr[b].T @ self.rt.n_valve[side]
        d = WR[b] @ d_local
        n = WR[b] @ n_local
        return WP[b] + d * 4.2 + n * 2.8, d, n


def _window(tau, windows):
    for a, b, kind in windows:
        if a <= tau < b:
            return a, b, kind
    return None


def orb_pose_fn(world, valve, rt, fps=MYSTERY_FPS):
    A = Anchors(world, valve, rt)

    def pose(t):
        k = int(round(t * fps))
        tau = _tau(k)
        w = _window(tau, ORB_WINDOWS)
        if w is None:
            return np.eye(3), FAR
        a, b, kind = w
        if kind == 'R':
            p, d, n = A.palm(t, 'R')
        elif kind == 'L':
            p, d, n = A.palm(t, 'L')
        elif kind == 'Ldrop':                     # starts high above the left hand (the oval blob in the preview), settles into the hand (the orb cluster)
            p, d, n = A.palm(t, 'L')
            u = (tau - a) / (b - a)
            lift = max(0.0, 1.0 - u / 0.75) ** 1.3
            p = p + np.array([0.0, 10.0 * lift, 24.0 * lift])
        else:                                     # 'both': between the hands above the head (the starburst)
            pr, _, _ = A.palm(t, 'R')
            pl, _, _ = A.palm(t, 'L')
            p = (pr + pl) / 2 + np.array([0.0, 0.0, 4.0])
        return np.eye(3), p
    return pose


def ring_pose_fn(world, valve, rt, fps=MYSTERY_FPS):
    A = Anchors(world, valve, rt)

    def pose(t):
        k = int(round(t * fps))
        tau = _tau(k)
        w = _window(tau, RING_WINDOWS)
        if w is None:
            return np.eye(3), FAR
        kind = w[2]
        if kind == 'hoopR':                       # a hoop held up in the right hand, facing the camera (world X = the player's forward)
            p, d, n = A.palm(t, 'R')
            return _ring_frame(np.array([1.0, 0.0, 0.0])), p + np.array([0.0, 0.0, 4.0])
        if kind in ('waist', 'chest'):
            R, p = A.bone(t, 'Spine' if kind == 'waist' else 'Spine2')
            axis = R[:, 0]                        # spine bone: local X = up
            return _ring_frame(axis), p + axis * (1.0 if kind == 'waist' else 2.0)
        side = kind[-1]
        if kind.startswith('ankle'):
            Rf, pf = A.bone(t, side + '_Foot')
            _, pc = A.bone(t, side + '_Calf')
            return _ring_frame(pf - pc), pf + _norm(pf - pc) * 1.5
        if kind.startswith('knee'):
            _, pc = A.bone(t, side + '_Calf')
            _, pt = A.bone(t, side + '_Thigh')
            return _ring_frame(pc - pt), pc
        return np.eye(3), FAR
    return pose


def extra_mystery(rt, valve, times):
    world = World(rt)
    orb = carrier_track(rt, valve, CARRIER_RH, times, orb_pose_fn(world, valve, rt), world)
    ring = carrier_track(rt, valve, CARRIER_LH, times, ring_pose_fn(world, valve, rt), world)
    return [{CARRIER_RH: o, CARRIER_LH: r} for o, r in zip(orb, ring)]


EXTRAS['mystery'] = extra_mystery
