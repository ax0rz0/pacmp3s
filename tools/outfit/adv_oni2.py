"""Cyber ONI mask v2 (robotic): hard-surface white plates over a black under-layer, glowing visor slits, a hinged jaw with fangs, short telescoping horns, ear cups with servo rings.

Layout is drawn in unwrapped head coordinates (u = arc across the face, v = height z) and draped over the player's head with adv_panels.  One mesh per colour:
white / black / gray / glow / steel (teeth) + the jaw (own OBJ, pivot at the jaw hinge).   build_oni2(scene) -> (parts, ctx)
"""
import numpy as np

import adv_geom as ag
import adv_panels as pn
import meshgen as mg
from adv_geom import Mesh, unit

WHITE = (236, 236, 240)
BLACK = (20, 20, 26)
GRAY = (62, 66, 78)
STEEL = (196, 202, 214)
GLOW = (255, 72, 30)

UNDER = 0.30          # height of the black under-layer above the skin
TOP = 0.80            # height of the white plate tops
JAW_PIVOT = np.array([-0.2, 0.0, 62.5])


def sline(u):
    """centre line of the eye slit (right side): rises towards the temple"""
    return 64.70 + (np.asarray(u, float) - 0.25) * 0.364


def M(poly):
    return pn.mirror_poly(poly)


def both(m_right, mirror_fn):
    return ag.merge([m_right, mirror_fn(m_right)])


