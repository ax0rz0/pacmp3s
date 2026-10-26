"""Custom hair for the netrunner: a smooth hair shell over the skull, layered thick locks on top, a side-swept fringe, a long back fall and a high ponytail with neon tips.
Locks follow a distance field of the player's head (ag.Radial), then fall under gravity.  build_hair(scene, ctx) -> (parts, ctx)."""
import numpy as np

import adv_geom as ag
import meshgen as mg
from adv_geom import unit

SILVER = (206, 212, 232)
UNDER = (118, 126, 150)
TIP = (255, 30, 140)
CENTRE = np.array([0.4, 0.0, 65.0])


def e_phi(ph):
    return np.array([-np.sin(ph), np.cos(ph), 0.0])


def taper(n, w0, w1=0.04, power=0.65):
    s = np.linspace(0, 1, n)
    return w1 + (w0 - w1) * (1 - s) ** power


def lock_mesh(path, w, th, up, sides=8, cap=True):
    """a tapered lock: elliptical section, width w along the up hint (flat side on the head), thickness th"""
    sc = np.column_stack([np.asarray(w) / 2.0, np.asarray(th) / 2.0])
    return ag.loft(np.asarray(path, float), ag.circle(sides, 1.0, 1.0), scale=sc, up_hint=np.asarray(up, float), cap_start=cap, cap_end=True)


def hang(last, v0, steps, step_len, g=0.22, jitter=None):
    P = [np.asarray(last, float)]
    v = unit(np.asarray(v0, float))
    for k in range(steps):
        v = unit(v + np.array([0, 0, -g]) + (0 if jitter is None else jitter(k)))
        P.append(P[-1] + v * step_len)
    return np.array(P[1:])


def skull_path(R, th0, ph0, th1, dph, off0, off1, vol, n=12):
    s = np.linspace(0, 1, n)
    th = th0 + (th1 - th0) * s
    ph = ph0 + dph * s
    off = off0 + (off1 - off0) * s + vol * np.sin(np.pi * np.minimum(s * 1.1, 1.0)) ** 1.2
    return R.point(th, ph, off)


def split_tip(path, w, th, frac):
    n = len(path)
    k = max(2, int(round(n * (1 - frac))))
    return (path[:k + 1], w[:k + 1], th[:k + 1]), (path[k:], w[k:], th[k:])


