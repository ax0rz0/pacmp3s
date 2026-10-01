"""Software preview renderer for the pin badge (numpy z-buffer, orthographic).

Works in the badge frame of SPEC.md (OBJ coordinates, +Y = face normal, +X = image up,
+Z = image right for a viewer standing in front of the wearer).

Views (camera basis in badge coordinates; depth is the component along the camera axis `w`):
    front          w = +Y, screen right = +Z, screen up = +X
    three_quarter  front rotated 35 deg about X (camera swings toward +Z), then tilted 20 deg
                   (camera rises toward +X)
    side           w = +Z, screen up = +X, screen right = -Y

Public API:
    render(manifest, view='front', size=640, texture_image=None) -> PIL RGB image
    orientation_check(manifest, reference_rgb, res, texture_image=None) -> dict
    contact_sheet(images, labels, path) -> path
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import pin_common as pc

BACKGROUND = (0x1e, 0x1f, 0x22)
VIEWS = ('front', 'three_quarter', 'side')
VIEW_EXTENT = 1.25          # visible width/height of the render in badge diameters
VIEW_CENTER = (0.0, 0.06, 0.0)
AMBIENT = 0.55              # flat shading: ambient + (1 - ambient) * |n . w|
_EPS = -1e-7                # barycentric inclusion tolerance (keeps shared edges crack free)


# ---------------------------------------------------------------- camera
def _view_basis(view):
    """Return (right, up, toward_camera) unit vectors in badge coordinates (right-handed: r x u = w)."""
    r = np.array([0.0, 0.0, 1.0])
    u = np.array([1.0, 0.0, 0.0])
    w = np.array([0.0, 1.0, 0.0])
    if view == 'front':
        return r, u, w
    if view == 'side':
        w = np.array([0.0, 0.0, 1.0])
        r = np.cross(u, w)          # (0, -1, 0)
        return r, u, w
    if view == 'three_quarter':
        a, t = math.radians(35.0), math.radians(20.0)
        w1 = w * math.cos(a) + r * math.sin(a)
        r1 = r * math.cos(a) - w * math.sin(a)
        w2 = w1 * math.cos(t) + u * math.sin(t)
        u2 = u * math.cos(t) - w1 * math.sin(t)
        return r1, u2, w2
    raise ValueError('unknown view %r (expected one of %s)' % (view, ', '.join(VIEWS)))


def _scale_for(manifest, size):
    d = float(manifest.get('diameter') or pc.DEFAULT_DIAMETER)
    return size / (VIEW_EXTENT * d)


# ---------------------------------------------------------------- rasteriser
def _bilinear(tex, u, v):
    """tex: (H, W, 3) float. u, v 1-D arrays; OBJ v=1 is the image top."""
    h, w = tex.shape[:2]
    fx = u * w - 0.5
    fy = (1.0 - v) * h - 0.5
    x0 = np.floor(fx)
    y0 = np.floor(fy)
    tx = (fx - x0)[:, None]
    ty = (fy - y0)[:, None]
    x0 = x0.astype(np.int64)
    y0 = y0.astype(np.int64)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    x0 = np.clip(x0, 0, w - 1)
    y0 = np.clip(y0, 0, h - 1)
    top = tex[y0, x0] * (1 - tx) + tex[y0, x1] * tx
    bot = tex[y1, x0] * (1 - tx) + tex[y1, x1] * tx
    return top * (1 - ty) + bot * ty


def _raster(zbuf, img, sx, sy, sz, tris, tri_rgb, uv=None, tex=None, tint=None, visible=None):
    """Rasterise triangles into zbuf (S, S) / img (S, S, 3). Larger depth = nearer.

    sx, sy, sz: per-vertex screen x, y (pixels, y down) and depth. tri_rgb: (T, 3) flat colour per
    triangle. uv/tex/tint: texturing (colour = tex(uv) * tint * shade, shade from tri_rgb / base).
    visible: optional bool array (T,) of triangles allowed to draw (back-face culling).
    """
    size = zbuf.shape[0]
    t = np.asarray(tris, dtype=np.int64)
    if len(t) == 0:
        return
    x = sx[t]
    y = sy[t]
    j0 = np.maximum(np.ceil(x.min(axis=1) - 0.5), 0).astype(np.int64)
    j1 = np.minimum(np.floor(x.max(axis=1) - 0.5), size - 1).astype(np.int64)
    i0 = np.maximum(np.ceil(y.min(axis=1) - 0.5), 0).astype(np.int64)
    i1 = np.minimum(np.floor(y.max(axis=1) - 0.5), size - 1).astype(np.int64)
    area = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
    ok = (j1 >= j0) & (i1 >= i0) & (np.abs(area) > 1e-12)
    if visible is not None:
        ok &= visible
    idx = np.nonzero(ok)[0]
    if len(idx) == 0:
        return
    xs, ys, zs = x.tolist(), y.tolist(), sz[t].tolist()
    j0l, j1l, i0l, i1l, al = j0.tolist(), j1.tolist(), i0.tolist(), i1.tolist(), area.tolist()
    if tex is not None:
        uvt = np.asarray(uv)[t]                         # (T, 3, 2)
        ut, vt = uvt[:, :, 0].tolist(), uvt[:, :, 1].tolist()
        shade = tri_rgb                                  # (T,) scalar shade when texturing
    else:
        cols = tri_rgb
    for k in idx.tolist():
        xa, xb, xc = xs[k]
        ya, yb, yc = ys[k]
        a = al[k]
        px = np.arange(j0l[k], j1l[k] + 1) + 0.5
        py = (np.arange(i0l[k], i1l[k] + 1) + 0.5)[:, None]
        w0 = ((xb - px) * (yc - py) - (xc - px) * (yb - py)) / a
        w1 = ((xc - px) * (ya - py) - (xa - px) * (yc - py)) / a
        w2 = 1.0 - w0 - w1
        m = (w0 >= _EPS) & (w1 >= _EPS) & (w2 >= _EPS)
        za, zb_, zc = zs[k]
        z = w0 * za + w1 * zb_ + w2 * zc
        zsub = zbuf[i0l[k]:i1l[k] + 1, j0l[k]:j1l[k] + 1]
        m &= z > zsub
        if not m.any():
            continue
        zsub[m] = z[m]
        isub = img[i0l[k]:i1l[k] + 1, j0l[k]:j1l[k] + 1]
        if tex is None:
            isub[m] = cols[k]
        else:
            ua, ub, uc = ut[k]
            va, vb, vc = vt[k]
            uu = w0[m] * ua + w1[m] * ub + w2[m] * uc
            vv = w0[m] * va + w1[m] * vb + w2[m] * vc
            isub[m] = _bilinear(tex, uu, vv) * tint * shade[k]


def _load_part(part, manifest):
    path = part.get('local_path')
    if not path or not os.path.isfile(path):
        alt = os.path.join(pc.obj_dir(manifest.get('slug', '')), part.get('file', ''))
        if part.get('file') and os.path.isfile(alt):
            path = alt
        else:
            raise FileNotFoundError('OBJ for part %r not found (local_path=%r)' % (part.get('key'), part.get('local_path')))
    verts, tris, uvs = pc.read_obj(path)
    return np.asarray(verts, dtype=np.float64).reshape(-1, 3), np.asarray(tris, dtype=np.int64).reshape(-1, 3), uvs


def _prepare_texture(img):
    if img is None:
        return None
    if img.mode in ('RGBA', 'LA', 'P'):
        rgba = img.convert('RGBA')
        bg = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        img = bg
    return np.asarray(img.convert('RGB'), dtype=np.float32) / 255.0


def _render_array(manifest, view, size, texture_image, shading, cull, skip_roles, ssaa):
    """Return float32 (size, size, 3) 0..1 image."""
    S = size * ssaa
    r, u, w = _view_basis(view)
    scale = _scale_for(manifest, S)
    c = np.asarray(VIEW_CENTER)
    cr, cu = float(r @ c), float(u @ c)
    tex = _prepare_texture(texture_image)
    bg = np.asarray(BACKGROUND, dtype=np.float32) / 255.0

    zbuf = np.full((S, S), -np.inf, dtype=np.float64)
    img = np.empty((S, S, 3), dtype=np.float32)
    img[:] = bg

    translucent = []
    for part in manifest.get('parts', []):
        if part.get('hidden'):
            continue
        if part.get('role') in skip_roles:
            continue
        role = part.get('role')
        is_tex = role == 'texture'
        if is_tex and tex is None:
            continue
        verts, tris, uvs = _load_part(part, manifest)
        if len(tris) == 0:
            continue
        if is_tex and uvs is None:
            continue
        alpha = float(part.get('alpha', 1.0))
        is_trans = bool(part.get('translucent')) or alpha < 0.999
        sx = S / 2.0 + (verts @ r - cr) * scale
        sy = S / 2.0 - (verts @ u - cu) * scale
        sz = verts @ w
        v0, v1, v2 = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
        n = np.cross(v1 - v0, v2 - v0)
        ln = np.linalg.norm(n, axis=1)
        nd = (n @ w) / np.maximum(ln, 1e-20)             # cos between normal and camera (signed)
        shade = (AMBIENT + (1.0 - AMBIENT) * np.abs(nd)) if shading else np.ones(len(tris))
        visible = (nd > 0) if cull else None
        col = np.asarray(part.get('color', (1, 1, 1)), dtype=np.float32)
        if is_tex:
            args = dict(uv=np.asarray(uvs, dtype=np.float64), tex=tex, tint=col)
            tri_rgb = shade.astype(np.float32)
        else:
            args = {}
            tri_rgb = (col[None, :] * shade[:, None].astype(np.float32))
        if is_trans:
            translucent.append((float(np.mean(sz)), alpha, sx, sy, sz, tris, tri_rgb, args, visible))
        else:
            _raster(zbuf, img, sx, sy, sz, tris, tri_rgb, visible=visible, **args)

    # translucent parts: far to near; each is resolved on its own first so overlapping triangles
    # inside one part blend only once, then composited over the opaque result.
    for _, alpha, sx, sy, sz, tris, tri_rgb, args, visible in sorted(translucent, key=lambda e: e[0]):
        pz = np.full((S, S), -np.inf, dtype=np.float64)
        pimg = np.zeros((S, S, 3), dtype=np.float32)
        _raster(pz, pimg, sx, sy, sz, tris, tri_rgb, visible=visible, **args)
        m = np.isfinite(pz) & (pz >= zbuf - 1e-4)
        img[m] = img[m] * (1.0 - alpha) + pimg[m] * alpha

    if ssaa > 1:
        img = img.reshape(size, ssaa, size, ssaa, 3).mean(axis=(1, 3))
    return np.clip(img, 0.0, 1.0)


# ---------------------------------------------------------------- public API
def render(manifest, view='front', size=640, texture_image=None, shading=True, cull=False, ssaa=2):
    """Render the badge. Returns a PIL RGB image (size x size).

    manifest: dict as in SPEC.md (uses parts[].local_path / file, color, alpha, translucent, hidden, role).
    texture_image: PIL image for role 'texture' parts; if None those parts are skipped.
    shading: flat headlight shading (ambient 0.55 + 0.45*|n.view|); front colours of the dome stay within 0.5%.
    cull: back-face culling (use it to check winding: front view of a correct mesh looks identical).
    ssaa: supersampling factor for smooth edges.
    """
    if view not in VIEWS:
        raise ValueError('unknown view %r (expected one of %s)' % (view, ', '.join(VIEWS)))
    arr = _render_array(manifest, view, int(size), texture_image, shading, cull, (), max(1, int(ssaa)))
    return Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8), 'RGB')


def orientation_check(manifest, reference_rgb, res, texture_image=None):
    """Compare the front render with `reference_rgb` (res x res PIL RGB image) at every cell centre
    inside 0.9R (SPEC cell mapping). Gloss / rim / back parts are ignored and there is no shading, so
    the comparison is on true part colours.

    Returns {'as_is', 'mirror_lr', 'mirror_ud', 'rot180': mean abs RGB error (0..255),
             'best': name, 'margin': 1 - as_is / next_best, 'cells': n, 'ok': bool}
    ok = as-is is the smallest error and at least 25% below the next best.
    """
    res = int(res)
    size = 8 * res
    arr = _render_array(manifest, 'front', size, texture_image, False, False, ('gloss', 'rim', 'back'), 1)
    arr = arr * 255.0
    ref = np.asarray(reference_rgb.convert('RGB').resize((res, res), Image.NEAREST)
                     if reference_rgb.size != (res, res) else reference_rgb.convert('RGB'), dtype=np.float64)

    R = float(manifest.get('diameter') or pc.DEFAULT_DIAMETER) / 2.0
    scale = _scale_for(manifest, size)
    rows, cols = np.mgrid[0:res, 0:res]
    xs = R - (rows + 0.5) * 2 * R / res
    zs = -R + (cols + 0.5) * 2 * R / res
    inside = np.hypot(xs, zs) <= 0.9 * R
    # front basis: right = +Z, up = +X, view centre has r.c = u.c = 0
    px = np.floor(size / 2.0 + zs * scale).astype(int)
    py = np.floor(size / 2.0 - xs * scale).astype(int)
    samp = np.zeros((res, res, 3))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            samp += arr[np.clip(py + dy, 0, size - 1), np.clip(px + dx, 0, size - 1)]
    samp /= 9.0

    variants = {
        'as_is': ref,
        'mirror_lr': ref[:, ::-1],
        'mirror_ud': ref[::-1, :],
        'rot180': ref[::-1, ::-1],
    }
    out = {}
    for name, v in variants.items():
        out[name] = float(np.abs(samp[inside] - v[inside]).mean()) if inside.any() else float('inf')
    others = [out[k] for k in ('mirror_lr', 'mirror_ud', 'rot180')]
    nxt = min(others)
    out['best'] = min(variants, key=lambda k: out[k])
    out['margin'] = float(1.0 - out['as_is'] / nxt) if nxt > 0 else 0.0
    out['cells'] = int(inside.sum())
    out['ok'] = bool(out['as_is'] < nxt and out['as_is'] <= 0.75 * nxt)
    return out


def contact_sheet(images, labels, path, cols=None, pad=10, label_h=28):
    """Save PNG with the images side by side (wrapping after `cols`), each with a label above it."""
    if len(images) != len(labels):
        raise ValueError('images and labels must have the same length')
    n = len(images)
    if n == 0:
        raise ValueError('no images')
    cols = n if not cols else min(int(cols), n)
    nrows = (n + cols - 1) // cols
    cw = max(im.width for im in images)
    ch = max(im.height for im in images)
    W = pad + cols * (cw + pad)
    H = pad + nrows * (label_h + ch + pad)
    sheet = Image.new('RGB', (W, H), BACKGROUND)
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=16)
    except TypeError:
        font = ImageFont.load_default()
    for i, (im, lab) in enumerate(zip(images, labels)):
        cx = pad + (i % cols) * (cw + pad)
        cy = pad + (i // cols) * (label_h + ch + pad)
        d.text((cx + 2, cy + 4), str(lab), fill=(235, 235, 235), font=font)
        sheet.paste(im.convert('RGB'), (cx + (cw - im.width) // 2, cy + label_h + (ch - im.height) // 2))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sheet.save(path, 'PNG')
    return path
