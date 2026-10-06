"""Small procedural-mesh toolkit for pac3 urlobj props (own geometry, written as OBJ with vertex normals) plus a z-buffer preview renderer.

Frame contract: OBJ coordinates are the pac model2 local frame (the urlobj loader reads `v x y z` verbatim). Faces are written CCW when seen from outside;
pac reverses the winding, which makes them front facing in Source. Vertex normals (`vn`) are always written so lighting works.
"""
import math
import numpy as np


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


class Mesh:
    def __init__(self):
        self.V = []
        self.N = []
        self.F = []

    # -- primitives ---------------------------------------------------------------------------------------------------------------------
    def _add(self, verts, norms, faces):
        o = len(self.V)
        self.V.extend(verts)
        self.N.extend(norms)
        for a, b, c in faces:
            va, vb, vc = verts[a], verts[b], verts[c]
            tri = np.cross(vb - va, vc - va)
            ref = norms[a] + norms[b] + norms[c]
            if np.dot(tri, ref) < 0:
                b, c = c, b
            self.F.append((o + a, o + b, o + c))

    def add_tube(self, pts, radii, sides=14, cap_start=True, cap_end=True, up=(0.0, 0.0, 1.0)):
        """Sweep a circle along a polyline (parallel-transport frames). radii: scalar or one value per point."""
        pts = [np.asarray(p, float) for p in pts]
        n = len(pts)
        radii = [float(radii)] * n if np.isscalar(radii) else [float(r) for r in radii]
        T = []
        for i in range(n):
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, n - 1)]
            T.append(_unit(b - a))
        up = np.asarray(up, float)
        N0 = up - np.dot(up, T[0]) * T[0]
        if np.linalg.norm(N0) < 1e-6:
            N0 = np.array([1.0, 0.0, 0.0]) - np.dot([1.0, 0.0, 0.0], T[0]) * T[0]
        Ns = [_unit(N0)]
        for i in range(1, n):
            Nn = Ns[-1] - np.dot(Ns[-1], T[i]) * T[i]
            Ns.append(_unit(Nn))
        verts, norms, faces = [], [], []
        for i in range(n):
            B = np.cross(T[i], Ns[i])
            # slope of the radius along the axis tilts the normals (matters for the bell)
            dr = 0.0
            if 0 < i < n - 1:
                ds = np.linalg.norm(pts[i + 1] - pts[i - 1])
                dr = (radii[i + 1] - radii[i - 1]) / ds if ds > 1e-9 else 0.0
            elif n > 1:
                j0, j1 = (0, 1) if i == 0 else (n - 2, n - 1)
                ds = np.linalg.norm(pts[j1] - pts[j0])
                dr = (radii[j1] - radii[j0]) / ds if ds > 1e-9 else 0.0
            for k in range(sides):
                th = 2 * math.pi * k / sides
                d = math.cos(th) * Ns[i] + math.sin(th) * B
                verts.append(pts[i] + radii[i] * d)
                norms.append(_unit(d - dr * T[i]))
        for i in range(n - 1):
            for k in range(sides):
                a = i * sides + k
                b = i * sides + (k + 1) % sides
                c = (i + 1) * sides + (k + 1) % sides
                d = (i + 1) * sides + k
                faces.append((a, b, c))
                faces.append((a, c, d))
        self._add(verts, norms, faces)
        for flag, idx, sign in ((cap_start, 0, -1.0), (cap_end, n - 1, 1.0)):
            if not flag or radii[idx] <= 1e-6:
                continue
            B = np.cross(T[idx], Ns[idx])
            nrm = sign * T[idx]
            cv = [pts[idx]]
            cn = [nrm]
            for k in range(sides):
                th = 2 * math.pi * k / sides
                cv.append(pts[idx] + radii[idx] * (math.cos(th) * Ns[idx] + math.sin(th) * B))
                cn.append(nrm)
            cf = [(0, 1 + k, 1 + (k + 1) % sides) for k in range(sides)]
            self._add(cv, cn, cf)

    def add_torus(self, center, axis, R, r, seg_big=48, seg_small=10):
        """Ring (hoop): major radius R around `axis`, tube radius r."""
        axis = _unit(np.asarray(axis, float))
        a = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1 = _unit(np.cross(axis, a))
        e2 = np.cross(axis, e1)
        center = np.asarray(center, float)
        verts, norms, faces = [], [], []
        for i in range(seg_big):
            u = 2 * math.pi * i / seg_big
            radial = math.cos(u) * e1 + math.sin(u) * e2
            for j in range(seg_small):
                v = 2 * math.pi * j / seg_small
                nrm = math.cos(v) * radial + math.sin(v) * axis
                verts.append(center + R * radial + r * nrm)
                norms.append(nrm)
        for i in range(seg_big):
            for j in range(seg_small):
                a_ = i * seg_small + j
                b_ = i * seg_small + (j + 1) % seg_small
                c_ = ((i + 1) % seg_big) * seg_small + (j + 1) % seg_small
                d_ = ((i + 1) % seg_big) * seg_small + j
                faces.append((a_, b_, c_))
                faces.append((a_, c_, d_))
        self._add(verts, norms, faces)

    def add_sphere(self, center, radius, seg=18):
        center = np.asarray(center, float)
        verts, norms, faces = [], [], []
        for i in range(seg + 1):
            ph = math.pi * i / seg
            for j in range(seg * 2):
                th = 2 * math.pi * j / (seg * 2)
                d = np.array([math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph)])
                verts.append(center + radius * d)
                norms.append(d)
        W = seg * 2
        for i in range(seg):
            for j in range(W):
                a, b = i * W + j, i * W + (j + 1) % W
                c, d = (i + 1) * W + (j + 1) % W, (i + 1) * W + j
                faces.append((a, b, c))
                faces.append((a, c, d))
        self._add(verts, norms, faces)

    # -- output -------------------------------------------------------------------------------------------------------------------------
    def arrays(self):
        return np.array(self.V), np.array(self.N), np.array(self.F, dtype=int)

    def write_obj(self, path, name='prop', comment=None):
        V, N, F = self.arrays()
        with open(path, 'w', newline='\n') as f:
            f.write('# claude skill made by ax0rz0\n')
            if comment:
                f.write('# %s\n' % comment)
            f.write('# %d vertices, %d triangles (own procedural geometry)\no %s\n' % (len(V), len(F), name))
            for v in V:
                f.write('v %.4f %.4f %.4f\n' % tuple(v))
            for n in N:
                f.write('vn %.4f %.4f %.4f\n' % tuple(n))
            for a, b, c in F:
                f.write('f %d//%d %d//%d %d//%d\n' % (a + 1, a + 1, b + 1, b + 1, c + 1, c + 1))
        return len(V), len(F)


