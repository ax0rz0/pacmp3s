"""Spectral Archivist geometry (ghost / transparent humanoid): porcelain veil mask with glowing slit eyes, a draped hood + tattered veil strips, a glowing inner anatomy (spine, ribs, sternum,
core with gyro rings), a ragged shroud around the hips, spectral chains from the wrists.  World frame, bind pose.  build_ghost(scene) -> (parts, ctx)."""
import numpy as np

import adv_geom as ag
import adv_panels as pn
import meshgen as mg
from adv_geom import unit

PORCELAIN = (226, 236, 250)
CLOTH = (120, 190, 255)
GLOW = (110, 215, 255)
CENTRE = np.array([0.4, 0.0, 65.0])


def e_phi(ph):
    return np.array([-np.sin(ph), np.cos(ph), 0.0])


def lock(path, w, th, up, sides=6, cap=True):
    sc = np.column_stack([np.asarray(w) / 2.0, np.asarray(th) / 2.0])
    return ag.loft(np.asarray(path, float), ag.circle(sides, 1.0, 1.0), scale=sc, up_hint=np.asarray(up, float), cap_start=cap, cap_end=True)


def taper(n, w0, w1=0.05, power=0.7):
    s = np.linspace(0, 1, n)
    return w1 + (w0 - w1) * (1 - s) ** power


def hang(last, v0, steps, step_len, g=0.2, sway=None):
    P = [np.asarray(last, float)]
    v = unit(np.asarray(v0, float))
    for k in range(steps):
        v = unit(v + np.array([0, 0, -g]) + (0 if sway is None else sway(k)))
        P.append(P[-1] + v * step_len)
    return np.array(P[1:])


# ------------------------------------------------------------------------------------------------------------------------------ face mask
def make_mask(S):
    R = np.array([[0.0, 68.7], [1.6, 68.5], [3.2, 67.8], [4.6, 66.5], [5.4, 64.7], [5.3, 62.7], [4.5, 61.0], [3.0, 59.8], [1.5, 59.3], [0.0, 59.1]])
    full = np.vstack([R, R[1:-1][::-1] * np.array([-1.0, 1.0])])
    body = pn.plateau(S, full, 0.2, 0.72, 0.45, step=0.22, n_in=6, profile='fillet', n_bev=4, dome=0.14)
    detail, glow = [], []
    # nose ridge, brow arcs, small mouth
    detail.append(pn.ribbon(S, [[0.0, 66.3], [0.0, 65.0], [0.0, 63.6]], 0.34, 0.26, 0.98))
    for sgn in (+1, -1):
        for line in (([0.5, 66.5], [1.6, 66.9], [3.0, 66.4]), ([0.5, 66.95], [1.6, 67.35], [3.1, 66.85])):
            pts = np.array([[sgn * a_, b_] for a_, b_ in line])
            pts = ag.catmull(np.column_stack([pts, np.zeros(len(pts))]), 14)[:, :2]
            detail.append(pn.ribbon(S, pts, 0.08, 0.08, 0.92))
    detail.append(pn.ribbon(S, [[-0.9, 61.5], [0.0, 61.25], [0.9, 61.5]], 0.08, 0.08, 0.93))
    # eyes: tall slanted slits (glow), cheek tear lines, forehead seam
    for sgn in (+1, -1):
        c = np.array([sgn * 1.45, 65.1])
        t = np.radians(sgn * 9.0)
        base = np.array([[0.0, 0.95], [0.34, 0.1], [0.0, -0.78], [-0.34, 0.1]])
        rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
        poly = (base @ rot.T) + c
        glow.append(pn.plateau(S, pn.round_poly(poly, 0.16, 3), 0.8, 1.0, 0.1, step=0.12, n_in=3, profile='chamfer', n_bev=1))
        glow.append(pn.ribbon(S, [[sgn * 1.6, 64.2], [sgn * 1.8, 63.2], [sgn * 1.7, 62.3]], 0.06, 0.06, 0.9))
    glow.append(pn.ribbon(S, [[0.0, 68.4], [0.0, 67.0]], 0.07, 0.06, 0.9))
    return body, ag.merge(detail), ag.merge(glow)


