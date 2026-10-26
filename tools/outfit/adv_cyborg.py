"""Protocol Unit (cyborg Ethics Assistant) geometry: left half of the face replaced by a chrome endoskeleton (brow plate, eye socket with a lens, cheek plates around a mechanism window, exposed
steel jaw with a piston), neck collar with hoses, a heavy left arm (pauldron, elbow ball, gauntlet, hand plate) and a back reactor with cooling fins, vents and cables.
World frame, bind pose.  build_cyborg(scene) -> (parts, ctx)."""
import numpy as np

import adv_geom as ag
import adv_panels as pn
import meshgen as mg
from adv_geom import unit

CHROME = (196, 202, 214)
DARK = (30, 32, 40)
STEEL = (132, 138, 152)
GLOW = (255, 150, 30)


def org(rig, name):
    return rig.world[rig.idx['ValveBiped.Bip01_' + name]][:3, 3]


# ------------------------------------------------------------------------------------------------------------------------------ left half of the face
def make_face(sc):
    cyl = ag.Cyl(sc.S_head, axis_xy=(0.4, 0.0), z0=56.0, z1=73.0)
    S = pn.HeadSurf(cyl, max_dev=1.2)
    chrome, dark, glow, steel = [], [], [], []
    UNDER = 0.3

    def plate(poly, off1=0.85, bevel=0.2, n_bev=1, profile='chamfer', cut=0.22, **kw):
        chrome.append(pn.plateau(S, pn.cut_poly(np.asarray(poly, float), cut), UNDER, off1, bevel, step=0.22, n_in=4, profile=profile, n_bev=n_bev, **kw))

    # dark mechanism layer under everything on the left half
    under = np.array([[0.2, 68.4], [3.0, 68.4], [5.0, 67.4], [5.7, 65.6], [5.8, 63.0], [5.0, 60.8], [3.4, 59.7], [1.2, 59.3], [0.2, 59.4]])
    dark.append(pn.plateau(S, pn.cut_poly(under, 0.3), 0.1, UNDER, 0.12, step=0.25, n_in=5, profile='chamfer', n_bev=1))
    # plates
    plate([[0.45, 68.2], [2.6, 68.1], [4.4, 67.2], [5.5, 66.0], [5.4, 65.4], [4.3, 65.8], [2.8, 66.35], [1.3, 66.45], [0.45, 66.3]], off1=0.95)                    # brow / forehead
    plate([[0.5, 64.3], [2.2, 64.55], [3.9, 64.75], [5.3, 63.8], [5.4, 63.2], [3.9, 63.4], [2.2, 63.5], [0.6, 63.55]], off1=0.85)                                   # upper cheek
    plate([[0.5, 62.9], [2.6, 62.8], [4.2, 62.5], [5.2, 61.8], [4.7, 60.5], [3.3, 59.9], [1.6, 59.7], [0.5, 60.2]], off1=0.9)                                       # lower cheek / jaw
    plate([[0.45, 63.2], [2.4, 63.1], [2.9, 62.65], [0.45, 62.65]], off1=0.8, bevel=0.1, cut=0.1)                                                                   # upper lip
    # eye socket with a glowing lens
    cu, cv = 1.45, 65.12
    ring = pn.ellipse_poly((cu, cv), 1.0, 0.8, n=36)
    dark.append(pn.ribbon_loop(S, ring, 0.38, 0.36, 0.6))
    chrome.append(pn.ribbon_loop(S, pn.ellipse_poly((cu, cv), 0.8, 0.62, n=36), 0.1, 0.1, 0.72))
    pl, nl, tul, tvl = pn.frame_at(S, cu, cv, 0.5)
    Rl = np.stack([tul, tvl, nl], 1)
    glow.append(ag.cone(0.55, 0.5, 0.2, sides=24).transform(R=Rl, t=pl))
    dark.append(ag.cone(0.28, 0.26, 0.24, sides=14).transform(R=Rl, t=pl + nl * 0.06))
    # mechanism window between the cheek plates: rods and pistons
    for k, v in enumerate((63.05, 62.85)):
        steel.append(pn.ribbon(S, [[0.8, v], [4.8, v - 0.12]], 0.12, 0.12, 0.62))
    for u in (1.2, 2.2, 3.2, 4.2):
        steel.append(pn.ribbon(S, [[u, 63.4], [u + 0.1, 62.65]], 0.1, 0.1, 0.66))
        glow.append(ag.cone(0.08, 0.08, 0.1, sides=8).transform(R=np.eye(3), t=pn.frame_at(S, u, 63.0, 0.72)[0]))
    # piston from the cheek to the jaw angle
    p0, n0, _, _ = pn.frame_at(S, 4.9, 63.6, 1.0)
    p1, n1, _, _ = pn.frame_at(S, 4.7, 61.2, 1.0)
    steel.append(ag.tube_path(np.array([p0, 0.5 * (p0 + p1) + n0 * 0.15, p1]), 0.16, sides=8))
    dark.append(ag.tube_path(np.array([p0 + (p1 - p0) * 0.05, p0 + (p1 - p0) * 0.5]), 0.3, sides=10))
    # exposed steel teeth: upper row hanging from the lip plate, lower row rising from the jaw plate
    for u in np.linspace(0.45, 2.7, 9):
        p, n, tu, tv = pn.frame_at(S, u, 62.68, 0.8)
        steel.append(ag.box((0.28, 0.26, 0.5), rc=0.03).transform(R=np.stack([tu, tv, n], 1), t=p + tv * -0.18))
        p2, n2, tu2, tv2 = pn.frame_at(S, u + 0.1, 62.82, 0.82)
        steel.append(ag.box((0.26, 0.24, 0.42), rc=0.03).transform(R=np.stack([tu2, tv2, n2], 1), t=p2 + tv2 * 0.12))
    # screws + panel lines
    for (u, v) in ((0.9, 67.7), (3.6, 67.4), (4.9, 66.2), (1.1, 64.0), (4.2, 64.2), (4.9, 63.7), (4.5, 61.2), (2.4, 60.5), (0.9, 60.6)):
        steel.append(pn.bolt(S, u, v, 0.92, radius=0.12, h=0.07))
    dark.append(pn.ribbon(S, [[0.6, 67.4], [2.0, 67.7], [3.8, 67.0], [5.0, 66.0]], 0.07, 0.06, 0.99))
    dark.append(pn.ribbon(S, [[1.0, 61.4], [3.0, 61.5], [4.4, 61.0]], 0.07, 0.06, 0.95))
    # glow: the split line down the middle of the face, brow LED, cheek LEDs
    glow.append(pn.ribbon(S, [[0.18, 68.3], [0.18, 66.2]], 0.07, 0.07, 0.5))
    glow.append(pn.ribbon(S, [[0.18, 64.2], [0.18, 62.9]], 0.07, 0.07, 0.5))
    glow.append(pn.ribbon(S, [[0.18, 62.4], [0.18, 59.6]], 0.07, 0.07, 0.5))
    glow.append(pn.ribbon(S, [[1.0, 67.8], [2.5, 68.0], [4.0, 67.3], [5.0, 66.4]], 0.06, 0.05, 1.0))
    glow.append(pn.ribbon(S, [[3.2, 64.5], [4.6, 64.5]], 0.06, 0.05, 0.9))
    # left ear: a small gunmetal cup with a glow ring (the human ear is on the right)
    c = np.array([-0.3, 3.75, 65.2])
    Rr = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]])
    steel.append(ag.cone(1.5, 1.35, 0.7, sides=26).transform(R=Rr, t=c))
    glow.append(mg.torus(1.0, 0.08, nu=32, nv=8).transform(R=Rr, t=c + np.array([0, 0.4, 0])))
    ant = ag.catmull(np.array([c + [0.4, 0.2, 1.2], c + [0.2, 0.0, 3.0], c + [-0.5, -0.2, 4.6]]), 12)
    steel.append(ag.tube_path(ant, 0.05, sides=6))
    glow.append(ag.cone(0.1, 0.1, 0.12, sides=8).transform(R=np.eye(3), t=ant[-1]))
    return ag.merge(chrome), ag.merge(dark), ag.merge(glow), ag.merge(steel), S


