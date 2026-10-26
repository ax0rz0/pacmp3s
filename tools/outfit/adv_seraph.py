"""Neon Seraph geometry: segmented data-wings (primary / secondary feathers, coverts, glowing edge lines, a hinge mount), a translucent cyber visor, angular shoulder fins and a ring of holographic
panels for the left forearm.  World frame, bind pose.  build_seraph(scene) -> (parts, ctx)."""
import numpy as np

import adv_geom as ag
import adv_panels as pn
import meshgen as mg
from adv_geom import unit

PEARL = (236, 240, 250)
CHROME = (200, 206, 218)
GLOW = (40, 220, 255)
LENS = (60, 200, 255)

# wing root (left wing; the right wing is the mirror image)
ROOT = np.array([-4.0, 2.3, 55.8])


def lock(path, w, th, up, sides=6, cap=True):
    sc = np.column_stack([np.asarray(w) / 2.0, np.asarray(th) / 2.0])
    return ag.loft(np.asarray(path, float), ag.circle(sides, 1.0, 1.0), scale=sc, up_hint=np.asarray(up, float), cap_start=cap, cap_end=True)


def taper(n, w0, w1=0.05, power=0.8):
    s = np.linspace(0, 1, n)
    return w1 + (w0 - w1) * (1 - s) ** power


def frame_path(n=40):
    pts = np.array([[0, 0, 0], [-1.2, 5.5, 8.5], [-2.6, 14.0, 13.5], [-3.8, 24.0, 11.0]], float)
    return ROOT + ag.catmull(pts, n)


def feather_path(root, d, L, bend, n=12):
    s = np.linspace(0, 1, n)[:, None]
    back = np.array([-1.0, 0.0, 0.0])
    return root + d[None, :] * L * s + back[None, :] * bend * L * s ** 2


def make_wing(rng):
    prim, sec, cov, glow = [], [], [], []
    fp = frame_path()
    n = len(fp)

    def at(t):
        i = t * (n - 1)
        i0 = int(np.floor(i))
        i1 = min(i0 + 1, n - 1)
        return fp[i0] * (1 - (i - i0)) + fp[i1] * (i - i0)

    # leading-edge arm (glowing tube) + joints
    glow.append(ag.tube_path(fp, 0.14, sides=8))
    for t in (0.0, 0.35, 0.7, 1.0):
        glow.append(mg.ellipsoid((0.45, 0.45, 0.45), nu=12, nv=8).transform(t=at(t)))
    # primary feathers
    for k in range(13):
        t = 0.3 + 0.7 * k / 12.0
        d = unit(np.array([-0.25 - 0.15 * t, 0.12 + 0.85 * t ** 1.15, -1.0 + 0.4 * t]))
        L = (11.0 + 27.0 * np.sin(np.pi * (0.22 + 0.78 * t)) ** 0.9) * (0.62 + 0.38 * t)
        path = feather_path(at(t), d, L, 0.14 + 0.06 * t)
        m = len(path)
        w = taper(m, 3.4 - 0.5 * t, 0.35, 0.85)
        up = np.cross(d, np.array([1.0, 0.0, 0.0]))
        prim.append(lock(path, w, np.full(m, 0.13), up if np.linalg.norm(up) > 1e-6 else (0, 1, 0)))
        # glowing edge line along the outer side of each feather
        side = unit(np.cross(d, np.array([-1.0, 0.0, 0.0])))
        edge = path + side[None, :] * (w[:, None] * 0.5)
        glow.append(ag.tube_path(edge[1:-1], 0.045, sides=5))
    # secondary feathers (shorter, inboard and lower)
    for k in range(11):
        t = 0.08 + 0.6 * k / 10.0
        d = unit(np.array([-0.45, 0.08 + 0.4 * t, -1.0]))
        L = (7.0 + 8.0 * np.sin(np.pi * (0.1 + 0.9 * t))) * (0.9 + 0.2 * rng.rand())
        r0 = at(t) + np.array([-0.7, 0.0, -0.4])
        path = feather_path(r0, d, L, 0.1)
        m = len(path)
        w = taper(m, 2.8, 0.3, 0.8)
        sec.append(lock(path, w, np.full(m, 0.12), np.cross(d, np.array([1.0, 0.0, 0.0]))))
    # coverts: small rounded plates along the top of the arm
    for k in range(15):
        t = 0.04 + 0.78 * k / 14.0
        d = unit(np.array([-0.3, 0.3 + 0.5 * t, -0.9]))
        path = feather_path(at(t) + np.array([-0.3, 0.0, 0.2]), d, 3.6 + 1.2 * np.sin(np.pi * t), 0.1, n=6)
        m = len(path)
        cov.append(lock(path, taper(m, 2.2, 0.5, 0.5), np.full(m, 0.16), np.cross(d, np.array([1.0, 0.0, 0.0])), sides=5))
    # hinge mount: a plate on the back + cylinder at the root
    mount = [ag.cone(1.0, 1.0, 2.2, sides=16).transform(R=np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]]), t=ROOT + np.array([0.4, -0.9, 0.0]))]
    mount.append(ag.box((1.2, 3.4, 3.8), rc=0.35).transform(R=np.eye(3), t=ROOT + np.array([0.9, -0.8, -0.4])))
    return ag.merge(prim + sec + cov + mount), ag.merge(glow)