# ---------------------------------------------------------------- path helpers
def line(p0, p1, n):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    return [p0 + (p1 - p0) * i / n for i in range(n + 1)]


def arc_xz(cx, cz, r, a0, a1, y0, y1, n):
    """Arc in the plane parallel to XZ: x = cx + r cos a, z = cz + r sin a (degrees), y blended from y0 to y1."""
    out = []
    for i in range(n + 1):
        t = i / n
        a = math.radians(a0 + (a1 - a0) * t)
        out.append(np.array([cx + r * math.cos(a), y0 + (y1 - y0) * t, cz + r * math.sin(a)]))
    return out


def join(*segments):
    pts = []
    for seg in segments:
        for p in seg:
            if not pts or np.linalg.norm(p - pts[-1]) > 1e-6:
                pts.append(p)
    return pts


# ---------------------------------------------------------------- the trumpet (ActMod prop space: long axis X, mouthpiece +X, bell -X, valves point +Z)
def trumpet():
    m = Mesh()
    zt, zb = 3.38, 1.0                      # upper / lower run heights (measured on the reference prop)
    ry = 0.47                               # leadpipe lane; the mouthpiece sits here
    rr = (zt - zb) / 2.0                    # bend radius
    cz = (zt + zb) / 2.0
    R_TUBE = 0.27
    # main tubing: mouthpiece rim -> leadpipe -> U bend -> lower run -> U bend -> bell run
    mouth = line((8.65, ry, zt), (7.4, ry, zt), 6)
    lead = line((7.4, ry, zt), (-4.2, ry, zt), 40)
    bend1 = arc_xz(-4.2, cz, rr, 90, 270, ry, -0.10, 24)
    run2 = line((-4.2, -0.10, zb), (5.6, -0.10, zb), 36)
    bend2 = arc_xz(5.6, cz, rr, -90, 90, -0.10, -0.67, 24)
    run3 = line((5.6, -0.67, zt), (-7.0, -0.67, zt), 44)
    pts = join(mouth, lead, bend1, run2, bend2, run3)
    # radius profile along the path: mouthpiece cup flares at the +X end
    rad = []
    for p in pts:
        r = R_TUBE
        if p[0] > 7.3 and abs(p[1] - ry) < 0.01 and abs(p[2] - zt) < 0.01:
            u = (p[0] - 7.3) / (8.65 - 7.3)
            r = R_TUBE + (0.66 - R_TUBE) * (u ** 1.6)
        rad.append(r)
    m.add_tube(pts, rad, sides=14, cap_start=True, cap_end=False, up=(0, 0, 1))
    # bell: horn flare from the end of run 3
    bell_pts = [np.array([-7.0 - 1.7 * i / 22.0, -0.67, zt]) for i in range(23)]
    bell_rad = [R_TUBE + (1.96 - R_TUBE) * ((i / 22.0) ** 2.4) for i in range(23)]
    m.add_tube(bell_pts, bell_rad, sides=22, cap_start=False, cap_end=False, up=(0, 0, 1))
    lip = [np.array([-8.7, -0.67, zt]), np.array([-8.58, -0.67, zt])]       # rolled lip: a short fat ring
    m.add_tube(lip, [1.99, 1.99], sides=22, cap_start=False, cap_end=False)
    # three piston valves (casing, caps, buttons)
    for vx in (-0.06, 0.76, 1.58):
        vy = -0.05
        m.add_tube([(vx, vy, 0.0), (vx, vy, 4.18)], [0.40, 0.40], sides=16, cap_start=True, cap_end=True)
        m.add_tube([(vx, vy, 4.18), (vx, vy, 4.36)], [0.47, 0.47], sides=16, cap_start=False, cap_end=True)
        m.add_tube([(vx, vy, 4.36), (vx, vy, 4.63)], [0.2, 0.2], sides=10, cap_start=False, cap_end=True)
        m.add_tube([(vx, vy, -0.09), (vx, vy, 0.2)], [0.46, 0.46], sides=16, cap_start=True, cap_end=False)
    # water key (little lever) on the upper bend and a finger hook, for the silhouette
    m.add_tube([(-4.2, ry, zt + 0.1), (-4.2, ry, zt + 0.9)], [0.12, 0.12], sides=8, cap_start=False, cap_end=True)
    return m


