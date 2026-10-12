"""Texture painters for the three BNA-palette Ethics Assistant styles on models/jericho/citizens/female_04 (femsuit_04).

Every output is a 1024x1024 RGB array in the model's UV space (the pac url-texture loader renders the image into a square, so any source aspect works).
Painting is driven by position maps (uvmap.py): each texel knows its 3D position, so stripes, cuffs, gradients and decals are defined on the body, not on the atlas.
Palette (BNA): PINK #fc2c9d, MAGENTA #c62c80, INDIGO #554eae, ROYAL #21388c, NAVY #0f215e.
"""
import numpy as np
from scipy.ndimage import gaussian_filter

from ethics_common import PINK, MAGENTA, INDIGO, ROYAL, NAVY

SIZE = 1024


def rgb(c):
    return np.asarray(c, np.float32) / 255.0


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lum(img):
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def layer(out, color, mask, alpha=1.0):
    m = (mask * alpha)[..., None].astype(np.float32)
    return out * (1.0 - m) + np.asarray(color, np.float32) * m


class Maps:
    def __init__(self, npz, prefix):
        self.pos = npz[prefix + '_pos']
        self.nrm = npz[prefix + '_nrm']
        self.rid = npz[prefix + '_rid']
        self.cover = npz[prefix + '_cover']
        self.pad = npz[prefix + '_padded']
        self.x, self.y, self.z = self.pos[..., 0], self.pos[..., 1], self.pos[..., 2]


# ------------------------------------------------------------------------------------------------------------------------------------ body-space coordinates
ARM = {+1: np.array([[-0.6, 5.7, 57.9], [-2.1, 11.7, 48.6], [-1.3, 17.7, 39.2]]), -1: np.array([[-0.6, -5.7, 57.9], [-2.1, -11.7, 48.6], [-1.3, -17.7, 39.2]])}


def arm_features(M, side):
    """distance to the arm axis, arc position t (0 shoulder .. 1 wrist) and the angle around the axis, for every texel"""
    P = M.pos.reshape(-1, 3).astype(np.float64)
    pts = ARM[side]
    seg = pts[1:] - pts[:-1]
    ln = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0], np.cumsum(ln)])
    best_d = np.full(len(P), 1e9)
    best_t = np.zeros(len(P))
    best_phi = np.zeros(len(P))
    for i in range(len(seg)):
        a, ab = pts[i], seg[i]
        t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        c = a + t[:, None] * ab
        r = P - c
        d = np.linalg.norm(r, axis=1)
        axis = ab / ln[i]
        ref = np.array([0.0, 0.0, -1.0])
        u = ref - (ref @ axis) * axis
        u /= np.linalg.norm(u)
        v = np.cross(axis, u)
        phi = np.arctan2(r @ v, r @ u)
        better = d < best_d
        best_d = np.where(better, d, best_d)
        best_t = np.where(better, (cum[i] + t * ln[i]) / cum[-1], best_t)
        best_phi = np.where(better, phi, best_phi)
    sh = M.z.shape
    return best_d.reshape(sh).astype(np.float32), best_t.reshape(sh).astype(np.float32), best_phi.reshape(sh).astype(np.float32)


def islands(M, min_texels=300):
    """connected UV islands of the atlas (seams closed): returns (label array, [dict(label, texels, zmin, zmax, ymax)])"""
    from scipy import ndimage as ndi
    merged = ndi.binary_closing(M.cover, structure=np.ones((3, 3)), iterations=2)
    lab, n = ndi.label(merged)
    info = []
    for i in range(1, n + 1):
        m = (lab == i) & M.cover
        cnt = int(m.sum())
        if cnt >= min_texels:
            info.append(dict(label=i, texels=cnt, zmin=float(M.z[m].min()), zmax=float(M.z[m].max()), ymax=float(np.abs(M.y[m]).max())))
    # grow every labelled island over its gutter so padded texels belong to the same island
    dist, idx = ndi.distance_transform_edt(lab == 0, return_indices=True)
    lab_full = lab[idx[0], idx[1]]
    lab_full = np.where(M.pad, lab_full, 0)
    return lab_full, info


def stripes(phase, width=0.07, soft=0.02):
    f = phase - np.floor(phase)
    return sstep(0.0, soft, f) * (1 - sstep(width, width + soft, f))


