"""Hard-surface / organic mesh toolkit for the advanced PAC outfits (own procedural geometry, written as OBJ with angle-aware normals).

Everything works on meshgen.Mesh (V, UV, F; triangles wound counter-clockwise seen from OUTSIDE, which pac reverses into Source's front faces).
  grid_mesh(P, holes)          quad grid of points -> Mesh
  solidify(Po, Pi, keep)       outer + inner grid + rim strips (also around holes) -> closed shell
  loft(path, section_fn, ...)  sweep any closed 2D section (with per-station scale / twist) along a 3D path (horns, tails, fangs, cables)
  Radial                       distance field of a surface seen from a centre (a smooth 'skull' to build masks / caps / hair on)
  write_obj_smooth             OBJ writer that splits vertices at hard edges (normals follow a smoothing angle)
"""
import numpy as np

import meshgen as mg
from meshgen import Mesh, Rx, Ry, Rz

EPS = 1e-9


def unit(v):
    v = np.asarray(v, float)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), EPS)


def merge(meshes):
    m = Mesh()
    for x in meshes:
        if x is not None and len(x.V):
            m.add(x)
    return m


def mirror_y(m):
    """reflect through the xz plane (y -> -y) and fix the winding"""
    V = m.V * np.array([1.0, -1.0, 1.0])
    return Mesh(V, m.UV.copy(), m.F[:, ::-1].copy())


def sym(m):
    """the mesh plus its y-mirror"""
    return merge([m, mirror_y(m)])