# ------------------------------------------------------------------------------------------------------------------------------ hood and veil
def make_hood(R):
    nth, nph = 30, 150
    th = np.radians(np.linspace(6, 89, nth + 1))
    ph = np.radians(np.linspace(-180, 180, nph + 1))
    TH, PH = np.meshgrid(th, ph, indexing='ij')
    rng = np.random.RandomState(3)
    folds = 0.28 * np.sin(9 * PH + 1.3 * np.sin(3 * TH)) * (0.4 + 0.6 * np.cos(TH)) + 0.16 * np.sin(5 * PH + 4 * TH)
    base = 1.15 + 0.35 * np.sin(np.pi * (TH / np.radians(89))) + folds
    Po = R.point(TH, PH, base)
    Pi = R.point(TH, PH, base - 0.16)
    cth = 0.5 * (TH[:-1, :-1] + TH[1:, 1:])
    cph = 0.5 * (PH[:-1, :-1] + PH[1:, 1:])
    dth, dph = np.degrees(cth), np.degrees(cph)
    keep = np.ones_like(dth, bool)
    keep &= ~((np.abs(dph) < 48) & (dth < 66))                         # face opening (the mask sits in it)
    keep &= ~((np.abs(dph) < 62) & (dth < 40))
    # ragged hem: lower edge noisy, longer at the back
    hem = 14 + 9 * np.sin(2.3 * dph * np.pi / 180) + 6 * np.sin(7.1 * dph * np.pi / 180 + 1.0) - 6 * np.cos(dph * np.pi / 180)
    keep &= dth > hem
    shell = ag.solidify(np.transpose(Po, (1, 0, 2)), np.transpose(Pi, (1, 0, 2)), keep.T)
    return ag.fix_outward(shell)


def make_veil(R, rng):
    """tattered cloth strips hanging from the back of the hood (origin of the mesh = the head bone origin so they can sway)"""
    out = []
    for k in range(13):
        s = k / 12.0
        ph0 = np.radians(112 + 136 * s + rng.uniform(-3, 3))
        th0 = np.radians(rng.uniform(12, 24))
        base = R.point(np.array([th0, th0 - 0.12]), np.array([ph0, ph0]), np.array([1.35, 1.7]))
        v0 = base[1] - base[0]
        length = rng.uniform(10, 24)
        steps = int(length / 1.1)
        ext = hang(base[1], v0 + np.array([-0.25, 0, 0]), steps, 1.1, g=0.32, sway=lambda i, a=rng.uniform(0, 6): np.array([0.05 * np.sin(a + i * 0.5), 0.07 * np.cos(a + i * 0.45), 0.0]))
        path = np.vstack([base, ext])
        path[:, 0] = np.minimum(path[:, 0], -2.6)
        n = len(path)
        w = taper(n, rng.uniform(1.6, 2.6), 0.12, 0.55)
        out.append(lock(path, w, np.full(n, 0.07), e_phi(ph0), sides=4))
    return ag.merge(out)