# ------------------------------------------------------------------------------------------------------------------------------ neck collar
def make_collar(rig):
    n = org(rig, 'Neck1')
    z = 60.7
    c = np.array([-1.15, 0.0, z])
    out_dark, out_chrome = [], []
    out_dark.append(mg.torus(2.35, 0.5, nu=40, nv=10).transform(R=np.eye(3), t=c))
    out_chrome.append(mg.torus(2.4, 0.18, nu=40, nv=8).transform(R=np.eye(3), t=c + np.array([0, 0, 0.7])))
    out_chrome.append(mg.torus(2.4, 0.14, nu=40, nv=8).transform(R=np.eye(3), t=c + np.array([0, 0, -0.55])))
    for sgn in (+1, -1):
        pts = np.array([[-0.3, sgn * 2.3, 61.0], [-0.6, sgn * 2.7, 59.8], [-1.2, sgn * 3.0, 58.4], [-1.9, sgn * 3.1, 57.3]])
        out_dark.append(ag.tube_path(ag.catmull(pts, 16), 0.26, sides=8))
    pts = np.array([[-3.3, 0.0, 61.5], [-3.7, 0.0, 59.5], [-4.1, 0.0, 57.5]])
    out_chrome.append(ag.box((0.5, 1.6, 2.6), rc=0.1).transform(R=np.eye(3), t=np.array([-3.4, 0.0, 60.2])))
    return ag.merge(out_dark), ag.merge(out_chrome)