# ------------------------------------------------------------------------------------------------------------------------------------ emblem (own design)
def _sd_box(px, py, cx, cy, hx, hy, ang=0.0):
    c, s = np.cos(ang), np.sin(ang)
    x = (px - cx) * c + (py - cy) * s
    y = -(px - cx) * s + (py - cy) * c
    qx, qy = np.abs(x) - hx, np.abs(y) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)


def _sd_hex(px, py, r):
    kx, ky, kz = -0.866025404, 0.5, 0.577350269
    x, y = np.abs(px), np.abs(py)
    d = kx * x + ky * y
    x = x - 2.0 * np.minimum(d, 0.0) * kx
    y = y - 2.0 * np.minimum(d, 0.0) * ky
    x = x - np.clip(x, -kz * r, kz * r)
    y = y - r
    return np.hypot(x, y) * np.sign(y)


def emblem_sd(a, b):
    """signed distance (negative inside) of the emblem in [-1,1]^2: a hexagon ring around an X with a bar on top"""
    ring = np.abs(_sd_hex(a, b, 0.86)) - 0.085
    x1 = _sd_box(a, b, 0.0, 0.08, 0.5, 0.085, np.radians(52))
    x2 = _sd_box(a, b, 0.0, 0.08, 0.5, 0.085, np.radians(-52))
    bar = _sd_box(a, b, 0.0, -0.46, 0.43, 0.075)
    return np.minimum(np.minimum(ring, bar), np.minimum(x1, x2))


def emblem_mask(a, b, px):
    """antialiased coverage; px = size of one pixel in the same units as a,b"""
    return np.clip(0.5 - emblem_sd(a, b) / px, 0, 1)


def emblem_image(size, fg, bg=None, pad=0.0):
    lin = (np.arange(size) + 0.5) / size * 2 - 1
    a, b = np.meshgrid(lin, lin)
    m = emblem_mask(a * (1 + pad), b * (1 + pad), 2.0 / size * (1 + pad))
    out = np.zeros((size, size, 4), np.float32)
    out[..., :3] = rgb(fg)
    out[..., 3] = m
    if bg is not None:
        base = np.zeros((size, size, 3), np.float32) + rgb(bg)
        base = base * (1 - m[..., None]) + rgb(fg) * m[..., None]
        return base
    return out


