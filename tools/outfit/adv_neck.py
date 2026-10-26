"""A skin coloured neck for the donor head swap (v2).

The Ethics Assistant's own head slot also holds her neck, so hiding the head hides the neck as well; the donor head (adv_head_obj.py) ends in a short stump of ITS neck, cut open by the clip plane.
This column plugs that stump: below ~59 it follows her own neck (front line, back line and width measured on her skin slot), then it eases into the open ring of the stump, runs a little wider than
the stump for a moment (so that the stump's rim always sits inside the column when the head turns against the neck bone) and ends inside the stump, closed, where nobody can see it.
There is no flare and no flat top any more: v1 flared back to meet the donor's wide flange and left its flat top cap sticking out under the hair.
Built in the in-game bind frame like the other accessories (world: x forward, y left, z up); the neck bone carries it.

    build_neck(ring_world, ring_normal, patch) -> (P, N, UV) triangle soup (T,3,3 / T,3,3 / T,3,2), faces counter clockwise outside; uvs are a window `patch` of the head texture atlas, mapped so that
    every triangle has a real uv area (see adv_head_obj.uv_det)
"""
import numpy as np

# her own neck (bind pose, measured on the player's skin slot): world x of the throat (front surface), of the nape (back surface) and the half width by height z
FRONT = np.array([[54.0, 1.00], [55.0, 1.10], [58.0, 1.50], [60.0, 1.75]])
BACK = np.array([[54.0, -1.85], [55.0, -1.8], [58.0, -1.45], [60.0, -1.4]])
HALF_WIDTH = np.array([[54.0, 2.0], [55.0, 2.0], [58.0, 1.95], [60.0, 1.95]])
Z_BOTTOM = 54.4                                    # inside the suit's collar
Z_BLEND = 57.8                                     # from here the column eases into the stump ring
OVER = 0.3                                        # how much wider than the stump ring the column is where it meets it (turning the head moves the rim by up to ~0.7)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _ring_polar(ring, c, e_f, e_l, n_cols):
    """radius of the (star shaped) ring about its centre c for n_cols evenly spaced angles, angle 0 = e_f (forward), growing towards e_l (left)"""
    a = (ring - c) @ e_f
    b = (ring - c) @ e_l
    phi = np.arctan2(b, a)
    rho = np.hypot(a, b)
    o = np.argsort(phi)
    theta = np.arange(n_cols) * (2 * np.pi / n_cols)
    th = np.where(theta > np.pi, theta - 2 * np.pi, theta)
    return np.interp(th, phi[o], rho[o], period=2 * np.pi)


INNER = [(0.45, 0.12), (1.0, -0.06), (1.6, -0.16), (2.1, -0.2)]      # (distance up the canal axis, offset from the stump ring radius) of the rings inside the stump