# ------------------------------------------------------------------------------------------------------------------------------ left arm
def make_arm(sc):
    rig = sc.rig
    sh, el, wr = org(rig, 'L_UpperArm'), org(rig, 'L_Forearm'), org(rig, 'L_Hand')
    U = pn.TubeSurf(sc.S_suit, sh, el, up_hint=(0, 0, 1.0), n_v=44, n_th=96, r0=2.0, smooth=4, rmax=7.0, v_pad=2.5)
    F = pn.TubeSurf(sc.S_suit, el, wr, up_hint=(0, 0, 1.0), n_v=44, n_th=96, r0=1.7, smooth=4, rmax=6.0, v_pad=1.0)
    uc, ug, fc, fg = [], [], [], []

    def plate(T, store, poly, off0, off1, bevel=0.18, cut=0.3, **kw):
        store.append(pn.plateau(T, pn.cut_poly(np.asarray(poly, float), cut), off0, off1, bevel, step=0.24, n_in=4, profile='chamfer', n_bev=1, **kw))

    # pauldron: a big domed plate over the shoulder and the top of the arm
    plate(U, uc, pn.rect_poly(-3.5, 3.5, -2.2, 5.2), 0.3, 1.5, bevel=0.35, cut=0.7, dome=0.7)
    plate(U, uc, pn.rect_poly(-3.2, 3.2, 5.45, 7.6), 0.3, 1.0, bevel=0.2, cut=0.4)
    plate(U, uc, pn.rect_poly(-2.6, 2.6, 7.85, 9.6), 0.3, 0.85, bevel=0.18, cut=0.35)
    for v in (5.32, 7.72):
        ug.append(pn.ribbon(U, [[u, v] for u in np.linspace(-3.4, 3.4, 14)], 0.09, 0.07, 0.42))
    for k in range(3):
        ug.append(pn.ribbon(U, [[-1.6, 1.0 + 1.3 * k], [1.6, 1.0 + 1.3 * k]], 0.07, 0.06, 1.62))
    ug.append(pn.ribbon(U, [[0.0, 5.6], [0.0, 7.4]], 0.08, 0.06, 1.05))
    # shoulder ridge + rivets
    uc.append(pn.ribbon(U, [[0.0, -1.8], [0.0, 4.6]], 0.5, 0.3, 1.6))
    for (u, v) in ((-3.0, 4.6), (3.0, 4.6), (-3.0, -1.4), (3.0, -1.4), (-2.4, 6.0), (2.4, 6.0)):
        uc.append(pn.bolt(U, u, v, 1.1, radius=0.14, h=0.08))
    # elbow ball joint + glowing ring (axis along the arm's top direction)
    e1 = U.e1
    uc.append(mg.ellipsoid((1.2, 1.2, 1.2), nu=18, nv=12).transform(t=el))
    ug.append(mg.torus(1.5, 0.09, nu=36, nv=8).transform(R=np.stack([unit(np.cross(e1, U.ax)), U.ax, e1], 1), t=el))
    # forearm gauntlet: two shells (top / underside), seams, vents, side pistons
    plate(F, fc, pn.rect_poly(-2.3, 2.3, 1.9, 4.8), 0.3, 0.75, cut=0.35)
    plate(F, fc, pn.rect_poly(-2.3, 2.3, 5.1, 7.4), 0.3, 0.8, cut=0.35)
    plate(F, fc, pn.rect_poly(-2.1, 2.1, 7.7, 9.6), 0.3, 0.7, cut=0.3)
    plate(F, fc, pn.rect_poly(5.4 - 1.7 * 3.14159 + 1.0, 5.4 + 1.7 * 3.14159 - 1.0, 2.0, 9.4), 0.25, 0.6, bevel=0.14, cut=0.5)       # underside half shell (u around +-pi)
    fc.append(pn.ribbon(F, [[0.0, 2.2], [0.0, 9.3]], 0.3, 0.2, 0.9))
    for v in (4.95, 7.55):
        fg.append(pn.ribbon(F, [[u, v] for u in np.linspace(-2.4, 2.4, 14)], 0.09, 0.07, 0.4))
    for k in range(4):
        fg.append(pn.ribbon(F, [[-0.8, 5.35 + 0.35 * k], [0.8, 5.35 + 0.35 * k]], 0.06, 0.05, 0.84))
    fg.append(pn.ribbon(F, [[-1.0, 9.0], [0.0, 8.2], [1.0, 9.0]], 0.09, 0.06, 0.78))
    for sgn in (+1, -1):
        p0 = F.pt(np.array([sgn * 2.2]), np.array([2.4]), np.array([0.62]))[0][0]
        p1 = F.pt(np.array([sgn * 2.2]), np.array([8.8]), np.array([0.62]))[0][0]
        fc.append(ag.tube_path(np.array([p0, 0.5 * (p0 + p1), p1]), 0.14, sides=8))
        fc.append(ag.tube_path(np.array([p0, p0 + (p1 - p0) * 0.45]), 0.24, sides=10))
    for ring_v, off in ((1.7, 0.5), (9.85, 0.42)):
        u = np.linspace(-np.pi * F.R0, np.pi * F.R0, 72, endpoint=False)
        u = np.concatenate([u, u[:2]])
        P, N = F.pt(u, np.full_like(u, ring_v), off)
        fc.append(ag.strip_solid(P, N, 0.36, 0.34, cap=False))
    # hand plate
    H = pn.TubeSurf(sc.S_hands, wr, org(rig, 'L_Finger2'), up_hint=(0, 1.0, 0.3), r0=1.0, n_v=26, n_th=96, rmax=4.0, smooth=3)
    hc, hg = [], []
    back = np.array([[-0.8, 0.2], [0.8, 0.2], [1.25, 1.4], [1.45, 3.0], [0.0, 3.55], [-1.45, 3.0], [-1.25, 1.4]])
    hc.append(pn.plateau(H, pn.cut_poly(back, 0.22), 0.1, 0.42, 0.14, step=0.2, n_in=3, profile='chamfer', n_bev=1))
    hc.append(pn.ribbon(H, [[-1.55, 3.3], [0.0, 3.45], [1.55, 3.3]], 0.38, 0.22, 0.5))
    for u in (-0.95, 0.0, 0.95):
        hc.append(pn.hex_prism_on(H, u, 3.4, 0.6, radius=0.22, h=0.16))
    hg.append(pn.ribbon(H, [[-0.4, 0.5], [-0.4, 2.2], [-0.8, 2.8]], 0.05, 0.05, 0.48))
    hg.append(pn.ribbon(H, [[0.4, 0.5], [0.4, 2.2], [0.8, 2.8]], 0.05, 0.05, 0.48))
    return dict(upper_chrome=ag.merge(uc), upper_glow=ag.merge(ug), fore_chrome=ag.merge(fc), fore_glow=ag.merge(fg), hand_chrome=ag.merge(hc), hand_glow=ag.merge(hg)), dict(U=U, F=F, H=H, elbow=el)


