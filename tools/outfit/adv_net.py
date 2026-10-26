"""Netrunner outfit geometry (Ethics Assistant): respirator half-mask with hex vents, side filters, glowing slit; right-eye cyber implant; ear cups + headset arc; custom hair.
Head parts are built in the in-game world frame (bind pose) like the oni mask.  build_head(scene) -> (parts, ctx)."""
import numpy as np

import adv_geom as ag
import adv_panels as pn
import meshgen as mg
from adv_geom import unit

BLACK = (16, 16, 21)
GRAPH = (44, 46, 56)
GUN = (92, 96, 110)
GLOW = (255, 30, 140)
LENS = (70, 210, 255)

UNDER = 0.36


def snout(u, v):
    """how far the respirator bulges forward in the middle of the face"""
    return 0.80 * np.exp(-(np.asarray(u, float) / 1.7) ** 2) * np.exp(-((np.asarray(v, float) - 62.3) / 1.9) ** 2)


def top_off(u, v):
    return 0.50 + snout(u, v)


def mask_outline():
    R = np.array([[0.0, 65.75], [0.4, 65.6], [0.8, 64.55], [1.5, 64.28], [2.4, 64.22], [3.4, 64.35], [4.3, 64.6], [5.05, 64.3], [5.55, 63.0], [5.55, 61.4], [4.8, 60.2], [3.4, 59.6],
                  [1.8, 59.4], [0.0, 59.35]])
    L = R[1:-1][::-1] * np.array([-1.0, 1.0])
    return np.vstack([R, L])


def top_edge_points(k):
    """points along the top rim of the mask, moved down by k * 0.22 (for the ribbed top)"""
    R = np.array([[0.4, 65.6], [0.8, 64.55], [1.5, 64.28], [2.4, 64.22], [3.4, 64.35], [4.3, 64.6]])
    pts = pn.densify_open(R, 0.15)
    return pts


