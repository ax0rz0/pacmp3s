"""Accessories for the three BNA Ethics Assistant styles (own geometry), placed on the femsuit_04 body in the in-game bind pose.

Every accessory is built in WORLD space (x forward, y left, z up, bind pose) from the real body surface (ray casts), then converted into the local frame of the bone it is
attached to, so the OBJ can be used with Position/Angles 0 and the part simply follows the bone.
"""
import re
import numpy as np

import meshgen as mg
from meshgen import Mesh
from ethics_common import PINK, MAGENTA, INDIGO, ROYAL, NAVY


# ------------------------------------------------------------------------------------------------------------------------------ pac friendly bone names
_REPL = [('Anim_Attachment', 'attach'), ('RH', 'right hand'), ('LH', 'left hand'), ('_L_', ' left '), ('_R_', ' right '), (None, ' '), ('ValveBiped', ''), ('Bip01', ''), ('Neck1', 'neck'),
         ('Head1', 'head'), ('Toe0', 'toe'), ('lowerarm', 'lower arm'), ('Bip', ''), (' R', ' right'), (' L', ' left')]


def friendly(name):
    """pac.BoneNameReplacements of the server's pac3 build, applied in order (None = every punctuation character), then trim, lowercase and a space before digit runs"""
    s = name
    for a, b in _REPL:
        s = re.sub(r'[!-/:-@\[-`{-~]', ' ', s) if a is None else s.replace(a, b)
    s = s.strip().lower()
    return re.sub(r'(.*?)(\d+)', r'\1 \2', s)


# ------------------------------------------------------------------------------------------------------------------------------ surface ray casts
class Surface:
    def __init__(self, pos):
        pos = np.asarray(pos, float)
        self.v0 = pos[:, 0]
        self.e1 = pos[:, 1] - pos[:, 0]
        self.e2 = pos[:, 2] - pos[:, 0]
        n = np.cross(self.e1, self.e2)
        self.n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    def cast(self, o, d, tmax=1e9):
        """nearest hit of the ray o + t d: (t, point, unit normal facing the ray origin) or None"""
        o = np.asarray(o, float)
        d = np.asarray(d, float) / np.linalg.norm(d)
        h = np.cross(d, self.e2)
        a = np.einsum('ij,ij->i', self.e1, h)
        ok = np.abs(a) > 1e-12
        f = np.where(ok, 1.0 / np.where(ok, a, 1), 0)
        s = o - self.v0
        u = f * np.einsum('ij,ij->i', s, h)
        q = np.cross(s, self.e1)
        v = f * (q @ d)
        t = f * np.einsum('ij,ij->i', self.e2, q)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < tmax)
        if not hit.any():
            return None
        i = np.nonzero(hit)[0][np.argmin(t[hit])]
        n = self.n[i] if self.n[i] @ d < 0 else -self.n[i]
        return float(t[i]), o + t[i] * d, n

    def front(self, y, z, x0=40.0):
        r = self.cast((x0, y, z), (-1, 0, 0))
        return None if r is None else r[1:]

    def back(self, y, z, x0=-40.0):
        r = self.cast((x0, y, z), (1, 0, 0))
        return None if r is None else r[1:]

    def side(self, x, z, sgn=+1, y0=40.0):
        r = self.cast((x, sgn * y0, z), (0, -sgn, 0))
        return None if r is None else r[1:]

    def radial(self, centre_xy, z, ang_deg, rmax=20.0):
        a = np.radians(ang_deg)
        d = np.array([np.cos(a), np.sin(a), 0.0])
        o = np.array([centre_xy[0], centre_xy[1], z]) + d * rmax
        r = self.cast(o, -d)
        return None if r is None else r[1:]


# ------------------------------------------------------------------------------------------------------------------------------ an accessory = world-space mesh + how to draw it in pac
class Acc:
    def __init__(self, name, mesh, bone, color=None, material='solid', alpha=None, nocull=False, nolight=False, texture=None, translucent=False, kind='model', size=1.0, note=''):
        self.name = name
        self.mesh = mesh                 # world space, bind pose, game frame
        self.bone = bone                 # full ValveBiped name
        self.color = color               # palette tuple (0..255) or None
        self.material = material         # 'solid' (debugwhite tinted by color) or 'texture'
        self.alpha = alpha
        self.nocull = nocull
        self.nolight = nolight
        self.texture = texture           # RGB array for textured parts
        self.translucent = translucent
        self.kind = kind
        self.size = size
        self.note = note

    def local_mesh(self, rig):
        if hasattr(rig, 'localize'):                      # a DeformedRig: the outfit scales bones (tech_deform.py)
            return Mesh(rig.localize(self.bone, self.mesh.V), self.mesh.UV.copy(), self.mesh.F.copy())
        W = rig.world[rig.idx[self.bone]]
        R = W[:3, :3]
        return Mesh((self.mesh.V - W[:3, 3]) @ R, self.mesh.UV.copy(), self.mesh.F.copy())


def to_world(mesh, R, t):
    """place a locally authored mesh: world = R @ v + t"""
    return mesh.transform(R=R, t=t)


def smooth_path(points, n=40):
    """Catmull-Rom through points (K,3) -> (n,3)"""
    P = np.asarray(points, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    ts = np.linspace(0, len(P) - 3, n)
    for t in ts:
        i = min(int(t), len(P) - 4)
        u = t - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    return np.array(out)


def rounded_rect_path(w, h, rc, seg=8, plane='yz', centre=(0, 0, 0)):
    """closed rounded-rectangle polyline (first point repeated at the end) lying in a coordinate plane"""
    o = mg.rounded_rect(w, h, rc, seg)
    o = np.vstack([o, o[:1]])
    c = np.asarray(centre, float)
    if plane == 'yz':      # width along y, height along z (a frame facing +x)
        return np.column_stack([np.full(len(o), c[0]), c[1] + o[:, 0], c[2] + o[:, 1]])
    raise ValueError(plane)