# ------------------------------------------------------------------------------------------------------------------------------ visor
def make_visor(sc):
    cyl = ag.Cyl(sc.S_head, axis_xy=(0.4, 0.0), z0=56.0, z1=73.0)
    S = pn.HeadSurf(cyl, max_dev=1.2)
    lens, frame, glow = [], [], []
    band = np.array([[-5.1, 64.3], [-3.4, 64.15], [0.0, 64.1], [3.4, 64.15], [5.1, 64.3], [5.4, 65.7], [3.6, 66.1], [0.0, 66.15], [-3.6, 66.1], [-5.4, 65.7]])
    lens.append(pn.plateau(S, pn.cut_poly(band, 0.3), 0.2, 0.75, 0.3, step=0.22, n_in=6, profile='fillet', n_bev=3, dome=0.1))
    # frame + glow lines
    top = np.array([[-5.2, 65.9], [-3.6, 66.3], [0.0, 66.35], [3.6, 66.3], [5.2, 65.9]])
    bot = np.array([[-5.0, 64.2], [-3.4, 64.0], [0.0, 63.95], [3.4, 64.0], [5.0, 64.2]])
    frame.append(pn.ribbon(S, pn.densify_open(top, 0.2), 0.32, 0.3, 0.8))
    frame.append(pn.ribbon(S, pn.densify_open(bot, 0.2), 0.26, 0.26, 0.78))
    glow.append(pn.ribbon(S, pn.densify_open(top, 0.2), 0.07, 0.07, 0.98))
    glow.append(pn.ribbon(S, pn.densify_open(bot, 0.2), 0.06, 0.06, 0.94))
    frame.append(pn.ribbon(S, [[0.0, 66.2], [0.0, 64.0]], 0.45, 0.3, 0.84))
    for sgn in (+1, -1):
        mod = pn.frame_at(S, sgn * 5.3, 65.1, 0.8)
        R = np.stack([mod[2], mod[3], mod[1]], 1)
        frame.append(ag.box((1.5, 1.2, 0.5), rc=0.12).transform(R=R, t=mod[0]))
        for k in range(3):
            glow.append(ag.cone(0.09, 0.09, 0.1, sides=8).transform(R=R, t=mod[0] + mod[1] * 0.3 + mod[2] * (-0.4 + 0.4 * k)))
    # forehead crest: an angular chevron
    crest = np.array([[-1.6, 67.0], [0.0, 68.6], [1.6, 67.0], [0.8, 67.0], [0.0, 67.8], [-0.8, 67.0]])
    frame.append(pn.plateau(S, crest, 0.2, 0.7, 0.15, step=0.15, n_in=3, profile='chamfer', n_bev=1, centre=np.array([0.0, 67.6])))
    glow.append(pn.ribbon(S, [[-1.1, 67.25], [0.0, 68.2], [1.1, 67.25]], 0.06, 0.05, 0.72))
    return ag.merge(lens), ag.merge(frame), ag.merge(glow), S