def build_neck(ring_world, ring_normal, patch, canal_axis=(0.172, 0.0, 0.985), n_cols=40, n_low=6, n_blend=8):
    ring = np.asarray(ring_world, float)
    n_up = np.asarray(ring_normal, float)
    n_up = n_up / np.linalg.norm(n_up)
    c_t = ring.mean(0)
    e_l = np.array([0.0, 1.0, 0.0])
    e_l = e_l - (e_l @ n_up) * n_up
    e_l /= np.linalg.norm(e_l)
    e_f = np.cross(e_l, n_up)                          # forward, in the ring plane
    if e_f[0] < 0:
        e_f = -e_f
        e_l = -e_l
    theta = np.arange(n_cols) * (2 * np.pi / n_cols)
    d_t = np.outer(np.cos(theta), e_f) + np.outer(np.sin(theta), e_l)                      # (M,3) directions in the ring plane
    rho = _ring_polar(ring, c_t, e_f, e_l, n_cols)

    axis = np.asarray(canal_axis, float)                  # the stump is a short tube along the head bone's long axis: the column continues up inside it
    axis = axis / np.linalg.norm(axis)

    def top(off, up):
        return c_t + up * axis + (rho + off)[:, None] * d_t

    def ellipse(z):
        xf = np.interp(z, FRONT[:, 0], FRONT[:, 1])
        xb = np.interp(z, BACK[:, 0], BACK[:, 1])
        hw = np.interp(z, HALF_WIDTH[:, 0], HALF_WIDTH[:, 1])
        xc, hd = (xf + xb) / 2.0, (xf - xb) / 2.0
        return np.column_stack([xc + hd * np.cos(theta), hw * np.sin(theta), np.full(n_cols, z)])

    rings = []
    for z in np.linspace(Z_BOTTOM, Z_BLEND, n_low, endpoint=False):
        rings.append(ellipse(z))
    e_b = ellipse(Z_BLEND)
    t_over = top(OVER, 0.0)
    for s in np.linspace(0.0, 1.0, n_blend + 1):
        rings.append((1 - smoothstep(s)) * e_b + smoothstep(s) * t_over)
    for up, off in INNER:                                 # gently back inside the stump so that the crease where the column leaves it is shallow
        rings.append(top(off, up))
    top_centre = c_t + INNER[-1][0] * axis
    K = len(rings)
    G = np.stack(rings)                                  # (K, M, 3)
    # vertex grid with the seam column repeated (uv wrap)
    Gc = np.concatenate([G, G[:, :1]], axis=1)           # (K, M+1, 3)
    # uv: column fraction across the patch width, ring fraction (by arc length along the axis) down the patch height
    axis_pts = G.mean(1)
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(axis_pts, axis=0), axis=1))])
    vfrac = arc / arc[-1]
    u0, v0, du, dv = patch
    inset = 0.04                                          # keep the patch's rim samples off the window edge (filtering)
    UVg = np.zeros((K, n_cols + 1, 2))
    UVg[..., 0] = (u0 + du * (inset + (1 - 2 * inset) * np.arange(n_cols + 1) / n_cols))[None, :]
    UVg[..., 1] = (v0 + dv * (inset + (1 - 2 * inset) * vfrac))[:, None]
    # side faces
    idx = np.arange(K * (n_cols + 1)).reshape(K, n_cols + 1)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
    V = Gc.reshape(-1, 3)
    UVv = UVg.reshape(-1, 2)
    # smooth vertex normals: area weighted face normals summed over the vertices that share a position (the seam column and the repeated first column are the same point)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    centre_of = axis_pts[F[:, 0] // (n_cols + 1)]
    if np.einsum('ij,ij->', fn, V[F[:, 0]] - centre_of) < 0:       # make the side faces counter clockwise outside
        F = F[:, ::-1]
        fn = -fn
    acc = np.zeros((K, n_cols + 1, 3))
    rows = F[:, 0] // (n_cols + 1)
    for k in range(3):
        np.add.at(acc.reshape(-1, 3), F[:, k], fn)
    acc[:, 0] += acc[:, -1]
    acc[:, -1] = acc[:, 0]
    # bottom / top end caps are flat fans (hidden inside the collar and inside the stump); the rim normals of the sides are left as they are
    nrm_v = acc.reshape(-1, 3)
    nrm_v = nrm_v / np.maximum(np.linalg.norm(nrm_v, axis=1, keepdims=True), 1e-12)
    P_s, N_s, U_s = V[F], nrm_v[F], UVv[F]
    soups = [(P_s, N_s, U_s)]
    for ring_pts, centre, outward in ((G[0], G[0].mean(0), -np.array([0.0, 0.0, 1.0])), (G[-1], top_centre, n_up)):
        rr = ring_pts - centre
        Rm = np.max(np.linalg.norm(rr, axis=1))
        tri_P, tri_U = [], []
        for i in range(n_cols):
            j = (i + 1) % n_cols
            p3 = np.array([centre, ring_pts[i], ring_pts[j]])
            g = np.cross(p3[1] - p3[0], p3[2] - p3[0])
            if g @ outward < 0:
                p3 = p3[[0, 2, 1]]
            tri_P.append(p3)
            # planar projection of the cap onto the patch window: every triangle has an area in uv space
            rel = (p3 - centre)
            uu = u0 + du * (0.5 + 0.45 * (rel @ e_f) / Rm)
            vv = v0 + dv * (0.5 + 0.45 * (rel @ e_l) / Rm)
            tri_U.append(np.column_stack([uu, vv]))
        tri_P = np.array(tri_P)
        tri_U = np.array(tri_U)
        tri_N = np.broadcast_to(outward, tri_P.shape).copy()
        soups.append((tri_P, tri_N, tri_U))
    P = np.concatenate([s[0] for s in soups])
    N = np.concatenate([s[1] for s in soups])
    U = np.concatenate([s[2] for s in soups])
    return P, N, U


if __name__ == '__main__':
    # smoke test with a made-up ring
    th = np.linspace(0, 2 * np.pi, 60, endpoint=False)
    ring = np.column_stack([-0.4 + 1.4 * np.cos(th), 1.9 * np.sin(th), np.full(60, 62.0)])
    P, N, U = build_neck(ring, np.array([0.0, 0.0, 1.0]), (0.36, 0.148, 0.027, 0.055))
    print('tris', len(P), 'z', P[..., 2].min(), P[..., 2].max())