# ------------------------------------------------------------------------------------------------------------------------------ inner anatomy
def make_anatomy(sc):
    S = sc.S_suit
    cyl = ag.Cyl(S, axis_xy=(-0.6, 0.0), z0=38.0, z1=60.0, n_z=50, n_phi=145, smooth=2)
    spine, ribs = [], []
    zs = np.linspace(41.0, 58.0, 24)
    # vertebrae
    for i, z in enumerate(zs):
        r_back = float(cyl.r(z, np.pi))
        cx = -0.6 - r_back + 2.4 + 0.15 * np.sin(i * 0.35)
        c = np.array([cx, 0.0, z])
        size = 0.62 + 0.14 * (1 - (z - 41) / 17.0)
        spine.append(ag.cone(size, size * 0.92, 0.55, sides=8).transform(R=np.eye(3), t=c - np.array([0, 0, 0.27])))
        spine.append(ag.box((0.55, 2.2 * size * 1.1, 0.22), rc=0.06).transform(R=np.eye(3), t=c + np.array([-0.55, 0, 0.0])))
        spine.append(ag.spike(np.array([c + [-0.5, 0, 0.1], c + [-1.25, 0, -0.05], c + [-1.8, 0, -0.3]]), 0.2, sides=4))
    # ribs: pairs of flat arcs from the spine to the sternum
    k_ribs = 10
    for k in range(k_ribs):
        z0 = 44.2 + 1.05 * k
        for sgn in (+1, -1):
            t = np.linspace(0, 1, 20)
            phi = np.pi - sgn * (np.radians(24) + t * (np.pi - np.radians(24) - np.radians(24)))     # from the back (pi) round the side to the front
            z = z0 - 1.6 * t ** 1.4 + 0.5 * np.sin(np.pi * t)
            r_in = cyl.r(z, phi) - 1.15 - 0.4 * (1 - np.sin(np.pi * np.clip(t, 0, 1)))
            pts = np.column_stack([-0.6 + np.cos(phi) * r_in, np.sin(phi) * r_in, z])
            w = 0.34 - 0.14 * t
            sec = ag.circle(6, 1.0, 1.0)
            ribs.append(ag.loft(pts, sec, scale=np.column_stack([w * 0.5, np.full_like(w, 0.085)]), up_hint=(0, 0, 1.0)))
    # sternum + clavicles
    zf = np.linspace(43.5, 54.5, 12)
    pts = np.column_stack([-0.6 + (cyl.r(zf, 0.0) - 1.5), np.zeros_like(zf), zf])
    ribs.append(ag.loft(pts, ag.circle(8, 1.0, 1.0), scale=np.column_stack([np.full_like(zf, 0.4), np.full_like(zf, 0.1)]), up_hint=(0, 1.0, 0)))
    for sgn in (+1, -1):
        pts = np.array([[0.7, 0.0, 55.2], [0.3, sgn * 2.2, 55.6], [-0.6, sgn * 4.6, 56.0], [-1.5, sgn * 6.4, 55.8]])
        ribs.append(ag.tube_path(ag.catmull(pts, 14), 0.2, sides=7))
    return ag.merge(spine), ag.merge(ribs), cyl


def make_core(centre):
    parts = []
    parts.append(mg.ellipsoid((1.25, 1.25, 1.25), nu=22, nv=14).transform(t=centre))
    return ag.merge(parts)


def make_rings(centre):
    rings = []
    for k, (R_, tilt) in enumerate(((2.4, 0.0), (3.0, 60.0), (3.6, -60.0))):
        t = mg.torus(R_, 0.1, nu=44, nv=8)
        a = np.radians(tilt)
        Rm = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
        rings.append(t.transform(R=Rm, t=centre))
        # small beads on each ring
        for j in range(3):
            ang_ = j * 2.0944 + k
            p = np.array([R_ * np.cos(ang_), R_ * np.sin(ang_), 0.0])
            rings.append(ag.cone(0.2, 0.15, 0.3, sides=8).transform(R=Rm, t=centre + Rm @ p))
    return ag.merge(rings)


def make_big_rings(centre):
    """two big thin orbit rings with runic ticks"""
    out = []
    for R_, tilt, n_tick in ((13.5, 0.0, 24), (16.0, 24.0, 32)):
        a = np.radians(tilt)
        Rm = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
        out.append(mg.torus(R_, 0.16, nu=72, nv=8).transform(R=Rm, t=centre))
        for j in range(n_tick):
            ang_ = j * 2 * np.pi / n_tick
            p = np.array([R_ * np.cos(ang_), R_ * np.sin(ang_), 0.0])
            h = 0.9 if j % 4 == 0 else 0.45
            tang = np.array([-np.sin(ang_), np.cos(ang_), 0.0])
            Rt = np.stack([np.array([np.cos(ang_), np.sin(ang_), 0.0]), tang, np.array([0.0, 0.0, 1.0])], 1)
            out.append(ag.box((h, 0.3, 0.12), rc=0.02).transform(R=Rm @ Rt, t=centre + Rm @ p))
    return ag.merge(out)