# ------------------------------------------------------------------------------------------------------------------------------ back reactor
def make_back(sc):
    S = sc.S_suit
    zc = 51.0
    bx = float(S.back(0.0, zc)[0][0]) - 0.1
    centre = np.array([bx - 1.7, 0.0, zc])
    dark, chrome, glow = [], [], []
    dark.append(ag.box((3.0, 5.6, 9.0), rc=0.6).transform(R=np.eye(3), t=centre))
    # cooling fins on both flanks
    for sgn in (+1, -1):
        for k in range(7):
            z = zc - 3.6 + 1.2 * k
            chrome.append(ag.box((2.6, 0.2, 0.7), rc=0.04).transform(R=np.eye(3), t=np.array([centre[0], sgn * 3.0, z])))
    # core: ring + glowing disc on the back face
    cb = centre + np.array([-1.55, 0, 0.3])
    Rb = np.array([[0, 0, -1.0], [0, 1.0, 0], [1.0, 0, 0]])           # local z -> world -x
    chrome.append(mg.torus(1.7, 0.28, nu=40, nv=10).transform(R=Rb, t=cb))
    glow.append(ag.cone(1.2, 1.2, 0.2, sides=30).transform(R=Rb, t=cb + np.array([-0.05, 0, 0])))
    glow.append(mg.torus(1.45, 0.07, nu=40, nv=8).transform(R=Rb, t=cb + np.array([-0.28, 0, 0])))
    dark.append(ag.cone(0.55, 0.55, 0.3, sides=14).transform(R=Rb, t=cb + np.array([-0.2, 0, 0])))
    # glowing seam lines on the housing
    for z in (zc + 3.9, zc - 3.5):
        glow.append(ag.box((0.2, 4.6, 0.12), rc=0.02).transform(R=np.eye(3), t=np.array([centre[0] - 1.45, 0, z])))
    # exhaust vents on top (tilted outward and back)
    vents = []
    for sgn in (+1, -1):
        base = np.array([centre[0] - 0.2, sgn * 1.7, zc + 4.4])
        d = unit(np.array([-0.35, sgn * 0.35, 1.0]))
        ref = np.array([0.0, 1.0, 0.0])
        x = unit(np.cross(ref, d))
        y = np.cross(d, x)
        R = np.stack([x, y, d], 1)
        chrome.append(ag.cone(0.75, 0.62, 2.4, sides=18).transform(R=R, t=base))
        chrome.append(ag.cone(0.85, 0.85, 0.3, sides=18).transform(R=R, t=base + d * 2.1))
        dark.append(ag.cone(0.45, 0.45, 0.2, sides=14).transform(R=R, t=base + d * 2.5))
        vents.append(base + d * 2.6)
    # cable bundle up to the collar and struts to the shoulders
    for k, y in enumerate((-0.7, 0.0, 0.7)):
        pts = np.array([[centre[0] + 0.2, y, zc + 4.6], [centre[0] + 0.5, y * 1.2, zc + 7.0], [-3.4, y * 0.9, 59.6], [-2.6, y * 0.6, 61.0]])
        dark.append(ag.tube_path(ag.catmull(pts, 18), 0.22, sides=8))
    for sgn in (+1, -1):
        pts = np.array([[centre[0] + 0.3, sgn * 2.6, zc + 3.4], [centre[0] + 0.6, sgn * 4.0, zc + 5.2], [-3.0, sgn * 5.2, 56.4]])
        chrome.append(ag.tube_path(ag.catmull(pts, 14), 0.3, sides=9))
    return ag.merge(dark), ag.merge(chrome), ag.merge(glow), vents, centre