def build_hair(sc, ctx):
    rng = np.random.RandomState(5)
    R = ag.Radial(sc.S_head, CENTRE, n_theta=61, n_phi=181, smooth=3, rmax=20.0)
    ctx['radial'] = R
    base, under, tips = [], [], []
    pony_body, pony_tips = [], []

    def add(path, w0, t0, up, tip_frac=0.0, w1=0.04, power=0.65, sides=8, to=None):
        n = len(path)
        w = taper(n, w0, w1, power)
        th = taper(n, t0, 0.04, 0.5)
        up = np.asarray(up, float)
        to = base if to is None else to
        if tip_frac > 0:
            (pb, wb, tb), (pt, wt, tt) = split_tip(path, w, th, tip_frac)
            to.append(lock_mesh(pb, wb, tb, up, sides))
            tips.append(lock_mesh(pt, wt, tt, up, sides, cap=False))
        else:
            to.append(lock_mesh(path, w, th, up, sides))

    # ------------------------------------------------------------ smooth shell over the skull (hides the original hair), open at the face, the temples and the ear cups
    nth, nph = 30, 120
    th = np.radians(np.linspace(16, 89, nth + 1))
    ph = np.radians(np.linspace(-180, 180, nph + 1))
    TH, PH = np.meshgrid(th, ph, indexing='ij')
    Po = R.point(TH, PH, 0.46)
    Pi = R.point(TH, PH, 0.12)
    cth = 0.5 * (TH[:-1, :-1] + TH[1:, 1:])
    cph = 0.5 * (PH[:-1, :-1] + PH[1:, 1:])
    d_th, d_ph = np.degrees(cth), np.degrees(cph)
    keep = np.ones_like(d_th, bool)
    keep &= ~((np.abs(d_ph) < 62) & (d_th < 60))                 # face / fringe region
    keep &= ~((np.abs(d_ph) >= 62) & (np.abs(d_ph) < 112) & (d_th < 56))     # temples + ears
    keep &= ~((np.abs(d_ph) >= 112) & (d_th < 18))                # open at the bottom of the back
    shell = ag.solidify(np.transpose(Po, (1, 0, 2)), np.transpose(Pi, (1, 0, 2)), keep.T)
    shell = ag.fix_outward(shell)
    under.append(shell)

    # ------------------------------------------------------------ layered top locks (thick, overlapping, combed back and outwards)
    for layer, (th_hi, th_lo, rows) in enumerate(((86, 52, 5), (70, 34, 6))):
        n_ph = 26 if layer == 0 else 32
        for ph0 in np.radians(np.arange(0, 360, 360 / n_ph) + 6 * layer):
            for th0 in np.radians(np.linspace(th_hi, th_lo, rows)):
                phw = (np.degrees(ph0) + 180) % 360 - 180
                tdeg = np.degrees(th0)
                if abs(phw) < 66 and tdeg < 64:
                    continue
                if 62 <= abs(phw) < 114 and tdeg < 58:
                    continue
                th1 = max(th0 - np.radians(rng.uniform(14, 24)), np.radians(26))
                path = skull_path(R, th0 + rng.uniform(-0.04, 0.04), ph0 + rng.uniform(-0.05, 0.05), th1, np.radians(rng.uniform(-10, 10)), 0.5, 0.58 + 0.04 * layer, 0.22, n=6)
                add(path, rng.uniform(1.3, 1.8), rng.uniform(0.34, 0.46), e_phi(ph0), 0.0, w1=0.05, sides=6)

    # ------------------------------------------------------------ fringe: long locks from the front hairline sweeping to the player's left across the forehead
    for k in range(13):
        s = k / 12.0
        ph0 = np.radians(-40 + 78 * s + rng.uniform(-2, 2))
        th0 = np.radians(62 + 3 * np.sin(s * np.pi))
        dph = np.radians(26 + 16 * s + rng.uniform(-4, 4))
        th1 = np.radians(23 + 8 * (1 - s) + rng.uniform(-2, 2))
        path = skull_path(R, th0, ph0, th1, dph, 0.5, 0.72, 0.3, n=12)
        add(path, rng.uniform(1.2, 1.6), rng.uniform(0.34, 0.42), e_phi(ph0 + dph * 0.5), 0.25, w1=0.05, power=0.6)

    # ------------------------------------------------------------ nape: layered shorter locks from behind the ears down to the neck (undercut), tips neon
    for k in range(20):
        s = k / 19.0
        ph0 = np.radians(112 + 136 * s + rng.uniform(-2, 2))
        th0 = np.radians(rng.uniform(32, 48))
        sk = skull_path(R, th0, ph0, np.radians(-8 - 6 * rng.rand()), np.radians(rng.uniform(-4, 4)), 0.5, 0.78, 0.25, n=9)
        v0 = sk[-1] - sk[-2]
        ext = hang(sk[-1], v0 + np.array([-0.12, 0, 0]), steps=4, step_len=0.95, g=0.3)
        path = np.vstack([sk, ext])
        path[:, 0] = np.minimum(path[:, 0], -2.3)
        add(path, rng.uniform(1.3, 1.8), rng.uniform(0.4, 0.5), e_phi(ph0), 0.2 if k % 2 == 0 else 0.0, w1=0.05, power=0.6)
    for k in range(10):
        s = k / 9.0
        ph0 = np.radians(116 + 128 * s + rng.uniform(-4, 4))
        th0 = np.radians(rng.uniform(24, 38))
        sk = skull_path(R, th0, ph0, np.radians(-12), np.radians(rng.uniform(-3, 3)), 0.78, 1.0, 0.3, n=9)
        v0 = sk[-1] - sk[-2]
        ext = hang(sk[-1], v0 + np.array([-0.2, 0, 0]), steps=3, step_len=0.95, g=0.3)
        path = np.vstack([sk, ext])
        path[:, 0] = np.minimum(path[:, 0], -2.5)
        add(path, rng.uniform(1.0, 1.4), rng.uniform(0.3, 0.4), e_phi(ph0), 0.0, w1=0.05, power=0.6, to=under)

    # ------------------------------------------------------------ high ponytail: own meshes, origin = the tie point (so it can swing)
    th_t, ph_t = np.radians(52), np.pi
    tie = R.point(th_t, ph_t, 1.0)
    v_start = np.array([-0.85, 0.0, 0.5])
    cl = np.vstack([tie, hang(tie, v_start, steps=18, step_len=1.15, g=0.19)])          # shared centre line of the tail
    n_cl = len(cl)
    s_cl = np.linspace(0, 1, n_cl)
    for k in range(15):
        a = 2 * np.pi * k / 15.0 + rng.uniform(-0.15, 0.15)
        reach = rng.uniform(0.7, 1.2)
        lat = np.stack([np.sin(a) * (0.1 + 1.1 * s_cl ** 1.2) * reach, np.cos(a) * (0.12 + 1.5 * s_cl ** 1.3) * reach, np.zeros(n_cl)], 1)
        wave = np.stack([0.2 * np.sin(2.0 * np.pi * s_cl + 2 * a) * s_cl, 0.3 * np.sin(2.4 * np.pi * s_cl + a) * s_cl, np.zeros(n_cl)], 1)
        path = cl + lat + wave - tie
        n = len(path)
        w = taper(n, rng.uniform(1.5, 2.1), 0.05, 0.5)
        th_ = taper(n, rng.uniform(0.5, 0.62), 0.05, 0.5)
        (pb, wb, tb), (pt, wt, tt) = split_tip(path, w, th_, 0.22)
        up = e_phi(np.pi + 0.25 * np.cos(a))
        pony_body.append(lock_mesh(pb, wb, tb, up))
        pony_tips.append(lock_mesh(pt, wt, tt, up, cap=False))
    ctx['tie'] = tie
    d = unit(np.array([-0.85, 0.0, 0.5]))
    ref = np.array([0.0, 1.0, 0.0])
    x = unit(np.cross(ref, d))
    y = np.cross(d, x)
    Rr = np.stack([x, y, d], 1)
    tie_ring = mg.torus(0.7, 0.2, nu=28, nv=8).transform(R=Rr, t=tie + d * 0.5)
    tie_glow = mg.torus(0.7, 0.08, nu=28, nv=6).transform(R=Rr, t=tie + d * 1.0)

    # ------------------------------------------------------------ circuit lines on the shaved temples
    glow = []
    for sgn in (+1, -1):
        base_ph = np.radians(88 * sgn)

        def line(pts, base_ph=base_ph, sgn=sgn):
            t_ = np.radians([p[0] for p in pts])
            p_ = base_ph + np.radians([p[1] * sgn for p in pts])
            P = R.point(t_, p_, 0.22)
            N = R.dir(t_, p_)
            return ag.strip_solid(P, N, 0.07, 0.05)

        glow.append(line([(52, -14), (50, -5), (44, -5), (42, 8), (36, 8)]))
        glow.append(line([(46, -18), (42, -12), (39, -12), (37, 0)]))
        glow.append(line([(54, 0), (50, 10), (46, 10), (44, 18), (40, 18)]))
        for (t_, p_) in ((36, 8), (37, 0), (40, 18)):
            c = R.point(np.radians(t_), base_ph + np.radians(p_ * sgn), 0.26)
            n = R.dir(np.radians(t_), base_ph + np.radians(p_ * sgn))
            xx = unit(np.cross([0, 0, 1.0], n))
            yy = np.cross(n, xx)
            glow.append(ag.cone(0.14, 0.12, 0.07, sides=10).transform(R=np.stack([xx, yy, n], 1), t=c))

    parts = {
        'hair': dict(mesh=ag.merge(base), color=SILVER, rough=0.42, smooth=60),
        'under': dict(mesh=ag.merge(under), color=UNDER, rough=0.5, smooth=60),
        'tips': dict(mesh=ag.merge(tips + glow), color=TIP, nolight=True, smooth=70),
        'pony': dict(mesh=ag.merge(pony_body), color=SILVER, rough=0.42, smooth=60, pivot=tie),
        'pony_tips': dict(mesh=ag.merge(pony_tips), color=TIP, nolight=True, smooth=70, pivot=tie),
        'tie': dict(mesh=ag.merge([tie_ring]), color=(30, 30, 38), rough=0.4, smooth=50),
        'tie_glow': dict(mesh=ag.merge([tie_glow]), color=TIP, nolight=True, smooth=60),
    }
    for k in ('pony', 'pony_tips'):
        m = parts[k]['mesh']
        parts[k]['mesh'] = type(m)(m.V + tie, m.UV.copy(), m.F.copy())
    return parts, ctx
