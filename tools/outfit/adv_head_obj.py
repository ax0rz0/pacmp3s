"""The Song So Mi head (Cyberpunk 2077: Phantom Liberty, Workshop 3283215678) as plain GitHub-hosted assets: OBJ meshes in the Ethics Assistant's head-bone frame + PNG / JPG textures, so that pac downloads
everything itself and nobody needs the Workshop addon.

The donor's compiled model is read with mdl_mesh / donor_tools (it is never run), skinned into the player's bind frame (BoneMerge math), moved into the head bone's local frame and split into
static meshes, every file under 1 MB (file names carry VER because pac caches downloads by url):
  hd_head_<VER>       the Head slot, cut under the skull by a plane (the donor's own neck is a wide flat flange; the neck is hd_neck_<VER>.obj, see adv_neck.py) + EyeL + EyeR
                      texture hd_head.jpg (2048x1024: Head_c 1024^2 | the eyes)
  hd_extras_<VER>     Lipstick + EyeMakeup + EyeBrows + Cyberware + EyeLashes (thin shells 0.015 above the skin) + the cyber port at the nape    texture hd_extras.png (one atlas, the $color2 tints baked in)
  hd_hair_a..c_<VER>  Hair (alpha tested cards, no culling) in three chunks, $color2 2.5 baked into the texture                                 texture hd_hair.png   (palette png with alpha)
Every mesh is moved by HEAD_SHIFT (the donor's head is shorter and sits further back than hers).
Winding: the donor is clockwise outside, pac reverses obj winding, so the faces are written counter clockwise outside.  uvs are written as (u, 1 - v) because pac flips v and wraps with % 1.
Two pac urlobj details the writer takes care of: (1) tangents are computed per triangle with r = 1 / (s1 t2 - s2 t1), so a triangle whose three uvs are collinear has infinite / NaN tangents and
renders black (the first neck had 91 % of its triangles like that) - write_obj nudges one or two corners of such triangles by a uv quantum (uv_det / repair_uv); (2) polygons are fanned from their
first corner, so two triangles (p,q,r) + (p,r,d) are written as one quad p q r d (merge_quads): the same triangles, a third fewer face bytes.

    build(stage_root)  ->  {'obj': {key: filename}, 'tex': {key: filename}, 'stats': ..., 'ring_world': the open end of the donor's neck stump, 'canal_axis_world': ..., 'neck_patch': (u0, v0, du, dv)}
    (files go to <stage_root>/obj/adv and <stage_root>/tex/adv)
"""
import os
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_scene as asn
import run_donor_preview as rdp

# the cut under the skull, in head-bone coordinates (X up, tilted 10 deg forward; Y back; Z lateral): plane through (CLIP_X, CLIP_Y, 0) with the normal (cos yaw, sin yaw, 0); keeps n.p >= c
CLIP_X = -1.5
CLIP_Y = -2.0
CLIP_YAW = -15.0
HAIR_CHUNKS = 3
# the donor's head is shorter and sits further back on its neck than the Ethics Assistant's: every head mesh is moved by this vector in the game frame (x forward, y left, z up) so that the
# eyes and nose line up with hers, the chin is as low as hers (no extra long neck) and the stump of the donor's neck sits nearly above her neck
HEAD_SHIFT = np.array([1.1, 0.0, -0.6])
VER = 'v2'                              # part of every obj file name (pac caches downloads by url: changed geometry needs a new name)

EXTRAS_SIZE = (1024, 1792)
EXTRAS_LAYOUT = {'Cyberware': (0, 0), 'EyeLashes': (0, 512), 'EyeBrows': (512, 512), 'EyeMakeup': (512, 768), 'Lipstick': (768, 768),
                 'Port': (0, 1024), 'PortSillicone': (512, 1024), 'PortScrews': (0, 1536), 'PortSilliconeShadow': (256, 1536)}
PORT_SIZES = {'Port': 512, 'PortSillicone': 512, 'PortScrews': 256, 'PortSilliconeShadow': 256}


def tint_of(params):
    for k in ('color2', 'color'):
        v = params.get(k)
        if v:
            nums = re.findall(r'-?\d*\.?\d+(?:[eE][+-]?\d+)?', v)
            if len(nums) >= 3:
                return np.array([float(x) for x in nums[:3]])
            if len(nums) == 1:
                return np.full(3, float(nums[0]))
    return np.ones(3)