# ------------------------------------------------------------------------------------------------------------------------------ OBJ output with a smoothing angle
def corner_normals(m, smooth_deg=35.0):
    """per-face-corner normals: faces sharing a position are smoothed together only when their normals differ by less than smooth_deg"""
    V, F = m.V, m.F
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    area = np.linalg.norm(fn, axis=1)
    fnu = fn / np.maximum(area, EPS)[:, None]
    key = np.round(V, 4)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    cos_t = np.cos(np.radians(smooth_deg))
    out = np.zeros((len(F), 3, 3))
    order = np.argsort(inv[F].ravel(), kind='stable')
    flat_pos = inv[F].ravel()
    faces_of = {}
    for idx in order:
        faces_of.setdefault(flat_pos[idx], []).append(idx // 3)
    for pid, fl in faces_of.items():
        fl = np.asarray(fl)
        if len(fl) == 1:
            n = fnu[fl[0]]
            for k in range(3):
                if inv[F[fl[0], k]] == pid:
                    out[fl[0], k] = n
            continue
        for f in fl:
            sel = fl[(fnu[fl] @ fnu[f]) >= cos_t]
            n = (fnu[sel] * area[sel][:, None]).sum(0)
            n = n / max(np.linalg.norm(n), EPS)
            for k in range(3):
                if inv[F[f, k]] == pid:
                    out[f, k] = n
    return out


def write_obj_smooth(m, path, name, comment=None, smooth_deg=35.0, watermark='claude skill made by ax0rz0'):
    """write OBJ (v / vt / vn, triangles); vertices are split where the normal differs (hard edges); normals and uvs are shared between vertices when equal. Returns (vertices, triangles)."""
    # drop degenerate (zero area) triangles: the poles of superellipsoids / spheres produce them and they would write zero-length normals
    V0, F0 = m.V, m.F
    area2 = np.linalg.norm(np.cross(V0[F0[:, 1]] - V0[F0[:, 0]], V0[F0[:, 2]] - V0[F0[:, 0]]), axis=1)
    if (area2 < 1e-7).any():
        m = Mesh(V0, m.UV, F0[area2 >= 1e-7])
    CN = corner_normals(m, smooth_deg)
    keys, remap = {}, np.zeros((len(m.F), 3), int)
    verts, uvi, nri = [], [], []
    uv_table, uv_ids = [], {}
    nr_table, nr_ids = [], {}
    for fi in range(len(m.F)):
        for k in range(3):
            vi = m.F[fi, k]
            nkey = tuple(np.round(CN[fi, k], 3))
            key = (vi, nkey)
            if key not in keys:
                keys[key] = len(verts)
                verts.append(m.V[vi])
                u = tuple(np.round(m.UV[vi], 3)) if len(m.UV) else (0.0, 0.0)
                if u not in uv_ids:
                    uv_ids[u] = len(uv_table)
                    uv_table.append(u)
                if nkey not in nr_ids:
                    nr_ids[nkey] = len(nr_table)
                    nr_table.append(nkey)
                uvi.append(uv_ids[u])
                nri.append(nr_ids[nkey])
            remap[fi, k] = keys[key]
    with open(path, 'w', newline='\n') as f:
        f.write('# %s\n' % watermark)
        if comment:
            f.write('# %s\n' % comment)
        f.write('# %d vertices, %d triangles (own procedural geometry)\no %s\n' % (len(verts), len(m.F), name))
        for v in verts:
            f.write('v %.3f %.3f %.3f\n' % tuple(v))
        for t in uv_table:
            f.write('vt %.3f %.3f\n' % tuple(t))
        for n in nr_table:
            f.write('vn %.3f %.3f %.3f\n' % tuple(n))
        for a, b, c in remap:
            f.write('f %d/%d/%d %d/%d/%d %d/%d/%d\n' % (a + 1, uvi[a] + 1, nri[a] + 1, b + 1, uvi[b] + 1, nri[b] + 1, c + 1, uvi[c] + 1, nri[c] + 1))
    return len(verts), len(m.F)


# ------------------------------------------------------------------------------------------------------------------------------ grids
def grid_mesh(P, keep=None, flip=False):
    """P (nu+1, nv+1, 3) grid of points; keep (nu, nv) bool mask of the cells to build (None = all). Winding: counter-clockwise seen from the side the (du x dv) normal points to."""
    nu, nv = P.shape[0] - 1, P.shape[1] - 1
    uu, vv = np.meshgrid(np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1), indexing='ij')
    UV = np.stack([uu, vv], -1).reshape(-1, 2)
    idx = np.arange((nu + 1) * (nv + 1)).reshape(nu + 1, nv + 1)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
    if keep is not None:
        k = np.asarray(keep, bool).reshape(-1)
        F = np.concatenate([F[:len(F) // 2][k], F[len(F) // 2:][k]])
    m = Mesh(P.reshape(-1, 3), UV, F)
    return m.flipped() if flip else m


def solidify(Po, Pi, keep=None, flip=False):
    """a closed shell from an outer and an inner grid: outer faces, inner faces (reversed) and rim strips on every boundary edge (outer border and hole borders).
    The outer grid's (du x dv) normal must point away from the inner grid."""
    nu, nv = Po.shape[0] - 1, Po.shape[1] - 1
    keep = np.ones((nu, nv), bool) if keep is None else np.asarray(keep, bool)
    outer = grid_mesh(Po, keep)
    inner = grid_mesh(Pi, keep).flipped()
    n_pts = (nu + 1) * (nv + 1)
    idx = np.arange(n_pts).reshape(nu + 1, nv + 1)
    # boundary edges: edges used by exactly one kept cell
    edges = {}
    for i in range(nu):
        for j in range(nv):
            if not keep[i, j]:
                continue
            for e in (((i, j), (i + 1, j)), ((i + 1, j), (i + 1, j + 1)), ((i + 1, j + 1), (i, j + 1)), ((i, j + 1), (i, j))):
                key = tuple(sorted(e))
                edges.setdefault(key, []).append(e)
    rim = []
    for key, lst in edges.items():
        if len(lst) == 1:
            (p, q) = lst[0]
            a, b = idx[p], idx[q]
            # cell edge (a -> b) is counter-clockwise around the cell seen from the outer normal side: the rim quad between outer and inner faces outward
            rim.append([a, n_pts + a, n_pts + b])
            rim.append([a, n_pts + b, b])
    V = np.vstack([Po.reshape(-1, 3), Pi.reshape(-1, 3)])
    UV = np.vstack([outer.UV, outer.UV])
    m = Mesh(V, UV, np.array(rim, int))
    # outer faces keep their indices, inner faces use the inner vertex block
    inner_f = inner.F + n_pts
    full = Mesh(V, UV, np.vstack([outer.F, inner_f, m.F]))
    return full.flipped() if flip else full


def orient_check(m):
    """True when the closed mesh is wound outward (positive volume)"""
    return m.signed_volume() >= 0


def fix_outward(m):
    return m if m.signed_volume() >= 0 else m.flipped()


# ------------------------------------------------------------------------------------------------------------------------------ sweeps
def path_frames(P, up_hint=(0, 0, 1.0)):
    """tangent, normal, binormal along a polyline (parallel transport)"""
    P = np.asarray(P, float)
    T = np.zeros_like(P)
    T[1:-1] = P[2:] - P[:-2]
    T[0] = P[1] - P[0]
    T[-1] = P[-1] - P[-2]
    T = unit(T)
    N = np.zeros_like(P)
    B = np.zeros_like(P)
    ref = np.asarray(up_hint, float)
    n0 = ref - T[0] * (ref @ T[0])
    if np.linalg.norm(n0) < 1e-6:
        n0 = np.cross(T[0], (1.0, 0, 0))
    N[0] = unit(n0)
    B[0] = np.cross(T[0], N[0])
    for i in range(1, len(P)):
        n = N[i - 1] - T[i] * (N[i - 1] @ T[i])
        if np.linalg.norm(n) < 1e-8:
            n = np.cross(T[i], B[i - 1])
        N[i] = unit(n)
        B[i] = np.cross(T[i], N[i])
    return T, N, B


def loft(path, section, scale=None, twist=None, cap_start=True, cap_end=True, up_hint=(0, 0, 1.0), uv_turns=1.0):
    """sweep a closed 2D section (S,2) along `path` (K,3).
    scale: scalar or (K,) or (K,2) per-station scale of the section (u along the frame normal, v along the binormal); twist: (K,) radians.
    The first section point is at +normal; the section runs counter-clockwise in (normal, binormal) seen along the tangent, which gives outward faces."""
    P = np.asarray(path, float)
    K = len(P)
    sec = np.asarray(section, float)
    S = len(sec)
    T, N, B = path_frames(P, up_hint)
    sc = np.ones((K, 2)) if scale is None else np.asarray(scale, float)
    if sc.ndim == 0:
        sc = np.full((K, 2), float(sc))
    elif sc.ndim == 1:
        sc = np.stack([sc, sc], 1)
    tw = np.zeros(K) if twist is None else np.asarray(twist, float)
    ring = np.zeros((K, S, 3))
    for i in range(K):
        c, s = np.cos(tw[i]), np.sin(tw[i])
        u = sec[:, 0] * c - sec[:, 1] * s
        v = sec[:, 0] * s + sec[:, 1] * c
        ring[i] = P[i] + (u * sc[i, 0])[:, None] * N[i] + (v * sc[i, 1])[:, None] * B[i]
    # close the ring by repeating the first point for UV seams
    ringc = np.concatenate([ring, ring[:, :1]], axis=1)
    V = ringc.reshape(-1, 3)
    uu = np.repeat(np.linspace(0, 1, K)[:, None], S + 1, axis=1)
    vv = np.tile(np.linspace(0, uv_turns, S + 1), (K, 1))
    UV = np.stack([uu, vv], -1).reshape(-1, 2)
    idx = np.arange(K * (S + 1)).reshape(K, S + 1)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
    m = Mesh(V, UV, F)
    # outward test: side normals against the direction from the path point
    v0 = V[F[:, 0]]
    fn = np.cross(V[F[:, 1]] - v0, V[F[:, 2]] - v0)
    rad = v0 - P[F[:, 0] // (S + 1)]
    if np.einsum('ij,ij->', fn, rad) < 0:
        m = m.flipped()
    for end, direction, wanted in ((0, -T[0], cap_start), (K - 1, T[-1], cap_end)):
        if not wanted:
            continue
        ringp = ring[end]
        Vc = np.vstack([P[end], ringp])
        Fc = np.array([[0, 1 + i, 1 + (i + 1) % S] for i in range(S)])
        n = np.cross(Vc[Fc[:, 1]] - Vc[Fc[:, 0]], Vc[Fc[:, 2]] - Vc[Fc[:, 0]])
        if (n @ direction).sum() < 0:
            Fc = Fc[:, ::-1]
        m.add(Mesh(Vc, np.zeros((len(Vc), 2)), Fc))
    return m


def circle(n=16, rx=1.0, ry=1.0):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.stack([np.cos(t) * rx, np.sin(t) * ry], 1)


def rounded_square(n=16, w=1.0, h=1.0, p=4.0):
    """superellipse section (p=2 ellipse, large p boxy)"""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    return np.stack([np.sign(c) * np.abs(c) ** (2 / p) * w, np.sign(s) * np.abs(s) ** (2 / p) * h], 1)


def bezier(pts, n=40):
    """de Casteljau curve through control points (any degree)"""
    P = np.asarray(pts, float)
    out = []
    for t in np.linspace(0, 1, n):
        Q = P.copy()
        while len(Q) > 1:
            Q = (1 - t) * Q[:-1] + t * Q[1:]
        out.append(Q[0])
    return np.array(out)


def catmull(points, n=40):
    from ethics_acc import smooth_path
    return smooth_path(np.asarray(points, float), n)


# ------------------------------------------------------------------------------------------------------------------------------ primitives
def box(size, rc=0.0, seg=3):
    """axis-aligned box centred at the origin (rc > 0 bevels the edges with a superellipse look)"""
    sx, sy, sz = [s / 2.0 for s in size]
    if rc <= 0:
        V = np.array([[x, y, z] for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)], float)
        F = []
        quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for q in quads:
            F += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
        return fix_outward(Mesh(V, np.zeros((8, 2)), np.array(F)))
    return fix_outward(mg.surface(lambda U, W: _superbox(U, W, sx, sy, sz, rc), 24, 12))


def _superbox(U, W, sx, sy, sz, rc):
    th = 2 * np.pi * U
    ph = np.pi * W - np.pi / 2
    e = max(0.15, min(1.0, rc / max(min(sx, sy, sz), 1e-3)))
    p = 2.0 / e
    def sp(a, k):
        return np.sign(a) * np.abs(a) ** k
    x = sx * sp(np.cos(ph), 2 / p) * sp(np.cos(th), 2 / p)
    y = sy * sp(np.cos(ph), 2 / p) * sp(np.sin(th), 2 / p)
    z = sz * sp(np.sin(ph), 2 / p)
    return np.stack([x, y, z], -1)


def cone(r0, r1, h, sides=16, cap=True):
    """frustum along +z from z=0 (radius r0) to z=h (radius r1)"""
    path = np.array([[0, 0, 0], [0, 0, h]], float)
    return loft(path, circle(sides), scale=np.array([r0, r1]), cap_start=cap, cap_end=cap)


def spike(path, r0, sides=12, power=1.0, ridges=0, ridge_amp=0.0):
    """a tapered curved spike (horn / fang / thorn): radius r0 at the base down to a point; optional spiral ridges"""
    K = len(path)
    s = np.linspace(0, 1, K)
    rad = r0 * (1 - s) ** power
    rad[-1] = max(rad[-1], 1e-3)
    if ridges:
        t = np.linspace(0, 2 * np.pi, sides, endpoint=False)
        sec = np.stack([np.cos(t), np.sin(t)], 1) * (1 + ridge_amp * np.cos(t * ridges))[:, None]
    else:
        sec = circle(sides)
    tw = s * 2.2 if ridges else None
    return loft(path, sec, scale=rad, twist=tw, cap_start=True, cap_end=True)


def blade(path, widths, thickness=0.12, up_hint=(0, 1.0, 0)):
    """a flat tapered blade / feather along a path: widths (K,) across the up_hint-perpendicular direction, thin solid"""
    P = np.asarray(path, float)
    K = len(P)
    T, N, B = path_frames(P, up_hint)
    w = np.asarray(widths, float)
    sec = np.array([[1, 0.0], [0.0, 1.0], [-1, 0.0], [0.0, -1.0]])
    sc = np.stack([w / 2.0, np.full(K, thickness / 2.0)], 1)
    return loft(P, sec, scale=sc, up_hint=up_hint)


def hex_prism(c, radius, h, normal=(0, 0, 1)):
    """a hexagonal prism centred at c with axis `normal`"""
    n = unit(normal)
    ref = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = unit(np.cross(n, ref))
    v = np.cross(n, u)
    R = np.stack([u, v, n], 1)
    m = loft(np.array([[0, 0, -h / 2], [0, 0, h / 2]]), circle(6, radius, radius), cap_start=True, cap_end=True)
    return m.transform(R=R, t=c)


def disc(r, n=32, z=0.0, thick=0.0):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.column_stack([np.cos(ang) * r, np.sin(ang) * r, np.full(n, z)])
    V = np.vstack([[0, 0, z], ring])
    F = np.array([[0, 1 + i, 1 + (i + 1) % n] for i in range(n)])
    return Mesh(V, np.zeros((len(V), 2)), F)


# ------------------------------------------------------------------------------------------------------------------------------ distance field of a surface from a centre
class Radial:
    """r(theta, phi): distance from `centre` to a (head-like) surface along rays; theta = elevation (-90..90 deg), phi = azimuth from +x towards +y.
    Smoothed bilinear lookup, so offset shells follow the surface without its triangle noise."""

    def __init__(self, surface, centre, n_theta=73, n_phi=145, smooth=2, rmax=30.0):
        self.c = np.asarray(centre, float)
        self.th = np.radians(np.linspace(-90, 90, n_theta))
        self.ph = np.radians(np.linspace(-180, 180, n_phi))
        R = np.full((n_theta, n_phi), np.nan)
        for i, t in enumerate(self.th):
            for j, p in enumerate(self.ph):
                d = np.array([np.cos(t) * np.cos(p), np.cos(t) * np.sin(p), np.sin(t)])
                hit = surface.cast(self.c, d, tmax=rmax)
                if hit is not None:
                    R[i, j] = hit[0]
        # fill misses from neighbours, then smooth
        for _ in range(6):
            miss = np.isnan(R)
            if not miss.any():
                break
            Rp = np.pad(R, 1, mode='edge')
            nb = np.stack([Rp[:-2, 1:-1], Rp[2:, 1:-1], Rp[1:-1, :-2], Rp[1:-1, 2:]])
            fill = np.nanmean(nb, axis=0)
            R = np.where(miss, fill, R)
        R = np.where(np.isnan(R), np.nanmean(R), R)
        for _ in range(smooth):
            Rp = np.pad(R, ((1, 1), (0, 0)), mode='edge')
            Rp = np.concatenate([Rp[:, -1:], Rp, Rp[:, :1]], axis=1)
            R = (Rp[1:-1, 1:-1] * 4 + Rp[:-2, 1:-1] + Rp[2:, 1:-1] + Rp[1:-1, :-2] + Rp[1:-1, 2:]) / 8.0
        self.R = R

    def r(self, theta, phi):
        t = np.clip(np.asarray(theta, float), -np.pi / 2, np.pi / 2)
        p = (np.asarray(phi, float) + np.pi) % (2 * np.pi) - np.pi
        ti = (t - self.th[0]) / (self.th[1] - self.th[0])
        pi_ = (p - self.ph[0]) / (self.ph[1] - self.ph[0])
        t0 = np.clip(np.floor(ti).astype(int), 0, len(self.th) - 2)
        p0 = np.clip(np.floor(pi_).astype(int), 0, len(self.ph) - 2)
        ft, fp = ti - t0, pi_ - p0
        R = self.R
        return (R[t0, p0] * (1 - ft) * (1 - fp) + R[t0 + 1, p0] * ft * (1 - fp) + R[t0, p0 + 1] * (1 - ft) * fp + R[t0 + 1, p0 + 1] * ft * fp)

    def point(self, theta, phi, off=0.0):
        th, ph = np.asarray(theta, float), np.asarray(phi, float)
        d = np.stack([np.cos(th) * np.cos(ph), np.cos(th) * np.sin(ph), np.sin(th)], -1)
        r = self.r(th, ph) + off
        return self.c + d * r[..., None]

    def dir(self, theta, phi):
        th, ph = np.asarray(theta, float), np.asarray(phi, float)
        return np.stack([np.cos(th) * np.cos(ph), np.cos(th) * np.sin(ph), np.sin(th)], -1)

    def angles_of(self, p):
        """(theta, phi) of the direction from the centre to a world point"""
        d = unit(np.asarray(p, float) - self.c)
        return np.arcsin(np.clip(d[..., 2], -1, 1)), np.arctan2(d[..., 1], d[..., 0])


class Cyl:
    """r(z, phi): horizontal distance from a vertical axis (x0, y0) to the surface, for every height z and azimuth phi (from +x towards +y); smoothed bilinear lookup"""

    def __init__(self, surface, axis_xy, z0, z1, n_z=61, n_phi=145, smooth=2, rmax=30.0):
        self.a = np.asarray(axis_xy, float)
        self.z = np.linspace(z0, z1, n_z)
        self.ph = np.radians(np.linspace(-180, 180, n_phi))
        R = np.full((n_z, n_phi), np.nan)
        for i, z in enumerate(self.z):
            for j, p in enumerate(self.ph):
                d = np.array([np.cos(p), np.sin(p), 0.0])
                hit = surface.cast(np.array([self.a[0], self.a[1], z]), d, tmax=rmax)
                if hit is not None:
                    R[i, j] = hit[0]
        for _ in range(8):
            miss = np.isnan(R)
            if not miss.any():
                break
            Rp = np.pad(R, 1, mode='edge')
            nb = np.stack([Rp[:-2, 1:-1], Rp[2:, 1:-1], Rp[1:-1, :-2], Rp[1:-1, 2:]])
            R = np.where(miss, np.nanmean(nb, axis=0), R)
        R = np.where(np.isnan(R), np.nanmean(R), R)
        for _ in range(smooth):
            Rp = np.pad(R, ((1, 1), (0, 0)), mode='edge')
            Rp = np.concatenate([Rp[:, -1:], Rp, Rp[:, :1]], axis=1)
            R = (Rp[1:-1, 1:-1] * 4 + Rp[:-2, 1:-1] + Rp[2:, 1:-1] + Rp[1:-1, :-2] + Rp[1:-1, 2:]) / 8.0
        self.R = R

    def dilated(self, k):
        """a copy whose radius is the local maximum over +-k grid cells (so offset surfaces clear narrow protrusions such as lips and nostrils)"""
        import copy
        c = copy.copy(self)
        R = self.R
        out = R.copy()
        for dz in range(-k, k + 1):
            Rz = np.roll(R, dz, axis=0)
            if dz > 0:
                Rz[:dz] = R[:1]
            elif dz < 0:
                Rz[dz:] = R[-1:]
            for dp in range(-k, k + 1):
                out = np.maximum(out, np.roll(Rz, dp, axis=1))
        c.R = out
        return c

    def smoothed(self, passes):
        """a copy of this surface with `passes` extra smoothing passes (a gentler skull for panels whose offsets must not flare on steep flanks)"""
        import copy
        c = copy.copy(self)
        R = self.R.copy()
        for _ in range(passes):
            Rp = np.pad(R, ((1, 1), (0, 0)), mode='edge')
            Rp = np.concatenate([Rp[:, -1:], Rp, Rp[:, :1]], axis=1)
            R = (Rp[1:-1, 1:-1] * 4 + Rp[:-2, 1:-1] + Rp[2:, 1:-1] + Rp[1:-1, :-2] + Rp[1:-1, 2:]) / 8.0
        c.R = R
        return c

    def r(self, z, phi):
        zc = np.clip(np.asarray(z, float), self.z[0], self.z[-1])
        p = (np.asarray(phi, float) + np.pi) % (2 * np.pi) - np.pi
        zi = (zc - self.z[0]) / (self.z[1] - self.z[0])
        pi_ = (p - self.ph[0]) / (self.ph[1] - self.ph[0])
        z0 = np.clip(np.floor(zi).astype(int), 0, len(self.z) - 2)
        p0 = np.clip(np.floor(pi_).astype(int), 0, len(self.ph) - 2)
        fz, fp = zi - z0, pi_ - p0
        R = self.R
        return (R[z0, p0] * (1 - fz) * (1 - fp) + R[z0 + 1, p0] * fz * (1 - fp) + R[z0, p0 + 1] * (1 - fz) * fp + R[z0 + 1, p0 + 1] * fz * fp)

    def point(self, z, phi, off=0.0):
        z, phi = np.broadcast_arrays(np.asarray(z, float), np.asarray(phi, float))
        r = self.r(z, phi) + off
        return np.stack([self.a[0] + np.cos(phi) * r, self.a[1] + np.sin(phi) * r, z], -1)

    def normal(self, z, phi, eps=0.35):
        """outward surface normal of the smoothed surface (from finite differences)"""
        z, phi = np.broadcast_arrays(np.asarray(z, float), np.asarray(phi, float))
        r0 = self.r(z, phi)
        dz = (self.r(z + eps, phi) - self.r(z - eps, phi)) / (2 * eps)
        dp = (self.r(z, phi + 0.02) - self.r(z, phi - 0.02)) / 0.04
        er = np.stack([np.cos(phi), np.sin(phi), np.zeros_like(phi)], -1)
        et = np.stack([-np.sin(phi), np.cos(phi), np.zeros_like(phi)], -1)
        # surface S(z, phi) = a + r er + z ez ; tangents: S_z = dz er + ez ; S_phi = dp er + r et
        Sz = dz[..., None] * er + np.array([0, 0, 1.0])
        Sp = dp[..., None] * er + r0[..., None] * et
        n = np.cross(Sp, Sz)
        n = unit(n)
        flip = (n * er).sum(-1, keepdims=True) < 0
        return np.where(flip, -n, n)


# ------------------------------------------------------------------------------------------------------------------------------ pieces that follow a surface
def cyl_at_yz(cyl, y, z, off=0.0):
    """point and outward normal of a Cyl surface at given lateral y and height z (y measured from the axis plane), offset along the normal"""
    y = np.asarray(y, float)
    z = np.asarray(z, float)
    ph = np.arctan2(y, 4.0) * np.ones_like(z)
    for _ in range(4):
        r = cyl.r(z, ph)
        ph = np.arcsin(np.clip((y - cyl.a[1]) / np.maximum(r, 1e-6), -0.999, 0.999))
    n = cyl.normal(z, ph)
    p = cyl.point(z, ph, 0.0) + n * off
    return p, n


def strip_solid(points, normals, width, thick, cap=True):
    """a prism strip following a polyline lying on a surface: width across the surface (perpendicular to the path), thick along the surface normal (centred on the points).
    width / thick: scalar or (K,)"""
    P = np.asarray(points, float)
    K = len(P)
    Nn = unit(np.asarray(normals, float))
    T = np.zeros_like(P)
    T[1:-1] = P[2:] - P[:-2]
    T[0] = P[1] - P[0]
    T[-1] = P[-1] - P[-2]
    T = unit(T)
    B = unit(np.cross(T, Nn))
    N2 = unit(np.cross(B, T))
    w = np.full(K, float(width)) if np.isscalar(width) else np.asarray(width, float)
    t = np.full(K, float(thick)) if np.isscalar(thick) else np.asarray(thick, float)
    corners = [(+1, +1), (-1, +1), (-1, -1), (+1, -1)]        # counter-clockwise seen along +T when B is "right" and N2 "up"
    ring = np.stack([P + b * (w / 2)[:, None] * B + nn * (t / 2)[:, None] * N2 for b, nn in corners], axis=1)   # (K, 4, 3)
    V = ring.reshape(-1, 3)
    idx = np.arange(K * 4).reshape(K, 4)
    F = []
    for i in range(K - 1):
        for j in range(4):
            a, b2 = idx[i, j], idx[i, (j + 1) % 4]
            c, d = idx[i + 1, (j + 1) % 4], idx[i + 1, j]
            F += [[a, b2, c], [a, c, d]]
    m = Mesh(V, np.zeros((len(V), 2)), np.array(F, int))
    if cap:
        for end, direction in ((0, -T[0]), (K - 1, T[-1])):
            Vc = np.vstack([P[end], ring[end]])
            Fc = np.array([[0, 1 + j, 1 + (j + 1) % 4] for j in range(4)])
            n = np.cross(Vc[Fc[:, 1]] - Vc[Fc[:, 0]], Vc[Fc[:, 2]] - Vc[Fc[:, 0]])
            if (n @ direction).sum() < 0:
                Fc = Fc[:, ::-1]
            m.add(Mesh(Vc, np.zeros((len(Vc), 2)), Fc))
    # outward orientation of the side faces
    v0 = m.V[m.F[:, 0]]
    fn = np.cross(m.V[m.F[:, 1]] - v0, m.V[m.F[:, 2]] - v0)
    cen = np.repeat(P, 4, axis=0)
    ok = np.einsum('ij,ij->', fn[:K * 8 - 8] if len(fn) >= K * 8 - 8 else fn, (v0 - cen[np.minimum(m.F[:, 0], len(cen) - 1)])[:K * 8 - 8] if len(fn) >= K * 8 - 8 else (v0 - cen[:len(fn)]))
    return m.flipped() if ok < 0 else m


def tube_path(points, radius, sides=10, cap=True):
    """round tube through points with constant or per-station radius"""
    P = np.asarray(points, float)
    r = np.full(len(P), float(radius)) if np.isscalar(radius) else np.asarray(radius, float)
    return loft(P, circle(sides), scale=r, cap_start=cap, cap_end=cap)


def teeth_row(base_pts, base_normals, length, width, curve=0.0, sides=6, lean=(0, 0, 0)):
    """small cones standing on the surface at given points along the normals (length scalar or (K,))"""
    L = np.full(len(base_pts), float(length)) if np.isscalar(length) else np.asarray(length, float)
    out = []
    for p, n, l in zip(base_pts, base_normals, L):
        n = unit(n + np.asarray(lean, float))
        path = np.array([p, p + n * l * 0.5 + curve * l * 0.15 * np.array([0, 0, 0]), p + n * l])
        out.append(spike(path, width, sides=sides, power=1.0))
    return merge(out)
