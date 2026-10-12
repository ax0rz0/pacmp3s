"""Small procedural mesh toolkit with UV coordinates for pac3 url models (own geometry, written as OBJ with vt + vn).

Mesh = vertices V (n,3), texture coordinates UV (n,2) in OBJ convention (v up), triangles F (m,3) wound counter-clockwise seen from OUTSIDE (pac reverses the winding, which makes
them front facing in Source). Open shapes (cards, ribbons) are meant to be drawn with the part's NoCulling flag.
"""
import numpy as np


class Mesh:
    def __init__(self, V=None, UV=None, F=None):
        self.V = np.zeros((0, 3)) if V is None else np.asarray(V, float)
        self.UV = np.zeros((0, 2)) if UV is None else np.asarray(UV, float)
        self.F = np.zeros((0, 3), int) if F is None else np.asarray(F, int)

    def copy(self):
        return Mesh(self.V.copy(), self.UV.copy(), self.F.copy())

    def add(self, other):
        o = len(self.V)
        self.V = np.vstack([self.V, other.V])
        self.UV = np.vstack([self.UV, other.UV])
        self.F = np.vstack([self.F, other.F + o])
        return self

    def transform(self, R=None, t=None, s=1.0):
        V = self.V * s
        if R is not None:
            V = V @ np.asarray(R, float).T
        if t is not None:
            V = V + np.asarray(t, float)
        return Mesh(V, self.UV.copy(), self.F.copy())

    def flipped(self):
        return Mesh(self.V.copy(), self.UV.copy(), self.F[:, ::-1].copy())

    def signed_volume(self):
        v0, v1, v2 = self.V[self.F[:, 0]], self.V[self.F[:, 1]], self.V[self.F[:, 2]]
        return float(np.einsum('ij,ij->i', v0, np.cross(v1, v2)).sum() / 6.0)

    def normals(self):
        """smooth vertex normals; vertices sharing a position (UV seams) share the accumulated normal"""
        v0, v1, v2 = self.V[self.F[:, 0]], self.V[self.F[:, 1]], self.V[self.F[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        key = np.round(self.V, 5)
        _, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.ravel()
        acc = np.zeros((inv.max() + 1, 3))
        for k in range(3):
            np.add.at(acc, inv[self.F[:, k]], fn)
        n = acc[inv]
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        return np.where(ln > 1e-12, n / np.maximum(ln, 1e-12), np.array([0, 0, 1.0]))

    def write_obj(self, path, name, comment=None, watermark='claude skill made by ax0rz0'):
        N = self.normals()
        with open(path, 'w', newline='\n') as f:
            f.write('# %s\n' % watermark)
            if comment:
                f.write('# %s\n' % comment)
            f.write('# %d vertices, %d triangles (own procedural geometry)\no %s\n' % (len(self.V), len(self.F), name))
            for v in self.V:
                f.write('v %.4f %.4f %.4f\n' % tuple(v))
            for t in self.UV:
                f.write('vt %.4f %.4f\n' % tuple(t))
            for n in N:
                f.write('vn %.4f %.4f %.4f\n' % tuple(n))
            for a, b, c in self.F:
                f.write('f %d/%d/%d %d/%d/%d %d/%d/%d\n' % (a + 1, a + 1, a + 1, b + 1, b + 1, b + 1, c + 1, c + 1, c + 1))
        return len(self.V), len(self.F)


# ---------------------------------------------------------------------------------------------------------------------------- rotations
def Rx(deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def basis_from_x(x, up_hint=(0, 0, 1.0)):
    """rotation matrix whose first column is x (normalised) and whose third column is as close to up_hint as possible"""
    x = np.asarray(x, float)
    x = x / np.linalg.norm(x)
    up = np.asarray(up_hint, float)
    y = np.cross(up, x)
    if np.linalg.norm(y) < 1e-6:
        y = np.cross(np.array([0, 1.0, 0]), x)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    return np.stack([x, y, z], axis=1)


# ---------------------------------------------------------------------------------------------------------------------------- generic surfaces
def surface(fn, nu, nv, flip=False):
    """fn(U, V) -> (..., 3) over a (nu+1) x (nv+1) grid of u, v in [0,1]; UV = (u, v)."""
    us = np.linspace(0, 1, nu + 1)
    vs = np.linspace(0, 1, nv + 1)
    U, Vv = np.meshgrid(us, vs, indexing='ij')
    P = np.asarray(fn(U, Vv), float).reshape(-1, 3)
    UV = np.stack([U, Vv], axis=-1).reshape(-1, 2)
    idx = np.arange((nu + 1) * (nv + 1)).reshape(nu + 1, nv + 1)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
    m = Mesh(P, UV, F)
    return m.flipped() if flip else m


def orient_outward(m):
    """closed shapes: make the winding outward (positive signed volume)"""
    return m if m.signed_volume() >= 0 else m.flipped()


def ellipsoid(radii, nu=28, nv=16, taper=None):
    """taper(w) -> scale of the cross-section along local z (w in [-1, 1]); e.g. lambda w: 1 - 0.5*(w+1)/2 makes a cone-like ear"""
    a, b, c = radii

    def fn(U, V):
        th = 2 * np.pi * U
        ph = np.pi * V
        w = np.cos(ph)
        k = taper(w) if taper else 1.0
        return np.stack([a * k * np.sin(ph) * np.cos(th), b * k * np.sin(ph) * np.sin(th), c * w], axis=-1)
    return orient_outward(surface(fn, nu, nv))


def torus(R, r, nu=48, nv=12, rz=None):
    """ring in the xy plane around z; cross-section radius r (rz along z for a flat band)"""
    rz = r if rz is None else rz

    def fn(U, V):
        th = 2 * np.pi * U
        ph = 2 * np.pi * V
        return np.stack([(R + r * np.cos(ph)) * np.cos(th), (R + r * np.cos(ph)) * np.sin(th), rz * np.sin(ph)], axis=-1)
    return orient_outward(surface(fn, nu, nv))


def elliptic_torus(a, b, r, nu=48, nv=12, rz=None):
    """ring in the xy plane around z whose centre line is an ellipse with semi-axes a (x) and b (y); cross-section radius r in the plane (rz along z for a flat band)"""
    rz = r if rz is None else rz

    def fn(U, V):
        th = 2 * np.pi * U
        ph = 2 * np.pi * V
        c, s = np.cos(th), np.sin(th)
        nrm = np.hypot(b * c, a * s)
        k = r * np.cos(ph)
        return np.stack([a * c + k * b * c / nrm, b * s + k * a * s / nrm, rz * np.sin(ph)], axis=-1)
    return orient_outward(surface(fn, nu, nv))


def cylinder(r, h, sides=32):
    """axis z, from -h/2 to +h/2, with caps (a tube along z)"""
    return tube(np.array([[0, 0, -h / 2], [0, 0, h / 2]]), r, sides=sides)


def frames_along(path):
    """tangents and a parallel-transported normal/binormal frame along a polyline (K,3)"""
    P = np.asarray(path, float)
    K = len(P)
    T = np.zeros_like(P)
    T[1:-1] = P[2:] - P[:-2]
    T[0] = P[1] - P[0]
    T[-1] = P[-1] - P[-2]
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.array([0, 0, 1.0]) if abs(T[0] @ np.array([0, 0, 1.0])) < 0.95 else np.array([1.0, 0, 0])
    N = np.zeros_like(P)
    B = np.zeros_like(P)
    n = np.cross(ref, T[0])
    n /= np.linalg.norm(n)
    for k in range(K):
        if k > 0:
            axis = np.cross(T[k - 1], T[k])
            s = np.linalg.norm(axis)
            if s > 1e-9:
                axis /= s
                ang = np.arctan2(s, T[k - 1] @ T[k])
                # rodrigues rotate n about axis by ang
                n = n * np.cos(ang) + np.cross(axis, n) * np.sin(ang) + axis * (axis @ n) * (1 - np.cos(ang))
            n = n - (n @ T[k]) * T[k]
            n /= np.linalg.norm(n)
        N[k] = n
        B[k] = np.cross(T[k], n)
    return T, N, B


def tube(path, radius, sides=16, cap_start=True, cap_end=True, scale_nb=(1.0, 1.0), uv_turns=1.0):
    """sweep an elliptical section (radius (K,) or scalar; scale_nb stretches the section along normal / binormal) along a polyline; u runs along the path, v around it.
    Sides and caps are wound outward (tested explicitly)."""
    P = np.asarray(path, float)
    K = len(P)
    r = np.full(K, float(radius)) if np.isscalar(radius) else np.asarray(radius, float)
    T, N, B = frames_along(P)
    th = np.linspace(0, 2 * np.pi, sides + 1)
    ring = (np.cos(th)[None, :, None] * N[:, None, :] * scale_nb[0] + np.sin(th)[None, :, None] * B[:, None, :] * scale_nb[1]) * r[:, None, None]
    V = (P[:, None, :] + ring).reshape(-1, 3)
    u = np.linspace(0, 1, K)
    UV = np.stack([np.repeat(u[:, None], sides + 1, axis=1), np.tile(np.linspace(0, uv_turns, sides + 1), (K, 1))], axis=-1).reshape(-1, 2)
    idx = np.arange(K * (sides + 1)).reshape(K, sides + 1)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
    # outward test for the sides: face normals against the radial direction from the path
    v0 = V[F[:, 0]]
    fn = np.cross(V[F[:, 1]] - v0, V[F[:, 2]] - v0)
    rad = v0 - P[F[:, 0] // (sides + 1)]
    if np.einsum('ij,ij->', fn, rad) < 0:
        F = F[:, ::-1]
    out = Mesh(V, UV, F)
    for end, direction, uval, wanted in ((0, -T[0], 0.0, cap_start), (K - 1, T[-1], 1.0, cap_end)):
        if not wanted:
            continue
        ringp = P[end] + ring[end]
        Vc = np.vstack([P[end], ringp])
        UVc = np.vstack([[uval, 0.5], np.stack([np.full(sides + 1, uval), np.linspace(0, 1, sides + 1)], 1)])
        Fc = np.array([[0, 1 + i, 2 + i] for i in range(sides)])
        n = np.cross(Vc[Fc[:, 1]] - Vc[Fc[:, 0]], Vc[Fc[:, 2]] - Vc[Fc[:, 0]])
        if (n @ direction).sum() < 0:
            Fc = Fc[:, ::-1]
        out.add(Mesh(Vc, UVc, Fc))
    return out


def ribbon(path, width, up=(0, 0, 1.0), thickness=0.0):
    """flat strip following a polyline; width (K,) or scalar; the strip lies in the plane spanned by the path tangent and `side = tangent x up`"""
    P = np.asarray(path, float)
    K = len(P)
    w = np.full(K, float(width)) if np.isscalar(width) else np.asarray(width, float)
    T = np.zeros_like(P)
    T[1:-1] = P[2:] - P[:-2]
    T[0] = P[1] - P[0]
    T[-1] = P[-1] - P[-2]
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    upv = np.asarray(up, float)
    upv = np.tile(upv, (K, 1)) if upv.ndim == 1 else upv
    S = np.cross(T, upv)
    S /= np.maximum(np.linalg.norm(S, axis=1, keepdims=True), 1e-9)
    L = P - S * (w[:, None] / 2)
    Rr = P + S * (w[:, None] / 2)
    V = np.stack([L, Rr], axis=1).reshape(-1, 3)
    u = np.linspace(0, 1, K)
    UV = np.stack([np.repeat(u[:, None], 2, axis=1), np.tile([0.0, 1.0], (K, 1))], axis=-1).reshape(-1, 2)
    idx = np.arange(K * 2).reshape(K, 2)
    a, b, c, d = idx[:-1, 0], idx[1:, 0], idx[1:, 1], idx[:-1, 1]
    F = np.concatenate([np.stack([a, b, c], -1), np.stack([a, c, d], -1)])
    return Mesh(V, UV, F)


def rounded_rect(w, h, rc, seg=6):
    """outline points (counter-clockwise) of a rounded rectangle centred at the origin in the xy plane"""
    pts = []
    for cx, cy, a0 in ((w / 2 - rc, h / 2 - rc, 0), (-w / 2 + rc, h / 2 - rc, 90), (-w / 2 + rc, -h / 2 + rc, 180), (w / 2 - rc, -h / 2 + rc, 270)):
        for i in range(seg + 1):
            a = np.radians(a0 + 90.0 * i / seg)
            pts.append((cx + rc * np.cos(a), cy + rc * np.sin(a)))
    return np.array(pts)


def card(w, h, t, rc=0.25, seg=5, back_uv=(0.02, 0.02)):
    """thin rounded card in the xy plane, front face towards +z with UV (0..1 over the card), solid-colour back and rim (UV = back_uv). Closed shape: draw normally."""
    o = rounded_rect(w, h, rc, seg)
    n = len(o)
    uvf = np.stack([o[:, 0] / w + 0.5, o[:, 1] / h + 0.5], axis=1)
    # front
    Vf = np.vstack([[0, 0, t / 2], np.column_stack([o, np.full(n, t / 2)])])
    UVf = np.vstack([[0.5, 0.5], uvf])
    Ff = np.array([[0, 1 + i, 1 + (i + 1) % n] for i in range(n)])
    front = Mesh(Vf, UVf, Ff)
    # back
    Vb = np.vstack([[0, 0, -t / 2], np.column_stack([o, np.full(n, -t / 2)])])
    UVb = np.tile(back_uv, (n + 1, 1))
    back = Mesh(Vb, UVb, Ff).flipped()
    # rim
    Vr = np.vstack([np.column_stack([o, np.full(n, t / 2)]), np.column_stack([o, np.full(n, -t / 2)])])
    UVr = np.tile(back_uv, (2 * n, 1))
    Fr = []
    for i in range(n):
        j = (i + 1) % n
        Fr.append([i, n + i, n + j])
        Fr.append([i, n + j, j])
    rim = Mesh(Vr, UVr, np.array(Fr))
    m = Mesh()
    m.add(front).add(back).add(rim)
    return orient_outward(m)


def bow(width=3.4, height=1.7, depth=0.9, knot=0.55, tails=True):
    """a simple bow in the xz plane (x = width, y = depth axis, z = height): two pillow-shaped loops, a knot and two short tails"""
    m = Mesh()
    for sgn in (-1, 1):
        loop = ellipsoid((width / 4, depth / 2, height / 2), nu=20, nv=12, taper=lambda w: 1.0)
        loop = loop.transform(R=Ry(-sgn * 10), t=(sgn * width / 4, 0, 0))
        m.add(loop)
    m.add(ellipsoid((knot, knot * 0.9, knot * 0.9), nu=16, nv=10))
    if tails:
        for sgn in (-1, 1):
            tl = ribbon(np.array([[0, 0, -0.1], [sgn * 0.55, 0.0, -0.9], [sgn * 0.95, 0.0, -1.8]]), width=0.55, up=(0, 1, 0)).transform(t=(0, depth * 0.3, 0))
            m.add(tl)
    return m