def slot_image(d, name, apply_tint=True):
    """donor texture of a slot as a PIL RGBA image with the VMT $color2 multiplied in"""
    arr = np.asarray(d.texture_array(name)).astype(float)
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.full(arr.shape[:2] + (1,), 255.0)], 2)
    if apply_tint:
        shader, params = d.vmt_params(name)
        arr[..., :3] = np.clip(arr[..., :3] * tint_of(params), 0, 255)
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def clip_soup(P, N, UV, n, c):
    """keep n.p >= c; triangle soup (T,3,3) positions / normals and (T,3,2) uvs, the straddling triangles are cut exactly"""
    d = np.einsum('tkj,j->tk', P, n) - c
    inside = (d >= 0).all(1)
    outside = (d < 0).all(1)
    cross = ~(inside | outside)
    out_P, out_N, out_U = [P[inside]], [N[inside]], [UV[inside]]
    cp, cn, cu = [], [], []
    for t in np.nonzero(cross)[0]:
        dd = d[t]
        polyP, polyN, polyU = [], [], []
        for i in range(3):
            j = (i + 1) % 3
            if dd[i] >= 0:
                polyP.append(P[t][i]); polyN.append(N[t][i]); polyU.append(UV[t][i])
            if (dd[i] >= 0) != (dd[j] >= 0):
                f = dd[i] / (dd[i] - dd[j])
                polyP.append(P[t][i] + (P[t][j] - P[t][i]) * f)
                nn = N[t][i] + (N[t][j] - N[t][i]) * f
                polyN.append(nn / max(np.linalg.norm(nn), 1e-9))
                polyU.append(UV[t][i] + (UV[t][j] - UV[t][i]) * f)
        for i in range(1, len(polyP) - 1):
            cp.append([polyP[0], polyP[i], polyP[i + 1]])
            cn.append([polyN[0], polyN[i], polyN[i + 1]])
            cu.append([polyU[0], polyU[i], polyU[i + 1]])
    if cp:
        out_P.append(np.array(cp)); out_N.append(np.array(cn)); out_U.append(np.array(cu))
    return np.concatenate(out_P), np.concatenate(out_N), np.concatenate(out_U)


def wrap_uv(UV):
    """source textures repeat: bring every triangle's uvs into [0, 1) (pac wraps per vertex, so a triangle must not straddle the seam)"""
    return UV - np.floor(UV.min(axis=1, keepdims=True) + 1e-6)


DEC = np.array([3, 3, 3, 2, 2, 2, 4, 4])          # decimals of x y z nx ny nz u v


def uv_det(uv):
    """urlobj computes tangents per triangle with r = 1 / (s1 * t2 - s2 * t1): a triangle whose three uvs are collinear (determinant exactly 0) gets infinite / NaN tangents and renders black or
    garbage.  uv (T,3,2) in the uv space pac sees (u % 1, (1 - vt) % 1 = v)."""
    s1 = uv[:, 1, 0] - uv[:, 0, 0]
    s2 = uv[:, 2, 0] - uv[:, 0, 0]
    t1 = uv[:, 1, 1] - uv[:, 0, 1]
    t2 = uv[:, 2, 1] - uv[:, 0, 1]
    return s1 * t2 - s2 * t1


def repair_uv(UVq, q):
    """UVq (T,3,2) quantised to q: nudge one corner of every uv-degenerate triangle by a quantum or two until its determinant is not zero; -> (UVq, number repaired)"""
    lo, hi = q, 1.0 - q
    bad = np.nonzero(np.abs(uv_det(UVq)) < 0.5 * q * q)[0]
    steps = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1), (2, 0), (0, 2), (-2, 0), (0, -2), (3, 1), (1, 3)]
    fixed = 0
    for t in bad:
        done = False
        for corner in (2, 1, 0):
            for dx, dy in steps:
                trial = UVq[t].copy()
                trial[corner] += np.array([dx, dy]) * q
                if trial.min() < lo - 1e-12 or trial.max() > hi + 1e-12:
                    continue
                if abs(uv_det(trial[None])[0]) >= 0.5 * q * q:
                    UVq[t] = trial
                    done = True
                    break
            if done:
                break
        if not done:                              # all three uvs equal: one moved corner is not enough (two equal points + one are still collinear), move two
            for d1, d2 in (((1, 0), (0, 1)), ((-1, 0), (0, -1)), ((1, 0), (0, -1)), ((-1, 0), (0, 1))):
                trial = UVq[t].copy()
                trial[1] += np.array(d1) * q
                trial[2] += np.array(d2) * q
                if trial.min() < lo - 1e-12 or trial.max() > hi + 1e-12:
                    continue
                if abs(uv_det(trial[None])[0]) >= 0.5 * q * q:
                    UVq[t] = trial
                    done = True
                    break
        fixed += done
    return UVq, fixed