def build_head(sc, head_surface=None, axis_xy=(0.4, 0.0), warp=None, cup_x=-0.3, cup_y=3.75, cup_z=65.2, arc_top=71.4, eye_u=-1.42, eye_v=65.12, act_smooth=0, act_dilate=0, inflate=0.0, max_dev=1.2, filter_v=61.9, **_ignored):
    """warp: (v_src, v_dst) landmark heights mapping this design onto another head (see pn.WarpSurf); head_surface: ethics_acc.Surface of the skin to fit (default: the Ethics Assistant's head)"""
    cyl = ag.Cyl(head_surface or sc.S_head, axis_xy=axis_xy, z0=56.0, z1=73.0)
    S = pn.HeadSurf(cyl, max_dev=max_dev, act_smooth=act_smooth, act_dilate=act_dilate)
    if warp:
        S = pn.WarpSurf(S, warp[0], warp[1], inflate=inflate)
    black, gray, gun, glow, lens = [], [], [], [], []

    # ------------------------------------------------------------------ the respirator shell
    outline = mask_outline()
    shell = pn.plateau(S, pn.cut_poly(outline, 0.25), UNDER, top_off, 0.2, step=0.2, n_in=7, profile='chamfer', n_bev=1)
    black.append(shell)

    def on_top(u, v, dz=0.0):
        return top_off(u, v) + dz

    # central beak ridge + ribbed top edge + chin plate
    black.append(pn.ribbon(S, [[0.0, 65.3], [0.0, 62.9], [0.0, 59.6]], 0.42, 0.22, on_top(0, 62.0, 0.06) + 0.04))
    for sgn in (+1, -1):
        for k in (1, 2, 3):
            e = top_edge_points(k) * np.array([sgn, 1.0]) + np.array([0.0, -0.20 * k - 0.1])
            black.append(pn.ribbon(S, e[1:], 0.09, 0.08, 0.66))
    chin = np.array([[-2.2, 60.75], [2.2, 60.75], [1.75, 59.75], [-1.75, 59.75]])
    gray.append(pn.plateau(S, pn.cut_poly(chin, 0.2), lambda u, v: top_off(u, v) - 0.02, lambda u, v: top_off(u, v) + 0.2, 0.12, step=0.2, n_in=3, profile='chamfer', n_bev=1))
    # hex mesh vents on the cheeks
    for sgn in (+1, -1):
        for (u, v) in pn.hex_lattice((2.55, 62.35), 1.05, 1.45, pitch=0.36, row=0.31):
            gun.append(pn.hex_prism_on(S, sgn * u, v, top_off(u, v) - 0.03, radius=0.185, h=0.14))
    # mouth slit (glow) with end brackets, chin ticks
    us = np.linspace(-2.0, 2.0, 22)
    w = np.interp(np.abs(us), [0, 1.2, 2.0], [0.2, 0.15, 0.07])
    pts = np.column_stack([us, np.full_like(us, 61.4)])
    P, N = S.pt(pts[:, 0], pts[:, 1], top_off(us, 61.4) + 0.05)
    glow.append(ag.strip_solid(P, N, w, 0.07))
    for sgn in (+1, -1):
        black.append(pn.ribbon(S, [[sgn * 2.15, 61.75], [sgn * 2.15, 61.05]], 0.12, 0.1, top_off(2.1, 61.4) + 0.05))
    for k in range(5):
        u = (k - 2) * 0.32
        glow.append(pn.ribbon(S, [[u, 60.55], [u, 60.2 - 0.0]], 0.07, 0.05, top_off(u, 60.4) + 0.2 + 0.03))
    # nostril vents
    for sgn in (+1, -1):
        for k in range(3):
            black.append(pn.ribbon(S, [[sgn * 0.45, 63.55 - 0.2 * k], [sgn * 0.95, 63.45 - 0.2 * k]], 0.07, 0.06, top_off(0.6, 63.5) + 0.06))

    # side filters: ribbed canisters with a glowing front ring
    for sgn in (+1, -1):
        p, n, tu, tv = pn.frame_at(S, sgn * 4.25, filter_v, top_off(4.25, filter_v) - 0.1)
        # canister axis: the surface normal tilted forward a little
        d = unit(n + np.array([0.35, 0.0, 0.0]))
        ref = np.array([0.0, 0.0, 1.0])
        x = unit(np.cross(ref, d))
        y = np.cross(d, x)
        R = np.stack([x, y, d], 1)
        gun.append(ag.cone(0.74, 0.68, 0.95, sides=24).transform(R=R, t=p))
        for k in (0.18, 0.5, 0.82):
            gray.append(ag.cone(0.8, 0.8, 0.08, sides=24).transform(R=R, t=p + d * 0.95 * k))
        black.append(ag.cone(0.55, 0.55, 0.1, sides=20).transform(R=R, t=p + d * 0.93))
        glow.append(mg.torus(0.47, 0.05, nu=28, nv=8).transform(R=R, t=p + d * 1.0))
        glow.append(ag.cone(0.12, 0.12, 0.08, sides=10).transform(R=R, t=p + d * 1.0))

    # ------------------------------------------------------------------ right-eye cyber implant
    cu, cv = eye_u, eye_v
    ring = pn.ellipse_poly((cu, cv), 1.02, 0.82, n=40)
    black.append(pn.ribbon_loop(S, ring, 0.34, 0.34, 0.55))
    glow.append(pn.ribbon_loop(S, pn.ellipse_poly((cu, cv), 0.8, 0.62, n=40), 0.07, 0.06, 0.62))
    for k in range(8):
        t = k * np.pi / 4
        a = np.array([cu + 1.18 * np.cos(t), cv + 0.95 * np.sin(t)])
        b = np.array([cu + 1.36 * np.cos(t), cv + 1.1 * np.sin(t)])
        gray.append(pn.ribbon(S, [a, b], 0.09, 0.2, 0.55))
    pl, nl, tul, tvl = pn.frame_at(S, cu, cv, 0.48)
    Rl = np.stack([tul, tvl, nl], 1)
    lens.append(ag.cone(0.66, 0.6, 0.12, sides=28).transform(R=Rl, t=pl))
    # side module + antenna at the outer corner
    pm, nm, tum, tvm = pn.frame_at(S, -2.75, 65.35, 0.5)
    Rm = np.stack([tum, tvm, nm], 1)
    gray.append(ag.box((0.9, 0.5, 0.34), rc=0.08).transform(R=Rm, t=pm + nm * 0.12))
    for k in range(3):
        glow.append(ag.cone(0.07, 0.07, 0.06, sides=8).transform(R=Rm, t=pm + nm * 0.32 + tum * (-0.3 + 0.3 * k)))
    pa, na, tua, tva = pn.frame_at(S, -3.0, 65.55, 0.55)
    ant = ag.catmull(np.array([pa, pa + np.array([-0.2, -0.45, 1.0]), pa + np.array([-0.7, -0.7, 2.4]), pa + np.array([-1.5, -0.9, 3.6])]), 14)
    gray.append(ag.tube_path(ant, 0.05, sides=6))
    glow.append(ag.cone(0.1, 0.1, 0.12, sides=10).transform(R=np.eye(3), t=ant[-1]))
    # scan line from the implant across the cheek
    glow.append(pn.ribbon(S, [[cu - 1.05, cv - 0.05], [-3.6, 65.0]], 0.05, 0.05, 0.66))

    # ------------------------------------------------------------------ ear cups, strap to the mask, headset arc
    for sgn in (+1, -1):
        c = np.array([cup_x, cup_y * sgn, cup_z])
        Rr = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, sgn * 1.0, 0]])
        gun.append(ag.cone(1.65, 1.5, 0.8, sides=28).transform(R=Rr, t=c))
        glow.append(mg.torus(1.12, 0.09, nu=36, nv=8).transform(R=Rr, t=c + np.array([0, sgn * 0.44, 0])))
        black.append(ag.cone(0.85, 0.85, 0.12, sides=20).transform(R=Rr, t=c + np.array([0, sgn * 0.42, 0])))
        gray.append(ag.cone(0.42, 0.42, 0.22, sides=14).transform(R=Rr, t=c + np.array([0, sgn * 0.5, 0])))
    arc_t = np.linspace(0, np.pi, 40)
    arc = np.column_stack([np.full_like(arc_t, cup_x), (cup_y + 0.1) * np.cos(arc_t), (cup_z + 0.8) + (arc_top - cup_z - 0.8) * np.sin(arc_t)])
    gray.append(ag.tube_path(arc, 0.2, sides=8))
    glow.append(ag.tube_path(arc + np.array([0.0, 0.0, 0.0]) + np.array([0.12, 0.0, 0.0]), 0.05, sides=6))

    parts = {
        'black': dict(mesh=ag.merge(black), color=BLACK, rough=0.55, smooth=40),
        'gray': dict(mesh=ag.merge(gray), color=GRAPH, rough=0.4, metal=0.3, smooth=40),
        'gun': dict(mesh=ag.merge(gun), color=GUN, rough=0.3, metal=0.7, smooth=38),
        'glow': dict(mesh=ag.merge(glow), color=GLOW, nolight=True, smooth=60),
        'lens': dict(mesh=ag.merge(lens), color=LENS, rough=0.1, alpha=0.4, smooth=50),
    }
    return parts, dict(surf=S, cyl=cyl)
