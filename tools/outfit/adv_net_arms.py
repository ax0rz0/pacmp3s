"""Netrunner cyber arms: segmented vambrace on the forearm (glowing seams, vents, rings) + a back-of-hand plate with knuckle studs.  Built for the LEFT arm in the in-game world frame
(bind pose); the right arm is the mirror image.  build_arm(scene) -> dict of world-space meshes: armor_f / glow_f (forearm bone), armor_h / glow_h (hand bone)."""
import numpy as np

import adv_geom as ag
import adv_panels as pn
import meshgen as mg
from adv_geom import unit

DARK = (30, 31, 39)
GLOW = (255, 30, 140)


def org(rig, name):
    return rig.world[rig.idx['ValveBiped.Bip01_' + name]][:3, 3]


def ring_around(T, v, width, thick, off, n=72):
    u = np.linspace(-np.pi * T.R0, np.pi * T.R0, n, endpoint=False)
    u = np.concatenate([u, u[:2]])
    P, N = T.pt(u, np.full_like(u, v), off)
    return ag.strip_solid(P, N, width, thick, cap=False)


def build_arm(sc):
    rig = sc.rig
    elbow, wrist = org(rig, 'L_Forearm'), org(rig, 'L_Hand')
    T = pn.TubeSurf(sc.S_suit, elbow, wrist, up_hint=(0, 0, 1.0), r0=1.7, n_v=44, n_th=96, rmax=6.0, smooth=4)
    armor_f, glow_f = [], []

    def plate(poly, off0, off1, bevel=0.15, **kw):
        armor_f.append(pn.plateau(T, pn.cut_poly(np.asarray(poly, float), 0.28), off0, off1, bevel, step=0.22, n_in=3, profile='chamfer', n_bev=1, **kw))

    # base shell under the plates
    armor_f.append(pn.plateau(T, pn.cut_poly(pn.rect_poly(-2.5, 2.5, 1.55, 9.95), 0.35), 0.1, 0.3, 0.12, step=0.25, n_in=3, profile='chamfer', n_bev=1))
    # three segmented plates
    plate(pn.rect_poly(-2.15, 2.15, 2.0, 4.6), 0.3, 0.62)
    plate(pn.rect_poly(-2.15, 2.15, 4.95, 7.25), 0.3, 0.66)
    plate(pn.rect_poly(-1.95, 1.95, 7.6, 9.6), 0.3, 0.6)
    # raised centre ridge over the top
    armor_f.append(pn.ribbon(T, [[0.0, 2.2], [0.0, 9.4]], 0.34, 0.24, 0.7))
    # glow: seams between the plates, vent slits, chevron near the wrist, top line segments
    for v in (4.78, 7.42):
        glow_f.append(pn.ribbon(T, [[u, v] for u in np.linspace(-2.25, 2.25, 14)], 0.09, 0.07, 0.4))
    for k in range(3):
        glow_f.append(pn.ribbon(T, [[-0.75, 5.5 + 0.38 * k], [0.75, 5.5 + 0.38 * k]], 0.06, 0.05, 0.7))
    glow_f.append(pn.ribbon(T, [[-0.95, 8.9], [0.0, 8.15], [0.95, 8.9]], 0.09, 0.06, 0.62))
    for (v0, v1) in ((2.4, 3.2), (3.5, 4.2), (5.4, 5.7)):
        pass
    glow_f.append(pn.ribbon(T, [[0.0, 2.5], [0.0, 4.4]], 0.07, 0.06, 0.76))
    # rings at both ends
    armor_f.append(ring_around(T, 1.75, 0.34, 0.34, 0.45))
    armor_f.append(ring_around(T, 9.85, 0.34, 0.34, 0.4))
    glow_f.append(ring_around(T, 9.55, 0.07, 0.07, 0.62))
    # bolts
    for (u, v) in ((-1.8, 2.3), (1.8, 2.3), (-1.8, 4.3), (1.8, 4.3), (-1.8, 5.2), (1.8, 5.2), (-1.8, 7.0), (1.8, 7.0)):
        armor_f.append(pn.bolt(T, u, v, 0.64, radius=0.11, h=0.07))

    # ------------------------------------------------------------ hand: plate on the back of the hand + knuckle studs
    mid = org(rig, 'L_Finger2')
    H = pn.TubeSurf(sc.S_hands, wrist, mid, up_hint=(0, 1.0, 0.3), r0=1.0, n_v=26, n_th=96, rmax=4.0, smooth=3)
    armor_h, glow_h = [], []
    back = np.array([[-0.75, 0.25], [0.75, 0.25], [1.2, 1.4], [1.4, 3.0], [0.0, 3.5], [-1.4, 3.0], [-1.2, 1.4]])
    armor_h.append(pn.plateau(H, pn.cut_poly(back, 0.2), 0.1, 0.34, 0.12, step=0.2, n_in=3, profile='chamfer', n_bev=1))
    armor_h.append(pn.ribbon(H, [[-1.5, 3.25], [0.0, 3.4], [1.5, 3.25]], 0.34, 0.2, 0.42))
    for u in (-0.9, 0.0, 0.9):
        armor_h.append(pn.hex_prism_on(H, u, 3.35, 0.5, radius=0.2, h=0.14))
    glow_h.append(pn.ribbon(H, [[-0.35, 0.5], [-0.35, 2.2], [-0.75, 2.8]], 0.05, 0.05, 0.4))
    glow_h.append(pn.ribbon(H, [[0.35, 0.5], [0.35, 2.2], [0.75, 2.8]], 0.05, 0.05, 0.4))
    pc, nc, tuc, tvc = pn.frame_at(H, 0.0, 1.3, 0.38)
    Rc = np.stack([tuc, tvc, nc], 1)
    glow_h.append(ag.cone(0.2, 0.2, 0.08, sides=14).transform(R=Rc, t=pc))
    armor_h.append(ag.cone(0.3, 0.3, 0.1, sides=14).transform(R=Rc, t=pc - nc * 0.02))

    return dict(armor_f=ag.merge(armor_f), glow_f=ag.merge(glow_f), armor_h=ag.merge(armor_h), glow_h=ag.merge(glow_h)), dict(tube=T, hand=H)


def mirror_world(mesh):
    """left -> right: reflect y (the body is symmetric in the bind pose)"""
    return ag.mirror_y(mesh)