def merge_quads(faces):
    """triangle index rows -> face rows: two triangles (p,q,r) + (p,r,d) that share the edge p-r are written as one quad p q r d.  pac fans a polygon from its first corner, which gives exactly the two
    triangles back, and the file gets a third shorter (the face lines are most of an obj's bytes)"""
    edge = {}
    for t, (a, b, c) in enumerate(faces):
        edge[(a, b)] = (t, c)
        edge[(b, c)] = (t, a)
        edge[(c, a)] = (t, b)
    used = np.zeros(len(faces), bool)
    out = []
    for t, (a, b, c) in enumerate(faces):
        if used[t]:
            continue
        used[t] = True
        for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
            hit = edge.get((p, r))
            if hit is not None and not used[hit[0]]:
                used[hit[0]] = True
                out.append((p, q, r, hit[1]))
                break
        else:
            out.append((a, b, c))
    return out


def write_obj(path, name, P, N, UV, comment='', flip=None, dec=None):
    """triangle soup -> indexed OBJ, vertices shared when position / normal / uv agree after rounding (dec = decimals of x y z nx ny nz u v); faces counter clockwise outside (decided by the vertex
    normals); vt = (u, 1 - v_down).  Zero area triangles are dropped and uv-degenerate ones (see uv_det) get a corner nudged by a uv quantum."""
    dec = DEC if dec is None else np.asarray(dec)
    area2 = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    keep = area2 > 2e-8
    if not keep.all():
        P, N, UV = P[keep], N[keep], UV[keep]
    q = 10.0 ** -int(dec[6])
    UVq = np.clip(np.round(UV * 10.0 ** dec[6]) / 10.0 ** dec[6], q, 1.0 - q)
    UVq, fixed = repair_uv(UVq, q)
    T = len(P)
    if flip is None:
        gn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        flip = float(((gn * N.mean(1)).sum(1) > 0).mean()) < 0.5
    corners = np.hstack([P.reshape(-1, 3), N.reshape(-1, 3), UVq.reshape(-1, 2)])
    key = np.round(corners * 10.0 ** dec) / 10.0 ** dec
    uk, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    faces = inv.reshape(T, 3)
    if flip:
        faces = faces[:, ::-1]
    V = key[first]
    nrm = V[:, 3:6]
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    uv = V[:, 6:8]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='\n') as f:
        f.write('# claude skill made by ax0rz0\n# %s\n' % (comment or name))
        f.write('o %s\n' % name)
        fv, fu = '%%.%df' % dec[0], '%%.%df' % dec[6]
        for v in V[:, :3]:
            f.write(('v %s %s %s\n' % (fv, fv, fv)) % tuple(v))
        for t in uv:
            f.write(('vt %s %s\n' % (fu, fu)) % (t[0], 1.0 - t[1]))
        for n in nrm:
            f.write('vn %.2f %.2f %.2f\n' % tuple(n))
        for fc in merge_quads(faces):
            f.write('f ' + ' '.join('%d/%d/%d' % (i + 1, i + 1, i + 1) for i in fc) + '\n')
    return len(V), T, os.path.getsize(path), flip


def cut_ring(p, n, c, tol=1e-6):
    """points of the boundary edges of the clipped triangle soup p (T,3,3) that lie on the cut plane n.p = c, as one loop sorted by angle in the plane -> (R,3)"""
    key = np.round(p * 4000).astype(np.int64)
    cnt, mid = {}, {}
    for t in range(len(p)):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ka, kb = tuple(key[t, a]), tuple(key[t, b])
            if ka == kb:
                continue
            e = (ka, kb) if ka < kb else (kb, ka)
            cnt[e] = cnt.get(e, 0) + 1
            mid[e] = (p[t, a], p[t, b])
    pts = []
    for e, k in cnt.items():
        if k == 1:
            a, b = mid[e]
            if abs(a @ n - c) < tol and abs(b @ n - c) < tol:
                pts += [a, b]
    pts = np.unique(np.round(np.array(pts), 5), axis=0)
    cen = pts.mean(0)
    u = np.cross(n, [0.0, 0.0, 1.0])
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    ang = np.arctan2((pts - cen) @ v, (pts - cen) @ u)
    return pts[np.argsort(ang)]


