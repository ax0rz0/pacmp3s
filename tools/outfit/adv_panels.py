"""Hard-surface panels that follow a surface: raised plates with filleted / chamfered edges, grooves, bolts, vents.

A "surface" maps 2D layout coordinates (u, v) plus an offset along the normal to a 3D point and its outward normal:
    surf.pt(u, v, off) -> (P (..., 3), N (..., 3))          u, v, off broadcastable arrays
Panels are designed as 2D polygons in (u, v) (the face unwrapped like a map), then draped over the surface:
    plateau(surf, poly, off0, off1, bevel)  one raised plate: flush with the layer below (off0) at its rim, off1 on top, fillet / chamfer between
    ribbon(surf, line, width, thick, off)  a thin strip along a polyline (grooves, LED seams, trim)
    polygon helpers: cut_poly (chamfer corners), round_poly (round corners), mirror_poly, offset helpers
"""
import numpy as np

import adv_geom as ag
from meshgen import Mesh

EPS = 1e-9


# ------------------------------------------------------------------------------------------------------------------------------ 2D polygon helpers
def densify_closed(poly, step):
    poly = np.asarray(poly, float)
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        k = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        for j in range(k):
            out.append(a + (b - a) * (j / k))
    return np.array(out)


def densify_open(line, step):
    line = np.asarray(line, float)
    out = []
    for i in range(len(line) - 1):
        a, b = line[i], line[i + 1]
        k = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        for j in range(k):
            out.append(a + (b - a) * (j / k))
    out.append(line[-1])
    return np.array(out)


def poly_centroid(p):
    p = np.asarray(p, float)
    x, y = p[:, 0], p[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    a = cr.sum() / 2.0
    if abs(a) < 1e-9:
        return p.mean(0)
    return np.array([((x + x1) * cr).sum(), ((y + y1) * cr).sum()]) / (6 * a)


def poly_area(p):
    p = np.asarray(p, float)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float((x * np.roll(y, -1) - np.roll(x, -1) * y).sum())


def cut_poly(poly, c):
    """chamfer every corner by distance c (scalar or per vertex) along both edges"""
    poly = np.asarray(poly, float)
    n = len(poly)
    out = []
    for i in range(n):
        p, a, b = poly[i], poly[i - 1], poly[(i + 1) % n]
        ci = float(c[i]) if np.ndim(c) else float(c)
        da, db = a - p, b - p
        la, lb = np.linalg.norm(da), np.linalg.norm(db)
        ci = min(ci, 0.46 * la, 0.46 * lb)
        if ci < 1e-6:
            out.append(p)
            continue
        out.append(p + da / la * ci)
        out.append(p + db / lb * ci)
    return np.array(out)


def round_poly(poly, r, seg=5):
    """round every corner: a quadratic Bezier from the point r before the corner to the point r after it"""
    poly = np.asarray(poly, float)
    n = len(poly)
    out = []
    for i in range(n):
        p, a, b = poly[i], poly[i - 1], poly[(i + 1) % n]
        ri = float(r[i]) if np.ndim(r) else float(r)
        da, db = a - p, b - p
        la, lb = np.linalg.norm(da), np.linalg.norm(db)
        ri = min(ri, 0.46 * la, 0.46 * lb)
        if ri < 1e-6:
            out.append(p)
            continue
        A, B = p + da / la * ri, p + db / lb * ri
        for t in np.linspace(0, 1, seg + 1):
            out.append((1 - t) ** 2 * A + 2 * t * (1 - t) * p + t ** 2 * B)
    return np.array(out)


def mirror_poly(poly, axis=0):
    """reflect in u (axis 0) or v (axis 1); the point order is reversed so the orientation stays consistent"""
    q = np.asarray(poly, float).copy()
    q[:, axis] *= -1
    return q[::-1]


def rect_poly(u0, u1, v0, v1):
    return np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1]], float)


def ellipse_poly(c, a, b, n=28, rot_deg=0.0):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    r = np.radians(rot_deg)
    x, y = np.cos(t) * a, np.sin(t) * b
    return np.column_stack([c[0] + x * np.cos(r) - y * np.sin(r), c[1] + x * np.sin(r) + y * np.cos(r)])