# ---------------------------------------------------------------- preview renderer (orthographic z-buffer, Lambert + a cheap metal highlight)
def render(mesh, view_dir, up=(0, 0, 1), size=480, margin=1.12, color=(0.95, 0.74, 0.22), light=(0.5, -0.6, 0.8), bg=(30, 34, 44)):
    V, N, F = mesh.arrays()
    w = _unit(np.asarray(view_dir, float))                 # direction from the scene to the camera
    r = _unit(np.cross(np.asarray(up, float), w))
    u = np.cross(w, r)
    P = np.stack([V @ r, V @ u, V @ w], axis=1)
    lo, hi = P[:, :2].min(axis=0), P[:, :2].max(axis=0)
    ext = (hi - lo).max() * margin
    scale = size / ext
    mid = (lo + hi) / 2
    sx = (P[:, 0] - mid[0]) * scale + size / 2
    sy = size / 2 - (P[:, 1] - mid[1]) * scale
    sz = P[:, 2]
    img = np.zeros((size, size, 3), float)
    img[:] = np.array(bg) / 255.0
    zbuf = np.full((size, size), -1e9)
    L = _unit(np.asarray(light, float))
    L = L[0] * r + L[1] * u + L[2] * w                      # light in camera space
    Nc = np.stack([N @ r, N @ u, N @ w], axis=1)
    for a, b, c in F:
        pa, pb, pc = (sx[a], sy[a]), (sx[b], sy[b]), (sx[c], sy[c])
        area = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        if abs(area) < 1e-9:
            continue
        x0, x1 = int(max(min(pa[0], pb[0], pc[0]), 0)), int(min(max(pa[0], pb[0], pc[0]) + 1, size - 1))
        y0, y1 = int(max(min(pa[1], pb[1], pc[1]), 0)), int(min(max(pa[1], pb[1], pc[1]) + 1, size - 1))
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((pb[0] - xs) * (pc[1] - ys) - (pb[1] - ys) * (pc[0] - xs)) / area
        w1 = ((pc[0] - xs) * (pa[1] - ys) - (pc[1] - ys) * (pa[0] - xs)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        z = w0 * sz[a] + w1 * sz[b] + w2 * sz[c]
        nrm = w0[..., None] * Nc[a] + w1[..., None] * Nc[b] + w2[..., None] * Nc[c]
        nl = np.linalg.norm(nrm, axis=2, keepdims=True)
        nrm = nrm / np.maximum(nl, 1e-9)
        diff = np.clip((nrm * L).sum(axis=2), 0, 1)
        refl = 2 * (nrm * L).sum(axis=2, keepdims=True) * nrm - L
        spec = np.clip(refl[..., 2], 0, 1) ** 24
        shade = 0.30 + 0.62 * diff
        col = np.array(color)[None, None, :] * shade[..., None] + 0.55 * spec[..., None]
        yy, xx = np.nonzero(inside)
        zz = z[inside]
        ok = zz > zbuf[y0 + yy, x0 + xx]
        yy, xx, zz = yy[ok], xx[ok], zz[ok]
        zbuf[y0 + yy, x0 + xx] = zz
        img[y0 + yy, x0 + xx] = np.clip(col[yy + 0, xx + 0] if False else col[inside][ok], 0, 1)
    return (img * 255).astype(np.uint8)


# ---------------------------------------------------------------- hoop / orb meshes for I'm a Mystery (axis = local Z)
RING_RADIUS = 9.5


def ring_mesh(R=RING_RADIUS, r=0.42, seg_big=72, seg_small=10):
    m = Mesh()
    m.add_torus((0, 0, 0), (0, 0, 1), R, r, seg_big=seg_big, seg_small=seg_small)
    return m


def ring_glow_mesh(R=RING_RADIUS, r=1.5, seg_big=72, seg_small=10):
    """the same hoop with a fat tube: drawn translucent behind the core ring as a soft halo"""
    return ring_mesh(R, r, seg_big, seg_small)


def orb_mesh(radius=2.2, seg=14):
    m = Mesh()
    m.add_sphere((0, 0, 0), radius, seg=seg)
    return m


# ---------------------------------------------------------------- the repo's obj/props/*.obj (python tools/emote/prop_geom.py [OUT_DIR], run from the repo root)
PROPS = (('trumpet.obj', 'trumpet', 'gold trumpet in the ActMod CanineCronutMix prop frame: long axis X, mouthpiece +X, bell -X, valves +Z (attach to the left carrier bone)', trumpet),
         ('hoop.obj', 'hoop', 'glowing hoop, radius 9.5, tube 0.42, axis = local Z (core)', ring_mesh),
         ('hoop_glow.obj', 'hoop_glow', 'same hoop with a fat tube (1.5) for the translucent halo', ring_glow_mesh))


if __name__ == '__main__':
    import os
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join('obj', 'props')
    os.makedirs(out, exist_ok=True)
    for fname, name, comment, make in PROPS:
        nv, nf = make().write_obj(os.path.join(out, fname), name, comment)
        print('%-14s %5d vertices %5d triangles' % (fname, nv, nf))