def drop_shreds(p, n, u):
    """the donor's neck flange left thin ragged ribbons in front of the stump where the clip plane cut it (a notch in the stump's front wall): drop them (head-bone coordinates, before the shift)"""
    cen = p.mean(1)
    rib = (cen[:, 1] > -1.25) & (cen[:, 1] < -0.8) & (cen[:, 0] > -1.4) & (cen[:, 0] < -0.15) & (np.abs(cen[:, 2]) < 1.2)
    return p[~rib], n[~rib], u[~rib]


def skin_patch(head_img, size=56, rows=(96, 220), cols=(160, 900)):
    """a plain skin window of the head texture (head_img: the 1024^2 PIL image) for the neck column: the quietest 56 px square in the neck band whose mean is closest to the colour the donor's neck
    stump has where it is cut -> (u0, v0, du, dv) in coordinates of the 2048x1024 atlas (the head texture is its left half)"""
    arr = np.asarray(head_img).astype(float)
    h, w = arr.shape[:2]
    target = np.array([151.3, 118.6, 98.3])                                                # texture colour at the cut vertices of the stump (measured: std 3)
    best = None
    for y in range(rows[0], rows[1] - size, 4):
        for x in range(cols[0], cols[1] - size, 4):
            win = arr[y:y + size, x:x + size].reshape(-1, 3)
            score = win.std(0).sum() + 0.4 * np.abs(win.mean(0) - target).sum()
            if best is None or score < best[0]:
                best = (score, x, y)
    _, x, y = best
    return (x / 2048.0, y / 1024.0, size / 2048.0, size / 1024.0)