def inset_poly(poly, d):
    """move every vertex towards the centroid by d (simple star-shaped inset)"""
    poly = np.asarray(poly, float)
    c = poly_centroid(poly)
    v = poly - c
    L = np.maximum(np.linalg.norm(v, axis=1), EPS)
    return c + v * np.maximum(1 - d / L, 0.05)[:, None]


# ------------------------------------------------------------------------------------------------------------------------------ surfaces
class HeadSurf:
    """unwrapped head: u = arc length across the face (u = R0 * phi, phi 0 straight ahead, + towards the player's left), v = height z.
    Offsets run along the normals of a heavily smoothed skull (no flaring on the nose / cheek flanks), plus the positive deviation of the real head from that skull (nose, brow, chin),
    so a plate never sinks into the real face."""
    R0 = 4.2

    def __init__(self, cyl, smooth_passes=60, r0=None, max_dev=1.2, act_smooth=0, act_dilate=0):
        act = cyl.dilated(act_dilate) if act_dilate else cyl
        self.cyl = act.smoothed(act_smooth) if act_smooth else act
        self.sm = cyl.smoothed(smooth_passes) if smooth_passes else cyl
        self.max_dev = max_dev
        if r0:
            self.R0 = r0

    def pt(self, u, v, off=0.0):
        u, v, off = np.broadcast_arrays(np.asarray(u, float), np.asarray(v, float), np.asarray(off, float))
        phi = u / self.R0
        n = self.sm.normal(v, phi)
        dev = np.clip(self.cyl.r(v, phi) - self.sm.r(v, phi), 0.0, self.max_dev)
        p = self.sm.point(v, phi, 0.0) + n * (off + dev)[..., None]
        return p, n


# ------------------------------------------------------------------------------------------------------------------------------ plateau
def _orient(m, N_per_vertex):
    """flip all faces when the majority of triangle normals disagree with the surface normals at their vertices"""
    V, F = m.V, m.F
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    ref = N_per_vertex[F].mean(axis=1)
    return m.flipped() if float((fn * ref).sum()) < 0 else m


def plateau(surf, poly, off0, off1, bevel=0.2, step=0.22, n_in=3, profile='fillet', n_bev=3, dome=0.0, centre=None, bevel_fn=None):
    """a raised plate over polygon `poly` (u, v): rim flush at offset off0, flat top at off1 (scalar or callable (u, v) -> offset), edge profile 'fillet' (quarter round) or 'chamfer'.
    The polygon must be star-shaped around its centre (convex-ish); split concave panels. dome adds a pillow bulge in the middle."""
    poly = np.asarray(poly, float)
    pts = densify_closed(poly, step)
    n = len(pts)
    c = poly_centroid(pts) if centre is None else np.asarray(centre, float)
    d = pts - c
    L = np.maximum(np.linalg.norm(d, axis=1), 1e-6)
    bev = np.full(n, float(bevel)) if bevel_fn is None else np.array([bevel_fn(p) for p in pts], float)
    inset = np.minimum(bev / L, 0.62)
    s_top = 1.0 - inset
    f1 = off1 if callable(off1) else (lambda u, v: np.full(np.shape(u), float(off1)))
    f0 = off0 if callable(off0) else (lambda u, v: np.full(np.shape(u), float(off0)))
    rings = []                                         # (u (n,), v (n,), off (n,))
    for k in range(1, n_in + 1):
        s = s_top * (k / n_in)
        u, v = c[0] + d[:, 0] * s, c[1] + d[:, 1] * s
        o = f1(u, v) + dome * (1 - (s / np.maximum(s_top, 1e-6)) ** 2)
        rings.append((u, v, o))
    ut, vt = rings[-1][0], rings[-1][1]
    top_off = rings[-1][2]
    ur, vr = pts[:, 0], pts[:, 1]
    rim_off = f0(ur, vr)
    for j in range(1, n_bev + 1):
        if profile == 'chamfer':
            t = j / n_bev
            su, so = t, t
        else:
            th = np.radians(90.0 * j / n_bev)
            su, so = np.sin(th), 1 - np.cos(th)
        u = ut + (ur - ut) * su
        v = vt + (vr - vt) * su
        o = top_off + (rim_off - top_off) * so
        rings.append((u, v, o))
    cen_off = f1(np.array([c[0]]), np.array([c[1]]))[0] + dome
    U = np.concatenate([[c[0]]] + [r[0] for r in rings])
    Vv = np.concatenate([[c[1]]] + [r[1] for r in rings])
    O = np.concatenate([[cen_off]] + [r[2] for r in rings])
    P, N = surf.pt(U, Vv, O)
    F = []
    R = len(rings)
    for i in range(n):
        F.append([0, 1 + i, 1 + (i + 1) % n])
    for r in range(R - 1):
        for i in range(n):
            a = 1 + r * n + i
            b = 1 + r * n + (i + 1) % n
            c2 = 1 + (r + 1) * n + (i + 1) % n
            d2 = 1 + (r + 1) * n + i
            F.append([a, d2, c2])
            F.append([a, c2, b])
    m = Mesh(P, np.zeros((len(P), 2)), np.array(F, int))
    return _orient(m, N)