# ------------------------------------------------------------------------------------------------------------------------------ shoulder fins (left side; mirrored for the right)
def make_shoulder(sc):
    rig = sc.rig
    sh = rig.world[rig.idx['ValveBiped.Bip01_L_UpperArm']][:3, 3]
    el = rig.world[rig.idx['ValveBiped.Bip01_L_Forearm']][:3, 3]
    U = pn.TubeSurf(sc.S_suit, sh, el, up_hint=(0, 0, 1.0), n_v=44, n_th=96, r0=2.0, smooth=4, rmax=7.0, v_pad=2.5)
    white, glow = [], []
    white.append(pn.plateau(U, pn.cut_poly(pn.rect_poly(-3.3, 3.3, -2.0, 4.8), 0.6), 0.3, 1.1, 0.3, step=0.24, n_in=4, profile='chamfer', n_bev=1, dome=0.45))
    white.append(pn.ribbon(U, [[0.0, -1.8], [0.0, 4.4]], 0.4, 0.3, 1.2))
    glow.append(pn.ribbon(U, [[-2.6, 4.9], [2.6, 4.9]], 0.08, 0.06, 0.45))
    glow.append(pn.ribbon(U, [[-1.2, -1.2], [-1.2, 3.8]], 0.06, 0.05, 1.18))
    glow.append(pn.ribbon(U, [[1.2, -1.2], [1.2, 3.8]], 0.06, 0.05, 1.18))
    # the fin: a tall angular blade rising from the top of the shoulder, swept back
    base, n_, tu, tv = pn.frame_at(U, 0.0, 1.0, 1.2)
    path = np.array([base, base + np.array([-0.8, 0.8, 3.2]), base + np.array([-2.2, 1.6, 6.0]), base + np.array([-4.2, 2.1, 7.8])])
    path = ag.catmull(path, 14)
    m = len(path)
    white.append(ag.blade(path, taper(m, 2.6, 0.2, 0.9), 0.22, up_hint=(1.0, 0.0, 0.0)))
    glow.append(ag.tube_path(path + np.array([0.0, 0.0, 0.0]) + np.array([0.12, 0.0, 0.0]), 0.05, sides=5))
    return ag.merge(white), ag.merge(glow)


# ------------------------------------------------------------------------------------------------------------------------------ holo panels around the left forearm
def make_holo(sc):
    rig = sc.rig
    el = rig.world[rig.idx['ValveBiped.Bip01_L_Forearm']][:3, 3]
    wr = rig.world[rig.idx['ValveBiped.Bip01_L_Hand']][:3, 3]
    ax = unit(wr - el)
    c = el + (wr - el) * 0.52
    ref = np.array([1.0, 0.0, 0.0])
    a = unit(np.cross(ax, ref))
    b = np.cross(ax, a)
    out = []
    for k in range(3):
        ang_ = k * 2 * np.pi / 3
        radial = np.cos(ang_) * a + np.sin(ang_) * b
        tang = np.cross(ax, radial)
        R = np.stack([tang, ax, radial], 1)                    # panel: local x = tangent, y = along the arm, z = radial normal
        centre = c + radial * 4.4
        W, H = 4.6, 3.4
        frame = [[-W / 2, -H / 2], [W / 2, -H / 2], [W / 2, H / 2], [-W / 2, H / 2], [-W / 2, -H / 2]]
        pts = np.array([centre + R @ np.array([x, y, 0.0]) for x, y in frame])
        out.append(ag.tube_path(pts, 0.05, sides=5, cap=True))
        for j in range(5):                                       # data bars
            h = 0.5 + 1.8 * rng_val(k * 7 + j)
            bx = -W / 2 + 0.55 + j * 0.8
            out.append(ag.box((0.4, h, 0.04), rc=0.0).transform(R=R, t=centre + R @ np.array([bx, -H / 2 + 0.4 + h / 2, 0.0])))
        for j in range(3):
            out.append(ag.box((W * 0.8, 0.06, 0.04), rc=0.0).transform(R=R, t=centre + R @ np.array([0.0, H / 2 - 0.5 - 0.35 * j, 0.0])))
    return ag.merge(out), c


WING_SCALE = 0.8


def scale_about(mesh, c, s):
    from meshgen import Mesh
    return Mesh(c + (mesh.V - c) * s, mesh.UV.copy(), mesh.F.copy())


def rng_val(i):
    return abs(np.sin(i * 12.9898) * 43758.5453) % 1.0


def build_seraph(sc):
    rng = np.random.RandomState(8)
    wing, wing_glow = make_wing(rng)
    wing = scale_about(wing, ROOT, WING_SCALE)
    wing_glow = scale_about(wing_glow, ROOT, WING_SCALE)
    lens, frame, vglow, S = make_visor(sc)
    sh_w, sh_g = make_shoulder(sc)
    holo, holo_c = make_holo(sc)
    parts = {
        'wing': dict(mesh=wing, color=PEARL, rough=0.35, metal=0.2, smooth=50),
        'wing_glow': dict(mesh=wing_glow, color=GLOW, nolight=True, smooth=60),
        'lens': dict(mesh=lens, color=LENS, rough=0.1, alpha=0.4, smooth=50),
        'visor_frame': dict(mesh=frame, color=CHROME, rough=0.3, metal=0.7, smooth=42),
        'visor_glow': dict(mesh=vglow, color=GLOW, nolight=True, smooth=60),
        'shoulder': dict(mesh=sh_w, color=PEARL, rough=0.35, metal=0.2, smooth=42),
        'shoulder_glow': dict(mesh=sh_g, color=GLOW, nolight=True, smooth=60),
        'holo': dict(mesh=holo, color=GLOW, nolight=True, smooth=60),
    }
    return parts, dict(surf=S, root=ROOT, holo_centre=holo_c)