def build(stage_root, head_tex=1024):
    obj_dir = os.path.join(stage_root, 'obj', 'adv')
    tex_dir = os.path.join(stage_root, 'tex', 'adv')
    os.makedirs(obj_dir, exist_ok=True)
    os.makedirs(tex_dir, exist_ok=True)
    d, tr, P, N = rdp.load()
    sc = asn.Scene()
    W = sc.rig.world[sc.rig.bone('Head1')]
    Rh, oh = W[:3, :3], W[:3, 3]
    Pl = ((P.reshape(-1, 3) - oh) @ Rh).reshape(P.shape)
    Nl = (N.reshape(-1, 3) @ Rh).reshape(N.shape)
    UV = tr['uv']
    slot = tr['slot']
    yaw = np.radians(CLIP_YAW)
    cn = np.array([np.cos(yaw), np.sin(yaw), 0.0])
    cc = float(cn @ np.array([CLIP_X, CLIP_Y, 0.0]))
    shift = HEAD_SHIFT @ Rh                                                              # the world shift in head-bone coordinates

    def soup(name):
        sel = np.nonzero(slot == d.tex.index(name))[0]
        return Pl[sel], Nl[sel], UV[sel]

    out = {'obj': {}, 'tex': {}, 'stats': {}}

    # ---- skin
    p, n, u = soup('Head')
    p, n, u = clip_soup(p, n, wrap_uv(u), cn, cc)
    ring = cut_ring(p, cn, cc)                                                           # the open end of the donor's neck stump (the neck column plugs it)
    p, n, u = drop_shreds(p, n, u)
    out['ring_world'] = oh + (ring + shift) @ Rh.T
    out['ring_normal_world'] = Rh @ cn                                                   # points into the head
    out['canal_axis_world'] = Rh[:, 0]                                                   # the head bone's long axis (up): the stump runs along it
    p = p + shift
    u = np.stack([u[..., 0] * 0.5, u[..., 1]], -1)                                       # the head texture is the left half of the 2048x1024 atlas
    Ps, Ns, Us = [p], [n], [u]
    # the eyeballs share the mesh: the two 512^2 eye textures sit in the right half, one above the other quarter
    atlas = Image.new('RGB', (2048, 1024))
    head_img = slot_image(d, 'Head').convert('RGB').resize((head_tex, head_tex), Image.LANCZOS)
    atlas.paste(head_img, (0, 0))
    out['neck_patch'] = skin_patch(head_img)
    for sname, x in (('EyeL', 1024), ('EyeR', 1536)):
        atlas.paste(slot_image(d, sname).convert('RGB'), (x, 0))
        pe, ne, ue = soup(sname)
        ue = wrap_uv(ue)
        ue = np.stack([(x + ue[..., 0] * 512) / 2048.0, (ue[..., 1] * 512) / 1024.0], -1)
        Ps.append(pe + shift); Ns.append(ne); Us.append(ue)
    fn = 'hd_head_%s.obj' % VER
    out['stats']['head'] = write_obj(os.path.join(obj_dir, fn), 'hd_head', np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Us), 'donor head skin (cut under the skull) + eyeballs',
                                     dec=[2, 2, 2, 2, 2, 2, 3, 3])
    out['obj']['head'] = fn
    atlas.save(os.path.join(tex_dir, 'hd_head.jpg'), quality=90, optimize=True)
    out['tex']['head'] = 'hd_head.jpg'

    # ---- extras: overlays + the cyber port in one translucent atlas (opaque plates get alpha 255)
    images = {}
    for sname in EXTRAS_LAYOUT:
        im = slot_image(d, sname)
        if sname in PORT_SIZES:
            im = im.resize((PORT_SIZES[sname],) * 2, Image.LANCZOS)
            if sname in ('Port', 'PortSillicone'):
                a = np.asarray(im).copy()
                a[..., 3] = 255
                im = Image.fromarray(a, 'RGBA')
        images[sname] = im
    atlas = Image.new('RGBA', EXTRAS_SIZE, (0, 0, 0, 0))
    rects = {}
    for sname, im in images.items():
        x, y = EXTRAS_LAYOUT[sname]
        assert x + im.size[0] <= EXTRAS_SIZE[0] and y + im.size[1] <= EXTRAS_SIZE[1], (sname, im.size)
        atlas.paste(im, (x, y))
        rects[sname] = (x, y, im.size[0], im.size[1])
    Ps, Ns, Us = [], [], []
    for sname in EXTRAS_LAYOUT:
        p, n, u = soup(sname)
        p, n, u = clip_soup(p, n, wrap_uv(u), cn, cc)
        x, y, w, h = rects[sname]
        u = np.stack([(x + u[..., 0] * w) / EXTRAS_SIZE[0], (y + u[..., 1] * h) / EXTRAS_SIZE[1]], -1)
        Ps.append(p + shift); Ns.append(n); Us.append(u)
    fn = 'hd_extras_%s.obj' % VER
    out['stats']['extras'] = write_obj(os.path.join(obj_dir, fn), 'hd_extras', np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Us),
                                       'lipstick, eye makeup, brows, cyberware lines, lashes, nape port')
    out['obj']['extras'] = fn
    atlas.save(os.path.join(tex_dir, 'hd_extras.png'), optimize=True)
    out['tex']['extras'] = 'hd_extras.png'

    # ---- hair, in chunks of consecutive cards
    p, n, u = soup('Hair')
    p = p + shift
    u = wrap_uv(u)
    flip = float(((np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]) * n.mean(1)).sum(1) > 0).mean()) < 0.5
    for i, idx in enumerate(np.array_split(np.arange(len(p)), HAIR_CHUNKS)):
        key = 'hair_' + 'abcdefgh'[i]
        fn = 'hd_%s_%s.obj' % (key, VER)
        out['stats'][key] = write_obj(os.path.join(obj_dir, fn), 'hd_' + key, p[idx], n[idx], u[idx], 'donor hair cards, part %d of %d (alpha tested, no culling)' % (i + 1, HAIR_CHUNKS), flip=flip)
        out['obj'][key] = fn
    im = slot_image(d, 'Hair')
    q = Image.fromarray(np.asarray(im)).quantize(colors=256, method=Image.FASTOCTREE, dither=Image.NONE)
    q.save(os.path.join(tex_dir, 'hd_hair.png'), optimize=True)
    out['tex']['hair'] = 'hd_hair.png'
    for k, fn in out['tex'].items():
        out['stats']['tex_' + k] = os.path.getsize(os.path.join(tex_dir, fn))
    return out


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
    r = build(root)
    for k, v in r['stats'].items():
        print(k, v)