def ribbon(surf, line, width, thick, off, step=0.2, cap=True):
    """a thin prism strip following a polyline in (u, v) (grooves, seams, LED lines); width across the surface, thick along the normal, centred at offset `off`"""
    pts = densify_open(line, step)
    P, N = surf.pt(pts[:, 0], pts[:, 1], off)
    return ag.strip_solid(P, N, width, thick, cap=cap)


def ribbon_loop(surf, poly, width, thick, off, step=0.2):
    """a closed ribbon along a polygon outline"""
    pts = densify_closed(poly, step)
    pts = np.vstack([pts, pts[:1], pts[1:3]])
    P, N = surf.pt(pts[:, 0], pts[:, 1], off)
    return ag.strip_solid(P, N, width, thick, cap=False)


def bolt(surf, u, v, off, radius=0.12, h=0.07, sides=8):
    """a small round head (low cylinder) standing on the surface at (u, v)"""
    p, n = surf.pt(np.array([u]), np.array([v]), np.array([off]))
    p, n = p[0], n[0]
    ref = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = ag.unit(np.cross(ref, n))
    y = np.cross(n, x)
    m = ag.cone(radius, radius * 0.82, h, sides=sides)
    return m.transform(R=np.stack([x, y, n], 1), t=p)


def frame_at(surf, u, v, off=0.0):
    """(point, outward normal, tangent along +u, tangent along +v) of the surface at (u, v)"""
    e = 0.05
    p, n = surf.pt(np.array([u]), np.array([v]), np.array([off]))
    pu, _ = surf.pt(np.array([u + e]), np.array([v]), np.array([off]))
    pv, _ = surf.pt(np.array([u]), np.array([v + e]), np.array([off]))
    return p[0], n[0], ag.unit(pu[0] - p[0]), ag.unit(pv[0] - p[0])