def build_oni2(sc):
    cyl = ag.Cyl(sc.S_head, axis_xy=(0.4, 0.0), z0=56.0, z1=72.0)
    S = pn.HeadSurf(cyl)
    white, black, gray, glow, steel = [], [], [], [], []

    def plate(poly, off1=TOP, bevel=0.2, profile='chamfer', n_bev=1, **kw):
        """one white plate + its mirror image"""
        poly = np.asarray(poly, float)
        a = pn.plateau(S, poly, UNDER, off1, bevel, profile=profile, n_bev=n_bev, **kw)
        b = pn.plateau(S, M(poly), UNDER, off1, bevel, profile=profile, n_bev=n_bev, **kw)
        white.extend([a, b])

    # ------------------------------------------------------------------ black under-layer over the whole lower face (hides the real mouth when the jaw opens)
    outline = np.array([[-5.7, 68.40], [5.7, 68.40], [5.9, 64.0], [5.2, 61.5], [3.8, 60.2], [1.5, 59.8], [-1.5, 59.8], [-3.8, 60.2], [-5.2, 61.5], [-5.9, 64.0]])
    black.append(pn.plateau(S, pn.cut_poly(outline, 0.4), 0.10, UNDER, 0.12, step=0.3, n_in=5, profile='chamfer', n_bev=1))

    # ------------------------------------------------------------------ white plates
    # forehead plate (centre) with a socket for the third eye
    fore = np.array([[-5.2, 68.30], [5.2, 68.30], [5.5, 67.45], [4.4, 66.95], [2.2, 66.62], [0.0, 66.95], [-2.2, 66.62], [-4.4, 66.95], [-5.5, 67.45]])
    white.append(pn.plateau(S, pn.cut_poly(fore, 0.3), UNDER, TOP, 0.2, step=0.25, n_in=4, profile='chamfer', n_bev=1))
    # brow plates (a heavy angry brow, taller than the rest)
    brow = np.array([[0.72, sline(0.72) + 0.42], [3.6, sline(3.6) + 0.42], [5.15, 66.85], [5.45, 67.55], [3.7, 67.80], [2.0, 67.42], [0.72, 66.80]])
    plate(pn.cut_poly(brow, 0.16), off1=TOP + 0.22, bevel=0.24)
    # nose plate: a narrow angular bridge
    nose = np.array([[-0.34, 66.50], [0.34, 66.50], [0.42, 65.4], [0.56, 64.1], [0.60, 63.5], [0.36, 63.14], [-0.36, 63.14], [-0.60, 63.5], [-0.56, 64.1], [-0.42, 65.4]])
    white.append(pn.plateau(S, pn.cut_poly(nose, 0.1), UNDER, TOP + 0.2, 0.18, step=0.2, n_in=4, profile='chamfer', n_bev=1))
    # cheek plates
    cheek = np.array([[0.78, sline(0.78) - 0.42], [3.6, sline(3.6) - 0.42], [5.05, 65.55], [5.25, 64.3], [4.7, 63.45], [3.1, 63.0], [1.25, 63.2], [1.1, 63.9]])
    plate(pn.cut_poly(cheek, 0.15), off1=TOP - 0.05, bevel=0.2)
    # vent slats on the lower cheek (thin bars, the black under-layer shows between them)
    for k in range(4):
        z0 = 62.45 - 0.44 * k
        u0, u1 = 3.35 - 0.14 * k, 4.35 - 0.3 * k
        slat = np.array([[u0, z0], [u1, z0 + 0.08], [u1 + 0.06, z0 + 0.28], [u0, z0 + 0.2]])
        plate(pn.cut_poly(slat, 0.05), off1=TOP - 0.2, bevel=0.07, n_in=2, step=0.16)
    # upper lip plate (carries the upper fangs)
    lip = np.array([[-2.5, 63.0], [2.5, 63.0], [2.85, 62.82], [2.55, 62.62], [-2.55, 62.62], [-2.85, 62.82]])
    white.append(pn.plateau(S, lip, UNDER, TOP + 0.04, 0.1, step=0.2, n_in=3, profile='chamfer', n_bev=1))
    # temple plates in front of the ear cups
    temple = np.array([[4.55, 66.4], [5.6, 66.7], [5.75, 65.0], [5.5, 63.8], [4.9, 64.2], [5.0, 65.5]])
    plate(pn.cut_poly(temple, 0.1), off1=TOP - 0.1, bevel=0.14, n_in=2)

    # ------------------------------------------------------------------ glow: visor slits, cheek LEDs, brow LED lines, third eye
    for sgn in (+1, -1):
        us = np.linspace(0.62, 3.55, 14)
        w = np.interp(us, [0.62, 1.2, 2.2, 3.55], [0.10, 0.34, 0.30, 0.10])
        line = np.column_stack([us * sgn, sline(us)])
        P, N = S.pt(line[:, 0], line[:, 1], UNDER + 0.05)
        glow.append(ag.strip_solid(P, N, w, 0.06, cap=True))
        # brow edge LED
        us2 = np.linspace(0.9, 4.6, 10)
        zz = np.interp(us2, [0.9, 2.0, 3.7, 4.6], [66.60, 67.05, 67.50, 67.52])
        glow.append(pn.ribbon(S, np.column_stack([us2 * sgn, zz]), 0.075, 0.05, TOP + 0.23 + 0.02))
        # small cheek LED bars on the outer cheek
        glow.append(pn.ribbon(S, [[sgn * 4.0, 64.1], [sgn * 4.75, 64.35]], 0.10, 0.05, TOP + 0.01))
        glow.append(pn.ribbon(S, [[sgn * 4.1, 63.75], [sgn * 4.85, 63.98]], 0.07, 0.05, TOP + 0.01))
    # third eye: a glowing lens in a socket
    pe, ne, te, ve = pn.frame_at(S, 0.0, 67.75, TOP + 0.02)
    R = np.stack([te, ve, ne], 1)
    socket = ag.cone(0.62, 0.5, 0.22, sides=24).transform(R=R, t=pe)
    lens = ag.cone(0.34, 0.26, 0.16, sides=22).transform(R=R, t=pe + ne * 0.12)
    black.append(socket)
    glow.append(lens)
    ring = mg.torus(0.5, 0.06, nu=32, nv=8).transform(R=R, t=pe + ne * 0.2)
    gray.append(ring)
    # forehead light bars
    for sgn in (+1, -1):
        glow.append(pn.ribbon(S, [[sgn * 1.25, 67.75], [sgn * 2.5, 67.75]], 0.10, 0.05, TOP + 0.02))
        glow.append(pn.ribbon(S, [[sgn * 1.25, 67.45], [sgn * 2.1, 67.45]], 0.07, 0.05, TOP + 0.02))

    # ------------------------------------------------------------------ black trim: panel lines, vent grooves, nostrils, seams
    for sgn in (+1, -1):
        black.append(pn.ribbon(S, [[sgn * 0.55, 66.75], [sgn * 0.55, 66.1]], 0.07, 0.06, TOP + 0.02))
        black.append(pn.ribbon(S, np.column_stack([sgn * np.array([1.2, 1.9, 2.7]), [67.9, 67.82, 67.95]]), 0.06, 0.05, TOP + 0.02))
        # nostril slits
        black.append(pn.ribbon(S, [[sgn * 0.42, 63.55], [sgn * 0.72, 63.28]], 0.11, 0.06, TOP + 0.14))
        # cheek panel line
        black.append(pn.ribbon(S, [[sgn * 1.55, 64.2], [sgn * 2.5, 63.95], [sgn * 3.4, 64.1]], 0.06, 0.05, TOP + 0.02))
        # forehead vertical grooves
        for k in range(3):
            u = sgn * (3.0 + 0.7 * k)
            black.append(pn.ribbon(S, [[u, 68.1], [u + sgn * 0.12, 67.55]], 0.07, 0.05, TOP + 0.02))
    # screws
    for sgn in (+1, -1):
        for (u, v) in ((4.9, 67.45), (4.95, 64.9), (1.3, 63.45), (5.35, 64.0)):
            gray.append(pn.bolt(S, sgn * u, v, TOP + 0.02, radius=0.13, h=0.06))

    # ------------------------------------------------------------------ slim headband with a glowing line
    ph = np.radians(np.linspace(-180, 180, 120))
    z = 68.78 + 0.30 * (1 - np.cos(ph)) / 2
    Pb = cyl.point(z, ph, 0.46)
    Nb = cyl.normal(z, ph)
    Pb, Nb = np.vstack([Pb, Pb[:3]]), np.vstack([Nb, Nb[:3]])
    black.append(ag.strip_solid(Pb, Nb, 0.62, 0.34, cap=False))
    glow.append(ag.strip_solid(Pb + Nb * 0.19, Nb, 0.08, 0.05, cap=False))

    # ------------------------------------------------------------------ short swept-back horns: hex section, white base + black tip, collar rings
    for sgn in (+1, -1):
        base, nb, tu, tv = pn.frame_at(S, sgn * 2.9, 68.55, 0.35)
        pts = np.array([base + np.array([0.0, 0, -0.15]), base + np.array([-0.15, sgn * 0.45, 0.95]), base + np.array([-0.6, sgn * 1.15, 1.85]), base + np.array([-1.35, sgn * 1.85, 2.5])])
        path = ag.catmull(pts, 26)
        s = np.linspace(0, 1, len(path))
        rad = np.interp(s, [0, 0.4, 0.75, 1.0], [0.62, 0.5, 0.28, 0.03])
        k = 15
        lower = ag.loft(path[:k + 1], ag.circle(6, 1.0, 1.0), scale=rad[:k + 1], cap_start=True, cap_end=True, up_hint=(1, 0, 0))
        upper = ag.loft(path[k:], ag.circle(6, 1.0, 1.0), scale=rad[k:], cap_start=True, cap_end=True, up_hint=(1, 0, 0))
        white.append(lower)
        black.append(upper)
        for idx, (rr, hh) in ((0, (1.22, 0.2)), (k, (1.2, 0.16))):
            dd = unit(path[min(idx + 1, len(path) - 1)] - path[idx])
            fr = ag.path_frames(np.array([path[idx], path[idx] + dd]))
            gray.append(ag.cone(rad[idx] * rr, rad[idx] * rr, hh, sides=12).transform(R=np.stack([fr[1][0], fr[2][0], dd], 1), t=path[idx] - dd * hh * 0.5))
        dd = unit(path[k + 1] - path[k])
        fr = ag.path_frames(np.array([path[k], path[k] + dd]))
        glow.append(mg.torus(rad[k] * 1.0, 0.05, nu=20, nv=6).transform(R=np.stack([fr[1][0], fr[2][0], dd], 1), t=path[k] + dd * 0.12))

    # ------------------------------------------------------------------ ear cups with servo rings, hoses
    for sgn in (+1, -1):
        c = np.array([-0.3, 3.75 * sgn, 65.4])
        Rr = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, sgn * 1.0, 0]])
        gray.append(ag.cone(1.85, 1.65, 0.85, sides=28).transform(R=Rr, t=c))
        glow.append(mg.torus(1.28, 0.1, nu=40, nv=8).transform(R=Rr, t=c + np.array([0, sgn * 0.46, 0])))
        black.append(ag.cone(0.95, 0.95, 0.12, sides=20).transform(R=Rr, t=c + np.array([0, sgn * 0.44, 0])))
        gray.append(ag.cone(0.5, 0.5, 0.24, sides=16).transform(R=Rr, t=c + np.array([0, sgn * 0.52, 0])))
        # jaw hinge servo below the ear cup
        hinge = np.array([JAW_PIVOT[0], 3.45 * sgn, JAW_PIVOT[2]])
        black.append(ag.cone(0.62, 0.62, 0.6, sides=18).transform(R=Rr, t=hinge - np.array([0, sgn * 0.1, 0])))
        gray.append(ag.cone(0.36, 0.36, 0.2, sides=14).transform(R=Rr, t=hinge + np.array([0, sgn * 0.48, 0])))
        pts = np.array([[-0.6, 3.1 * sgn, 61.8], [-1.4, 3.7 * sgn, 60.2], [-2.5, 4.3 * sgn, 58.2], [-3.4, 5.0 * sgn, 56.2], [-4.0, 5.6 * sgn, 54.8]], float)
        path = ag.catmull(pts, 24)
        gray.append(ag.tube_path(path, 0.28, sides=10))
        for t in (3, 11, 19):
            cc = path[t]
            dd = unit(path[t + 1] - path[t])
            fr = ag.path_frames(np.array([cc, cc + dd]))
            black.append(ag.cone(0.40, 0.40, 0.33, sides=12).transform(R=np.stack([fr[1][0], fr[2][0], dd], 1), t=cc - dd * 0.16))

    # ------------------------------------------------------------------ teeth: upper fangs on the lip plate (steel), lower tusks on the jaw
    for u in np.linspace(-1.9, 1.9, 9):
        if abs(u) < 0.2:
            continue
        p, n, tu, tv = pn.frame_at(S, u, 62.66, TOP + 0.02)
        path = np.array([p, p + np.array([0.12, 0, -0.26]), p + np.array([0.2, 0, -0.52])])
        steel.append(ag.spike(path, 0.15, sides=4, power=1.0))
    for sgn in (+1, -1):
        p, n, tu, tv = pn.frame_at(S, sgn * 1.2, 62.66, TOP + 0.02)
        path = np.array([p, p + np.array([0.1, sgn * 0.05, -0.65]), p + np.array([0.22, sgn * 0.12, -1.3])])
        steel.append(ag.spike(ag.catmull(path, 8), 0.22, sides=6, power=1.1))

    parts = {}
    parts['white'] = dict(mesh=ag.merge(white), color=WHITE, rough=0.32, smooth=42)
    parts['black'] = dict(mesh=ag.merge(black), color=BLACK, rough=0.5, smooth=40)
    parts['gray'] = dict(mesh=ag.merge(gray), color=GRAY, rough=0.35, metal=0.55, smooth=40)
    parts['glow'] = dict(mesh=ag.merge(glow), color=GLOW, nolight=True, smooth=60)
    parts['steel'] = dict(mesh=ag.merge(steel), color=STEEL, rough=0.3, metal=0.35, smooth=35)

    # ------------------------------------------------------------------ jaw (hinged at JAW_PIVOT): lower plate, lower tusks, an inner black mouth plate
    jaw_white, jaw_steel, jaw_black = [], [], []
    jaw_poly = np.array([[-2.95, 62.46], [2.95, 62.46], [3.0, 61.5], [2.6, 60.6], [1.4, 59.95], [-1.4, 59.95], [-2.6, 60.6], [-3.0, 61.5]])
    jaw_white.append(pn.plateau(S, pn.cut_poly(jaw_poly, 0.14), UNDER, TOP + 0.1, 0.2, step=0.22, n_in=4))
    for sgn in (+1, -1):
        # chin vent slots
        for k in range(3):
            z0 = 61.0 - 0.28 * k
            jaw_black.append(pn.ribbon(S, [[sgn * 0.5, z0], [sgn * 1.9 - 0.2 * k, z0 - 0.04]], 0.07, 0.05, TOP + 0.13))
    for sgn in (+1, -1):
        jaw_black.append(pn.ribbon(S, [[sgn * 1.15, 62.0], [sgn * 1.25, 61.2], [sgn * 0.95, 60.3]], 0.07, 0.05, TOP + 0.13))
        jaw_black.append(pn.ribbon(S, [[sgn * 1.25, 61.2], [sgn * 2.55, 61.45]], 0.06, 0.05, TOP + 0.13))
        for (u, v) in ((2.55, 62.05), (2.35, 60.95), (0.7, 60.35)):
            jaw_steel.append(pn.bolt(S, sgn * u, v, TOP + 0.12, radius=0.12, h=0.07))
    jaw_black.append(pn.ribbon(S, [[-1.15, 62.0], [1.15, 62.0]], 0.06, 0.05, TOP + 0.13))
    jaw_glow = [pn.ribbon(S, [[-0.55, 61.55], [0.0, 61.2], [0.55, 61.55]], 0.09, 0.05, TOP + 0.14)]
    for u in np.linspace(-1.5, 1.5, 7):
        p, n, tu, tv = pn.frame_at(S, u, 62.42, TOP + 0.1)
        path = np.array([p, p + np.array([0.0, 0, 0.24]), p + np.array([-0.05, 0, 0.46])])
        jaw_steel.append(ag.spike(path, 0.14, sides=4))
    for sgn in (+1, -1):
        p, n, tu, tv = pn.frame_at(S, sgn * 1.75, 62.38, TOP + 0.1)
        path = np.array([p, p + np.array([0.4, sgn * 0.1, 0.95]), p + np.array([0.8, sgn * 0.3, 2.0])])
        jaw_steel.append(ag.spike(ag.catmull(path, 10), 0.25, sides=6, power=1.1))
    parts['jaw'] = dict(mesh=ag.merge(jaw_white), color=WHITE, rough=0.32, smooth=42, pivot=JAW_PIVOT)
    parts['jaw_black'] = dict(mesh=ag.merge(jaw_black), color=BLACK, rough=0.5, smooth=40, pivot=JAW_PIVOT)
    parts['jaw_steel'] = dict(mesh=ag.merge(jaw_steel), color=STEEL, rough=0.3, metal=0.35, smooth=35, pivot=JAW_PIVOT)
    parts['jaw_glow'] = dict(mesh=ag.merge(jaw_glow), color=GLOW, nolight=True, smooth=60, pivot=JAW_PIVOT)
    return parts, dict(surf=S, cyl=cyl, lists=dict(white=white, black=black, gray=gray, glow=glow, steel=steel))


def rotate_about_y(mesh, pivot, deg):
    """preview helper: rotate a Source-frame mesh about the hinge axis (the world y axis through `pivot`); positive opens the jaw (chin down and back)"""
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    V = (mesh.V - pivot) @ R.T + pivot
    return Mesh(V, mesh.UV.copy(), mesh.F.copy())
