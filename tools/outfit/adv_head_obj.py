"""The Song So Mi head (Cyberpunk 2077: Phantom Liberty, Workshop 3283215678) as plain GitHub-hosted assets: OBJ meshes in the Ethics Assistant's head-bone frame + PNG / JPG textures, so that pac downloads
everything itself and nobody needs the Workshop addon.

The donor's compiled model is read with mdl_mesh / donor_tools (it is never run), skinned into the player's bind frame (BoneMerge math), moved into the head bone's local frame and split into
static meshes, every file under 1 MB:
  hd_head       the Head slot, cut under the skull by a plane (the donor's own neck is a wide flat flange; the neck is hd_neck.obj) + EyeL + EyeR   texture hd_head.jpg (2048x1024: Head_c 1024^2 | the eyes)
  hd_extras     Lipstick + EyeMakeup + EyeBrows + Cyberware + EyeLashes (thin shells 0.015 above the skin) + the cyber port at the nape    texture hd_extras.png (one atlas, the $color2 tints baked in)
  hd_hair_a..c  Hair (alpha tested cards, no culling) in three chunks, $color2 2.5 baked into the texture                                 texture hd_hair.png   (palette png with alpha)
Winding: the donor is clockwise outside, pac reverses obj winding, so the faces are written counter clockwise outside.  uvs are written as (u, 1 - v) because pac flips v and wraps with % 1.

    build(stage_root)  ->  {'obj': {key: filename}, 'tex': {key: filename}, 'stats': ..., 'nape_uv': (u, v)}   (files go to <stage_root>/obj/adv and <stage_root>/tex/adv)
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


def write_obj(path, name, P, N, UV, comment='', flip=None, dec=None):
    """triangle soup -> indexed OBJ, vertices shared when position / normal / uv agree after rounding (dec = decimals of x y z nx ny nz u v); faces counter clockwise outside (decided by the vertex
    normals); vt = (u, 1 - v_down)"""
    T = len(P)
    if flip is None:
        gn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        flip = float(((gn * N.mean(1)).sum(1) > 0).mean()) < 0.5
    corners = np.hstack([P.reshape(-1, 3), N.reshape(-1, 3), UV.reshape(-1, 2)])
    dec = DEC if dec is None else np.asarray(dec)
    key = np.round(corners * 10.0 ** dec) / 10.0 ** dec
    uk, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    faces = inv.reshape(T, 3)
    if flip:
        faces = faces[:, ::-1]
    V = key[first]
    nrm = V[:, 3:6]
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    uv = np.clip(V[:, 6:8], 0.0005, 0.9995)
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
        for a, b, c in faces:
            f.write('f %d/%d/%d %d/%d/%d %d/%d/%d\n' % (a + 1, a + 1, a + 1, b + 1, b + 1, b + 1, c + 1, c + 1, c + 1))
    return len(V), T, os.path.getsize(path), flip


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

    def soup(name):
        sel = np.nonzero(slot == d.tex.index(name))[0]
        return Pl[sel], Nl[sel], UV[sel]

    out = {'obj': {}, 'tex': {}, 'stats': {}}

    # ---- skin
    p, n, u = soup('Head')
    # the neck column borrows a small patch of the skin texture from the nape just above the cut, so that it shares the head's material and colour
    cen = p.mean(1)
    near = (cen[:, 0] > CLIP_X) & (cen[:, 0] < CLIP_X + 1.2) & (cen[:, 1] > 1.0)
    out['nape_uv'] = tuple(float(x) for x in np.median(wrap_uv(u)[near].reshape(-1, 2), axis=0))
    p, n, u = clip_soup(p, n, wrap_uv(u), cn, cc)
    u = np.stack([u[..., 0] * 0.5, u[..., 1]], -1)                                       # the head texture is the left half of the 2048x1024 atlas
    Ps, Ns, Us = [p], [n], [u]
    # the eyeballs share the mesh: the two 512^2 eye textures sit in the right half, one above the other quarter
    atlas = Image.new('RGB', (2048, 1024))
    atlas.paste(slot_image(d, 'Head').convert('RGB').resize((head_tex, head_tex), Image.LANCZOS), (0, 0))
    for sname, x in (('EyeL', 1024), ('EyeR', 1536)):
        atlas.paste(slot_image(d, sname).convert('RGB'), (x, 0))
        pe, ne, ue = soup(sname)
        ue = wrap_uv(ue)
        ue = np.stack([(x + ue[..., 0] * 512) / 2048.0, (ue[..., 1] * 512) / 1024.0], -1)
        Ps.append(pe); Ns.append(ne); Us.append(ue)
    out['stats']['head'] = write_obj(os.path.join(obj_dir, 'hd_head.obj'), 'hd_head', np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Us), 'donor head skin (cut under the skull) + eyeballs',
                                     dec=[2, 2, 2, 2, 2, 2, 3, 3])
    out['obj']['head'] = 'hd_head.obj'
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
        Ps.append(p); Ns.append(n); Us.append(u)
    out['stats']['extras'] = write_obj(os.path.join(obj_dir, 'hd_extras.obj'), 'hd_extras', np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Us),
                                       'lipstick, eye makeup, brows, cyberware lines, lashes, nape port')
    out['obj']['extras'] = 'hd_extras.obj'
    atlas.save(os.path.join(tex_dir, 'hd_extras.png'), optimize=True)
    out['tex']['extras'] = 'hd_extras.png'

    # ---- hair, in chunks of consecutive cards
    p, n, u = soup('Hair')
    u = wrap_uv(u)
    flip = float(((np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]) * n.mean(1)).sum(1) > 0).mean()) < 0.5
    for i, idx in enumerate(np.array_split(np.arange(len(p)), HAIR_CHUNKS)):
        key = 'hair_' + 'abcdefgh'[i]
        fn = 'hd_%s.obj' % key
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