# ------------------------------------------------------------------------------------------------------------------------------ tube surface (forearms, hands, legs, torsos along an axis)
class TubeSurf:
    """a limb-like surface around the axis p0 -> p1, measured from a Surface by radial ray casts.  u = arc length around the axis (u = R0 * theta, theta from the reference direction e1),
    v = distance along the axis from p0.  Offsets run along the smoothed surface normal."""

    def __init__(self, surface, p0, p1, up_hint=(0, 0, 1.0), n_v=48, n_th=96, r0=2.0, smooth=3, rmax=9.0, v_pad=0.0, t_clip=(0.0, 1.0)):
        self.p0 = np.asarray(p0, float)
        self.p1 = np.asarray(p1, float)
        self.L = float(np.linalg.norm(self.p1 - self.p0))
        self.ax = (self.p1 - self.p0) / self.L
        up = np.asarray(up_hint, float)
        e1 = up - self.ax * (up @ self.ax)
        self.e1 = e1 / np.linalg.norm(e1)
        self.e2 = np.cross(self.ax, self.e1)
        self.R0 = r0
        self.v = np.linspace(-v_pad, self.L + v_pad, n_v)
        self.th = np.linspace(-np.pi, np.pi, n_th, endpoint=False)
        R = np.full((n_v, n_th), np.nan)
        for i, v in enumerate(self.v):
            c = self.p0 + self.ax * v
            for j, t in enumerate(self.th):
                d = np.cos(t) * self.e1 + np.sin(t) * self.e2
                hit = surface.cast(c, d, tmax=rmax)
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

    def radius(self, v, th):
        v = np.clip(np.asarray(v, float), self.v[0], self.v[-1])
        t = (np.asarray(th, float) + np.pi) % (2 * np.pi) - np.pi
        vi = (v - self.v[0]) / (self.v[1] - self.v[0])
        ti = (t - self.th[0]) / (self.th[1] - self.th[0])
        v0 = np.clip(np.floor(vi).astype(int), 0, len(self.v) - 2)
        t0 = np.floor(ti).astype(int)
        fv, ft = vi - v0, ti - t0
        t0 = t0 % len(self.th)
        t1 = (t0 + 1) % len(self.th)
        R = self.R
        return R[v0, t0] * (1 - fv) * (1 - ft) + R[v0 + 1, t0] * fv * (1 - ft) + R[v0, t1] * (1 - fv) * ft + R[v0 + 1, t1] * fv * ft

    def _point(self, v, th, off):
        r = self.radius(v, th) + off
        d = np.cos(th)[..., None] * self.e1 + np.sin(th)[..., None] * self.e2
        return self.p0 + np.asarray(v, float)[..., None] * self.ax + d * r[..., None]

    def pt(self, u, v, off=0.0):
        u, v, off = np.broadcast_arrays(np.asarray(u, float), np.asarray(v, float), np.asarray(off, float))
        th = u / self.R0
        P = self._point(v, th, off)
        # normal from the tangent frame of the zero-offset surface
        e = 0.05
        Pv = (self._point(v + e, th, 0.0 * off) - self._point(v - e, th, 0.0 * off)) / (2 * e)
        Pt = (self._point(v, th + 0.02, 0.0 * off) - self._point(v, th - 0.02, 0.0 * off)) / 0.04
        n = ag.unit(np.cross(Pt, Pv))
        d = np.cos(th)[..., None] * self.e1 + np.sin(th)[..., None] * self.e2
        n = np.where((n * d).sum(-1, keepdims=True) < 0, -n, n)
        P = P - 0.0 * n
        # move along the true normal instead of the radial direction (no flaring on tilted flanks)
        base = self._point(v, th, 0.0 * off)
        return base + n * off[..., None], n


def hex_lattice(centre, rx, ry, pitch=0.36, row=0.31, inside=None):
    """points of a honeycomb lattice inside an ellipse (or a predicate) around centre=(u, v)"""
    pts = []
    nj = int(np.ceil(ry / row)) + 1
    ni = int(np.ceil(rx / pitch)) + 1
    for j in range(-nj, nj + 1):
        for i in range(-ni, ni + 1):
            u = centre[0] + i * pitch + (0.5 * pitch if j % 2 else 0.0)
            v = centre[1] + j * row
            ok = ((u - centre[0]) / rx) ** 2 + ((v - centre[1]) / ry) ** 2 <= 1.0 if inside is None else inside(u, v)
            if ok:
                pts.append((u, v))
    return np.array(pts)


def hex_prism_on(surf, u, v, off, radius=0.18, h=0.12, sides=6):
    """a hexagonal prism standing on the surface at (u, v)"""
    p, n = surf.pt(np.array([u]), np.array([v]), np.array([off]))
    p, n = p[0], n[0]
    ref = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = ag.unit(np.cross(ref, n))
    y = np.cross(n, x)
    m = ag.cone(radius, radius * 0.9, h, sides=sides)
    return m.transform(R=np.stack([x, y, n], 1), t=p)


def oriented(m, R, t):
    return m.transform(R=R, t=t)


class WarpSurf:
    """a surface seen through a mapping of its layout coordinates: u' = su * u, v' = interp(v) through landmark heights (v_src -> v_dst, linear beyond the ends).
    Used to re-fit a design made on one head to another head with different landmark heights."""

    def __init__(self, base, v_src, v_dst, su=1.0, inflate=0.0):
        self.base = base
        self.su = su
        self.inflate = inflate
        vs = np.asarray(v_src, float)
        vd = np.asarray(v_dst, float)
        # extend with unit slope so the mapping stays defined outside the landmarks
        self.vs = np.concatenate([[vs[0] - 20.0], vs, [vs[-1] + 20.0]])
        self.vd = np.concatenate([[vd[0] - 20.0], vd, [vd[-1] + 20.0]])
        self.sm = getattr(base, 'sm', None)

    def pt(self, u, v, off=0.0):
        u = np.asarray(u, float)
        v = np.asarray(v, float)
        return self.base.pt(u * self.su, np.interp(v, self.vs, self.vd), np.asarray(off, float) + self.inflate)