def build_cyborg(sc):
    chrome, dark, glow, steel, S = make_face(sc)
    collar_dark, collar_chrome = make_collar(sc.rig)
    arm, actx = make_arm(sc)
    back_dark, back_chrome, back_glow, vents, back_c = make_back(sc)
    parts = {
        'face_chrome': dict(mesh=ag.merge([chrome, steel]), color=CHROME, rough=0.25, metal=0.85, smooth=42),
        'face_dark': dict(mesh=dark, color=DARK, rough=0.5, smooth=40),
        'face_glow': dict(mesh=glow, color=GLOW, nolight=True, smooth=60),
        'collar': dict(mesh=ag.merge([collar_dark, collar_chrome]), color=(60, 62, 72), rough=0.4, metal=0.6, smooth=45),
        'upper_chrome': dict(mesh=arm['upper_chrome'], color=CHROME, rough=0.25, metal=0.85, smooth=42),
        'upper_glow': dict(mesh=arm['upper_glow'], color=GLOW, nolight=True, smooth=60),
        'fore_chrome': dict(mesh=arm['fore_chrome'], color=CHROME, rough=0.25, metal=0.85, smooth=42),
        'fore_glow': dict(mesh=arm['fore_glow'], color=GLOW, nolight=True, smooth=60),
        'hand_chrome': dict(mesh=arm['hand_chrome'], color=CHROME, rough=0.25, metal=0.85, smooth=42),
        'hand_glow': dict(mesh=arm['hand_glow'], color=GLOW, nolight=True, smooth=60),
        'back_body': dict(mesh=ag.merge([back_dark, back_chrome]), color=(90, 94, 106), rough=0.35, metal=0.7, smooth=42),
        'back_glow': dict(mesh=back_glow, color=GLOW, nolight=True, smooth=60),
    }
    return parts, dict(surf=S, vents=vents, back_centre=back_c, arm=actx)