# ------------------------------------------------------------------------------------------------------------------------------------ shared cloth shading
def cloth_shade(L0, covered, seed=3, grain=0.05, k=0.9):
    """multiplicative shading from the original atlas (folds, AO) plus a fine weave"""
    blur = gaussian_filter(L0, 5)
    det = np.clip((L0 - blur) / (blur + 0.03), -0.7, 0.7)
    rs = np.random.RandomState(seed)
    noise = gaussian_filter(rs.randn(SIZE, SIZE).astype(np.float32), 0.7) * 0.9
    weave = (((np.arange(SIZE)[None, :] // 2) + (np.arange(SIZE)[:, None] // 2)) % 2).astype(np.float32) * 0.5 - 0.25
    sh = 1.0 + k * det + grain * noise + 0.03 * weave
    return np.clip(sh, 0.55, 1.4).astype(np.float32)


def blouse_shade(L0):
    blur = gaussian_filter(L0, 4)
    return np.clip(0.5 + 0.7 * np.clip((L0 - 0.4) / 0.6, 0, 1) + 1.4 * (L0 - blur), 0.45, 1.25).astype(np.float32)


# ------------------------------------------------------------------------------------------------------------------------------------ the suit atlas (jacket + blouse + trousers)
def suit_regions(M, orig):
    L0 = lum(orig[..., :3].astype(np.float32) / 255.0)
    Lb = gaussian_filter(L0, 1.0)
    blouse = sstep(0.34, 0.60, Lb) * M.pad
    jacket = (M.rid == 1) & M.pad
    pants = (M.rid == 2) & M.pad
    dl, tl, pl = arm_features(M, +1)
    dr, tr, pr = arm_features(M, -1)
    lab, info = islands(M)
    sleeve_ids = [i['label'] for i in info if i['ymax'] > 15.0 and i['zmin'] > 30.0]       # the sleeve island (both sleeves, arms reach |y| ~ 19)
    sleeve = np.isin(lab, sleeve_ids) & jacket
    t = np.where(M.y > 0, tl, tr)
    phi = np.where(M.y > 0, pl, pr)
    return dict(L0=L0, blouse=blouse, jacket=jacket, pants=pants, sleeve=sleeve, t=t, phi=phi)


def _torso_theta(M):
    return np.arctan2(M.y, M.x + 0.8)


def paint_suit(style, M, orig):
    R = suit_regions(M, orig)
    L0, blouse, jacket, pants, sleeve = R['L0'], R['blouse'], R['jacket'], R['pants'], R['sleeve']
    cloth_sh = cloth_shade(L0, M.pad)
    bl_sh = blouse_shade(L0)
    out = np.zeros((SIZE, SIZE, 3), np.float32) + rgb(NAVY) * 0.5
    z = M.z
    theta = _torso_theta(M)
    # leg angle about each leg's own vertical axis (trousers)
    ly = np.where(M.y > 0, 3.7, -3.7)
    leg_theta = np.arctan2(M.y - ly, M.x - 0.2)
    torso = jacket & ~sleeve
    nrm_back = M.nrm[..., 0] < -0.35
    if style == 'formal':
        base = rgb(NAVY)
        out = layer(out, base * cloth_sh[..., None], M.pad)
        # pinstripes in ROYAL: around the torso, around the arms, around each trouser leg
        ph = np.where(sleeve, R['phi'] * 3.0 / 2.6, np.where(pants, leg_theta * 3.4 / 2.3, theta * 5.6 / 3.2))
        out = layer(out, rgb(ROYAL) * cloth_sh[..., None] * 1.25, stripes(ph, 0.075) * (jacket | pants) * (1 - blouse), 0.85)
        # piping: cuffs (last 10% of the sleeve) and the jacket hem in MAGENTA, lapel-side collar band in PINK
        cuff = sstep(0.89, 0.91, R['t']) * sleeve
        out = layer(out, rgb(MAGENTA) * cloth_sh[..., None], cuff)
        hem = (1 - sstep(35.2, 35.9, z)) * jacket * ~sleeve
        out = layer(out, rgb(MAGENTA) * cloth_sh[..., None], hem * (1 - blouse))
        out = layer(out, rgb(PINK) * bl_sh[..., None], blouse)
        # trouser cuffs: a thin MAGENTA band just above the hem of the flare
        cuffp = pants * sstep(7.2, 7.6, z) * (1 - sstep(8.4, 8.8, z))
        out = layer(out, rgb(MAGENTA) * cloth_sh[..., None], cuffp)
    elif style == 'anima':
        # INDIGO jacket fading to NAVY at the hem, ROYAL sleeves, MAGENTA blouse, PINK cuffs
        fade = sstep(36.0, 56.0, z)
        body = rgb(NAVY) * (1 - fade[..., None]) + rgb(INDIGO) * fade[..., None]
        out = layer(out, body * cloth_sh[..., None], M.pad)
        out = layer(out, rgb(ROYAL) * cloth_sh[..., None] * 1.1, sleeve, 0.95)
        # fine tonal stripes on the sleeves (INDIGO on ROYAL) so they read as knit
        out = layer(out, rgb(INDIGO) * cloth_sh[..., None], stripes(R['phi'] * 3.0 / 2.0, 0.22) * sleeve, 0.55)
        out = layer(out, rgb(PINK) * cloth_sh[..., None], sstep(0.84, 0.86, R['t']) * (1 - sstep(0.93, 0.95, R['t'])) * sleeve)
        out = layer(out, rgb(MAGENTA) * cloth_sh[..., None], sstep(0.945, 0.96, R['t']) * sleeve)
        # shoulder yoke accent line (PINK) and hem line
        out = layer(out, rgb(PINK) * cloth_sh[..., None], (1 - sstep(35.2, 36.0, z)) * torso * (1 - blouse))
        out = layer(out, rgb(MAGENTA) * bl_sh[..., None], blouse)
        # trousers (used when the pants bodygroup is on): NAVY with a PINK outer-seam stripe
        out = layer(out, rgb(NAVY) * cloth_sh[..., None], pants)
        side = (np.abs(M.nrm[..., 1]) > 0.8) & (np.sign(M.nrm[..., 1]) == np.sign(M.y)) & (np.abs(M.y) > 2.2)
        out = layer(out, rgb(PINK) * cloth_sh[..., None], side * pants * 1.0)
    elif style == 'neon':
        # hot PINK bomber with MAGENTA shading, NAVY sleeves with INDIGO + PINK stripes, big emblem on the back
        grad = sstep(36.0, 58.0, z)
        body = rgb(MAGENTA) * (1 - grad[..., None]) + rgb(PINK) * grad[..., None]
        out = layer(out, body * cloth_sh[..., None], M.pad)
        out = layer(out, rgb(NAVY) * cloth_sh[..., None], sleeve)
        out = layer(out, rgb(INDIGO) * cloth_sh[..., None], stripes(R['t'] * 9.0, 0.11) * sleeve * (R['t'] > 0.25) * (R['t'] < 0.82))
        out = layer(out, rgb(PINK) * cloth_sh[..., None], sstep(0.86, 0.88, R['t']) * sleeve)
        # collar / hem rib in NAVY
        out = layer(out, rgb(NAVY) * cloth_sh[..., None], (1 - sstep(35.3, 36.2, z)) * torso * (1 - blouse))
        out = layer(out, rgb(NAVY) * bl_sh[..., None] * 1.15, blouse)
        # trousers: NAVY with a thick PINK side stripe and a thin INDIGO stripe beside it, ROYAL flared cuffs
        out = layer(out, rgb(NAVY) * cloth_sh[..., None], pants)
        outer = (np.sign(M.nrm[..., 1]) == np.sign(M.y)) & (np.abs(M.nrm[..., 1]) > 0.78) & (np.abs(M.y) > 2.2)
        out = layer(out, rgb(PINK) * cloth_sh[..., None], outer * pants)
        outer2 = (np.sign(M.nrm[..., 1]) == np.sign(M.y)) & (np.abs(M.nrm[..., 1]) > 0.58) & (np.abs(M.nrm[..., 1]) <= 0.78) & (np.abs(M.y) > 2.2)
        out = layer(out, rgb(INDIGO) * cloth_sh[..., None], outer2 * pants)
        out = layer(out, rgb(ROYAL) * cloth_sh[..., None], pants * (1 - sstep(8.0, 8.6, z)))
        # emblem on the upper back (NAVY ring + INDIGO fill is too dark on pink: use NAVY emblem with an INDIGO shadow)
        a = -(M.y - 0.0) / 4.4
        b = (z - 49.5) / 4.4
        px = 1.0 / (14.0 * 4.4)
        sdw = emblem_mask(a + 0.05, b - 0.05, px * 1.6)
        em = emblem_mask(a, b, px * 1.6)
        mask_zone = (np.abs(a) < 1.2) & (np.abs(b) < 1.2) & nrm_back & jacket
        out = layer(out, rgb(INDIGO), sdw * mask_zone, 0.9)
        out = layer(out, rgb(NAVY), em * mask_zone)
    # bleed unused texels toward the base colour so mip-less filtering does not pull in grey
    out = np.where(M.pad[..., None], out, rgb(NAVY) * 0.45)
    return np.clip(out, 0, 1)


# ------------------------------------------------------------------------------------------------------------------------------------ the skirt atlas (skirt + stockings + shoes)
def paint_skirt(style, M, orig):
    L0 = lum(orig[..., :3].astype(np.float32) / 255.0)
    sh = cloth_shade(np.maximum(L0, 0.02), M.pad, seed=5, grain=0.045, k=0.8)
    z = M.z
    theta = np.arctan2(M.y, M.x + 0.6)
    lab, info = islands(M)
    skirt = np.isin(lab, [i['label'] for i in info if i['zmin'] > 20.0])
    shoes = np.isin(lab, [i['label'] for i in info if i['zmax'] < 5.6])
    legs = M.pad & ~skirt & ~shoes
    out = np.zeros((SIZE, SIZE, 3), np.float32) + rgb(NAVY) * 0.4
    if style == 'formal':
        out = layer(out, rgb(NAVY) * sh[..., None], skirt)
        out = layer(out, rgb(ROYAL) * sh[..., None] * 1.25, stripes(theta * 5.4 / 3.2, 0.075) * skirt, 0.85)
        out = layer(out, rgb(MAGENTA) * sh[..., None], (1 - sstep(23.6, 24.4, z)) * skirt)                                    # hem piping
        out = layer(out, rgb(NAVY) * 0.42 * sh[..., None], legs)                                                              # sheer navy stockings
        out = layer(out, rgb(MAGENTA) * sh[..., None] * 1.05, shoes)                                                          # MAGENTA pumps
    elif style == 'anima':
        out = layer(out, rgb(NAVY) * sh[..., None], skirt)
        out = layer(out, rgb(INDIGO) * sh[..., None], skirt * sstep(31.0, 37.0, z) * 0.8)                                     # waistband glow
        out = layer(out, rgb(PINK) * sh[..., None], (1 - sstep(23.5, 24.1, z)) * skirt)                                       # PINK hem
        side = (np.abs(M.nrm[..., 1]) > 0.86) * skirt * (np.abs(M.y) > 3.0)                                                   # side-seam stripe
        out = layer(out, rgb(MAGENTA) * sh[..., None], side)
        out = layer(out, rgb(NAVY) * 0.55 * sh[..., None], legs)
        for zc, col, w in ((19.0, MAGENTA, 0.45), (17.6, PINK, 0.3), (9.2, MAGENTA, 0.45), (7.9, PINK, 0.3)):                # ring socks accents
            out = layer(out, rgb(col) * sh[..., None], (1 - sstep(w, w + 0.15, np.abs(z - zc))) * legs)
        out = layer(out, rgb(PINK) * sh[..., None] * 1.05, shoes)
    elif style == 'neon':
        # (the neon style normally wears the trousers; if the skirt bodygroup is on, keep it coherent)
        out = layer(out, rgb(NAVY) * sh[..., None], skirt)
        out = layer(out, rgb(PINK) * sh[..., None], (np.abs(M.nrm[..., 1]) > 0.8) * skirt * (np.abs(M.y) > 3.0))
        out = layer(out, rgb(INDIGO) * 0.55 * sh[..., None], legs)
        out = layer(out, rgb(PINK) * sh[..., None] * 1.05, shoes)
        out = layer(out, rgb(NAVY) * sh[..., None], shoes * (z < 1.1))
    return np.clip(out, 0, 1)


# ------------------------------------------------------------------------------------------------------------------------------------ the face / hair map
def paint_face(style, M, orig_face):
    """orig_face: stock facemap (512x256 RGBA) -> 1024x1024 RGB with the hair recoloured (the face skin is untouched)."""
    import cv2
    f = cv2.resize(orig_face[..., :3], (SIZE, SIZE), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
    L = lum(f)
    Lb = gaussian_filter(L, 0.8)
    hair = (1 - sstep(0.20, 0.36, Lb))                       # near-black pixels: hair, brows, lashes
    hair = gaussian_filter(hair, 0.6)
    x, z = M.x, M.z
    # 0 at the roots .. 1 at the tips: the ponytail hangs below z 62 at the back
    tip = sstep(63.2, 60.2, z) * sstep(-2.2, -4.2, x)
    crown = sstep(66.0, 69.5, z)
    ln = np.clip(L / 0.30, 0, 1.4)
    if style == 'formal':
        dark, mid, hi = rgb((5, 8, 24)), rgb(NAVY) * 0.9, rgb(ROYAL) * 1.0
        col = dark[None, None] * (1 - np.clip(ln, 0, 1))[..., None] + mid[None, None] * np.clip(ln, 0, 1)[..., None]
        col = col + (hi * 0.45)[None, None] * np.clip(ln - 0.75, 0, 0.6)[..., None]
    elif style == 'anima':
        dark, mid = rgb((10, 10, 40)), rgb(INDIGO) * 0.8
        col = dark[None, None] * (1 - np.clip(ln, 0, 1))[..., None] + mid[None, None] * np.clip(ln, 0, 1)[..., None]
        # gradient to MAGENTA then PINK on the ponytail
        t1 = sstep(0.05, 0.55, tip)[..., None]
        t2 = sstep(0.55, 1.0, tip)[..., None]
        tipc = (rgb(MAGENTA) * (1 - t2) + rgb(PINK) * t2) * (0.35 + 0.75 * np.clip(ln, 0, 1))[..., None]
        col = col * (1 - t1) + tipc * t1
    else:     # neon
        dark, mid = rgb((12, 8, 40)), rgb(INDIGO) * 0.95
        col = dark[None, None] * (1 - np.clip(ln, 0, 1))[..., None] + mid[None, None] * np.clip(ln, 0, 1)[..., None]
        t1 = sstep(0.05, 0.6, tip)[..., None]
        tipc = rgb(PINK) * (0.4 + 0.7 * np.clip(ln, 0, 1))[..., None]
        col = col * (1 - t1) + tipc * t1
    out = f * (1 - hair[..., None]) + np.clip(col, 0, 1) * hair[..., None]
    return np.clip(out, 0, 1)