# ------------------------------------------------------------------------------------------------------------------------------ shroud + chains
def make_shroud(sc, rng):
    S = sc.S_all
    cyl = ag.Cyl(S, axis_xy=(0.1, 0.0), z0=30.0, z1=44.0, n_z=30, n_phi=145, smooth=3)
    out = []
    n = 22
    for k in range(n):
        ph0 = 2 * np.pi * (k + rng.uniform(-0.2, 0.2)) / n - np.pi
        z0 = 41.5
        r0 = float(cyl.r(z0, ph0)) + 0.5
        p0 = np.array([0.1 + np.cos(ph0) * r0, np.sin(ph0) * r0, z0])
        length = rng.uniform(16, 38) * (0.75 + 0.25 * np.cos(ph0 * 2))
        steps = int(length / 1.6)
        flare = np.array([np.cos(ph0), np.sin(ph0), 0.0]) * rng.uniform(0.18, 0.3)
        wave = rng.uniform(0, 6)
        ext = hang(p0, flare + np.array([0, 0, -0.9]), steps, 1.6, g=0.0, sway=lambda i, w=wave, f=flare: f * 0.06 + np.array([0.06 * np.sin(w + i * 0.4), 0.06 * np.cos(w + 0.7 * i), 0.0]))
        path = np.vstack([p0, ext])
        m = len(path)
        w_ = taper(m, rng.uniform(2.4, 3.4), 0.15, 0.6)
        out.append(lock(path, w_, np.full(m, 0.08), e_phi(ph0), sides=4))
    return ag.merge(out)


def make_chain(p0, direction, links=13, link_len=2.1, link_w=1.15, tube=0.19):
    """a chain of interlocked elliptical links hanging along `direction` from p0"""
    d = unit(np.asarray(direction, float))
    ref = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    a = unit(np.cross(d, ref))
    b = np.cross(d, a)
    pitch = link_len - 0.55
    out = []
    t = np.linspace(0, 2 * np.pi, 30)
    for i in range(links):
        c = p0 + d * (0.4 + i * pitch)
        u = a if i % 2 == 0 else b
        pts = c[None, :] + np.outer(np.cos(t), u) * (link_w / 2.0) + np.outer(np.sin(t), d) * (link_len / 2.0)
        out.append(ag.tube_path(pts, tube, sides=7, cap=False))
    return ag.merge(out)


def build_ghost(sc):
    rng = np.random.RandomState(21)
    cyl = ag.Cyl(sc.S_head, axis_xy=(0.4, 0.0), z0=56.0, z1=73.0)
    S = pn.HeadSurf(cyl, max_dev=1.2)
    R = ag.Radial(sc.S_head, CENTRE, n_theta=61, n_phi=181, smooth=3, rmax=20.0)
    mask, mask_detail, eyes = make_mask(S)
    hood = make_hood(R)
    veil = make_veil(R, rng)
    spine, ribs, tcyl = make_anatomy(sc)
    rig = sc.rig
    s2 = rig.world[rig.idx['ValveBiped.Bip01_Spine2']][:3, 3]
    core_c = np.array([1.2, 0.0, 51.2])
    core = make_core(core_c)
    rings = make_rings(core_c)
    big = make_big_rings(np.array([0.3, 0.0, 47.0]))
    shroud = make_shroud(sc, rng)
    hand = rig.world[rig.idx['ValveBiped.Bip01_L_Hand']][:3, 3]
    elbow = rig.world[rig.idx['ValveBiped.Bip01_L_Forearm']][:3, 3]
    chain_dir = unit(hand - elbow)
    chain_l = make_chain(hand + chain_dir * 0.4, chain_dir)
    parts = {
        'mask': dict(mesh=ag.merge([mask, mask_detail]), color=PORCELAIN, rough=0.3, smooth=50),
        'eyes': dict(mesh=eyes, color=GLOW, nolight=True, smooth=60),
        'hood': dict(mesh=hood, color=CLOTH, rough=0.8, alpha=0.38, double=True, smooth=55),
        'veil': dict(mesh=veil, color=CLOTH, rough=0.8, alpha=0.34, double=True, smooth=60),
        'anatomy': dict(mesh=ag.merge([spine, ribs]), color=GLOW, nolight=True, smooth=55),
        'core': dict(mesh=core, color=(235, 250, 255), nolight=True, smooth=60),
        'rings': dict(mesh=rings, color=GLOW, nolight=True, smooth=60),
        'shroud': dict(mesh=shroud, color=CLOTH, rough=0.8, alpha=0.34, double=True, smooth=60),
        'chain_l': dict(mesh=chain_l, color=GLOW, nolight=True, smooth=55),
    }
    ctx = dict(surf=S, radial=R, core=core_c, chain_origin=hand + chain_dir * 0.4, chain_dir=chain_dir, spine2=s2, big_centre=np.array([0.3, 0.0, 47.0]))
    return parts, ctx
