"""Image side of the pin badge generator: load, square/resample, quantise, and build the
geometry mosaic (one OBJ layer per palette colour).  Frame and cell mapping per SPEC.md:

    x = R - (r + 0.5) * 2R/N          (image up)
    z = -R + (c + 0.5) * 2R/N         (image right as seen from the front)
    polygons are CCW in (z, x); vertices sit on dome_y(x, z, R).
"""
import io
import math
import os
import urllib.request

import numpy as np
from PIL import Image, ImageOps

from pin_common import (DEFAULT_DIAMETER, MAX_LAYER_TRIS, MeshBuilder, circle_polygon,
                        clip_convex, dome_y, hex_color, write_obj)

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')
MAX_DOWNLOAD = 64 * 1024 * 1024


# ---------------------------------------------------------------- loading
def _is_url(src):
    return isinstance(src, str) and src.lower().startswith(('http://', 'https://'))


def read_source_bytes(src):
    """Raw bytes of an image given as a local path or http(s) URL (for hashing and loading)."""
    if _is_url(src):
        req = urllib.request.Request(src, headers={
            'User-Agent': USER_AGENT,
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        })
        # urlopen follows redirects (GitHub raw -> raw.githubusercontent.com) by default
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read(MAX_DOWNLOAD + 1)
        if len(data) > MAX_DOWNLOAD:
            raise ValueError('image at %s is larger than %d MB' % (src, MAX_DOWNLOAD >> 20))
        return data
    with open(src, 'rb') as f:
        return f.read()


def _to_rgba(im):
    """Any Pillow mode -> RGBA (handles palette+transparency, grayscale, 16-bit, CMYK, 1-bit)."""
    if im.mode == 'RGBA':
        return im
    if im.mode in ('I;16', 'I;16L', 'I;16B', 'I', 'F'):
        a = np.asarray(im, dtype=np.float64)
        hi = a.max() if a.size else 1.0
        a = a / (65535.0 if hi > 255 else 255.0) * 255.0
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'L')
    if im.mode == 'P' and 'transparency' in im.info:
        return im.convert('RGBA')
    return im.convert('RGBA')


def load_image(src):
    """Load png/jpg/webp/gif (first frame)/palette/grayscale from a path or URL -> PIL RGBA."""
    if isinstance(src, Image.Image):
        im = src
    else:
        im = Image.open(io.BytesIO(read_source_bytes(src)))
        try:
            im.seek(0)                      # animated gif/webp: first frame
        except EOFError:
            pass
        im.load()
        im = ImageOps.exif_transpose(im) or im
    return _to_rgba(im).copy()


# ---------------------------------------------------------------- prepare
_RESAMPLE = {
    'nearest': Image.NEAREST, 'lanczos': Image.LANCZOS, 'bilinear': Image.BILINEAR,
    'bicubic': Image.BICUBIC, 'box': Image.BOX, 'hamming': Image.HAMMING,
}


def prepare(img, res=64, fit='crop', bg=(255, 255, 255), resample='auto'):
    """-> RGB res x res image. fit 'crop' = centre-crop square, 'pad' = letterbox with bg.
    Alpha is composited over bg first. resample 'auto': NEAREST for small pixel art
    (<= 2*res on both sides) else LANCZOS."""
    img = _to_rgba(img)
    w, h = img.size
    bg = tuple(int(v) for v in bg[:3])
    flat = Image.new('RGBA', img.size, bg + (255,))
    flat.alpha_composite(img)
    flat = flat.convert('RGB')

    if fit == 'pad':
        side = max(w, h)
        canvas = Image.new('RGB', (side, side), bg)
        canvas.paste(flat, ((side - w) // 2, (side - h) // 2))
        sq = canvas
    elif fit == 'crop':
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
        sq = flat.crop((left, top, left + side, top + side))
    else:
        raise ValueError("fit must be 'crop' or 'pad'")

    if resample == 'auto':
        mode = Image.NEAREST if (w <= 2 * res and h <= 2 * res) else Image.LANCZOS
    else:
        mode = _RESAMPLE[resample.lower()]
    if sq.size != (res, res):
        sq = sq.resize((res, res), mode)
    return sq


# ---------------------------------------------------------------- quantise
def _inside_mask(n):
    """bool n x n: cell centre inside the inscribed circle (grid units)."""
    idx = np.arange(n) + 0.5 - n / 2.0
    return (idx[:, None] ** 2 + idx[None, :] ** 2) <= (n / 2.0) ** 2


def quantize(img, colors=16, min_pixels=3, merge_dist=10):
    """-> (index_grid [[int]] res x res, palette [(r, g, b)]). MEDIANCUT, no dither; merges
    near-identical entries and folds colours with < min_pixels in-circle cells into the
    nearest survivor. Only cells whose centre is inside the circle are counted."""
    img = img.convert('RGB')
    n = img.size[0]
    assert img.size == (n, n), 'quantize expects a square image (use prepare)'
    q = img.quantize(colors=max(2, int(colors)), method=Image.Quantize.MEDIANCUT,
                     dither=Image.Dither.NONE)
    grid = np.array(q, dtype=np.int64)
    pal_flat = q.getpalette() or []
    k = len(pal_flat) // 3
    pal = np.array(pal_flat[:3 * k], dtype=np.float64).reshape(-1, 3)
    k = max(k, int(grid.max()) + 1)
    if len(pal) < k:
        pal = np.vstack([pal, np.zeros((k - len(pal), 3))])

    inside = _inside_mask(n)
    cnt_in = np.bincount(grid[inside], minlength=k)
    cnt_all = np.bincount(grid.ravel(), minlength=k)

    # 1) merge entries closer than merge_dist: larger (in-circle, then total) absorbs smaller
    order = sorted((i for i in range(k) if cnt_all[i] > 0), key=lambda i: (-cnt_in[i], -cnt_all[i], i))
    remap = np.arange(k)
    kept = []
    for i in order:
        best, bd = None, None
        for j in kept:
            d = float(np.linalg.norm(pal[i] - pal[j]))
            if bd is None or d < bd:
                best, bd = j, d
        if best is not None and bd < merge_dist:
            remap[i] = best
        else:
            kept.append(i)
    grid = remap[grid]
    cnt_in = np.bincount(grid[inside], minlength=k)

    # 2) fold rare colours into the nearest survivor
    surv = [i for i in kept if cnt_in[i] >= min_pixels]
    if not surv:
        surv = [max(kept, key=lambda i: (cnt_in[i], cnt_all[i]))]
    remap2 = np.arange(k)
    for i in kept:
        if i not in surv:
            remap2[i] = min(surv, key=lambda j: float(np.linalg.norm(pal[i] - pal[j])))
    grid = remap2[grid]
    cnt_in = np.bincount(grid[inside], minlength=k)

    # 3) compact: palette ordered by in-circle pixel count, descending
    surv.sort(key=lambda i: (-cnt_in[i], i))
    compact = np.zeros(k, dtype=np.int64)
    for new, old in enumerate(surv):
        compact[old] = new
    grid = compact[grid]
    palette = [tuple(int(round(v)) for v in pal[i]) for i in surv]
    return grid.tolist(), palette


# ---------------------------------------------------------------- mosaic
def build_mosaic(index_grid, palette, out_dir, file_for_key, diameter=DEFAULT_DIAMETER):
    """Write one OBJ per palette colour (keys c01.. ordered by in-circle pixel count desc).

    file_for_key: callable key -> file name (joined onto out_dir; absolute paths pass through),
    or a dict / '%s' format string. Returns (parts, edge_color): parts are manifest-style dicts
    (key, role 'image', label 'mosaic #rrggbb', file, local_path, color 0..1, alpha, translucent,
    hidden False, material None, pixels, verts, tris); edge_color is the most common colour (0..1)
    among in-circle cells whose centre radius > 0.85 R."""
    n = len(index_grid)
    R = diameter / 2.0
    s = 2.0 * R / n
    zs = [-R + i * s for i in range(n + 1)]
    xs = [R - i * s for i in range(n + 1)]
    circle = circle_polygon(R)                           # (z, x), CCW
    apothem2 = (R * math.cos(math.pi / len(circle))) ** 2

    builders = {}
    pixels = {}
    edge = {}
    for r in range(n):
        xt, xb = xs[r], xs[r + 1]
        for c in range(n):
            ci = index_grid[r][c]
            cz, cx = (zs[c] + zs[c + 1]) * 0.5, (xt + xb) * 0.5
            rc = math.hypot(cz, cx)
            if rc <= R:
                pixels[ci] = pixels.get(ci, 0) + 1
                if rc > 0.85 * R:
                    edge[ci] = edge.get(ci, 0) + 1
            z0, z1 = zs[c], zs[c + 1]
            dz, dx = max(z0, -z1, 0.0), max(xb, -xt, 0.0)
            if dz * dz + dx * dx >= R * R:
                continue                                  # fully outside the disc
            if max(z0 * z0, z1 * z1) + max(xb * xb, xt * xt) <= apothem2:
                poly = [(z0, xb), (z1, xb), (z1, xt), (z0, xt)]    # fully inside: no clip
            else:
                poly = clip_convex([(z0, xb), (z1, xb), (z1, xt), (z0, xt)], circle)
            clean = []
            for p in poly:
                if not clean or abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
                    clean.append(p)
            if len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) <= 1e-9 and abs(clean[0][1] - clean[-1][1]) <= 1e-9:
                clean.pop()
            if len(clean) < 3:
                continue
            mb = builders.get(ci)
            if mb is None:
                mb = builders[ci] = MeshBuilder()
            idx = [mb.vertex((p[1], dome_y(p[1], p[0], R), p[0])) for p in clean]
            for k in range(1, len(clean) - 1):
                a, b, d = clean[0], clean[k], clean[k + 1]
                area2 = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
                if area2 > 1e-12:                         # drops zero-area slivers (CCW => positive)
                    mb.tri(idx[0], idx[k], idx[k + 1])

    ranked = sorted(builders, key=lambda i: (-pixels.get(i, 0), i))
    parts = []
    for rank, ci in enumerate(ranked, 1):
        key = 'c%02d' % rank
        mb = builders[ci]
        assert mb.tris, 'empty layer %s' % key
        assert len(mb.tris) <= MAX_LAYER_TRIS, \
            'layer %s has %d triangles (> %d); lower res or colours' % (key, len(mb.tris), MAX_LAYER_TRIS)
        if callable(file_for_key):
            fname = file_for_key(key)
        elif isinstance(file_for_key, dict):
            fname = file_for_key[key]
        else:
            fname = file_for_key % key
        path = os.path.join(out_dir, fname)
        write_obj(path, mb.verts, mb.tris, comment='pin badge mosaic layer %s' % key)
        col = tuple(v / 255.0 for v in palette[ci])
        parts.append({
            'key': key, 'role': 'image', 'label': 'mosaic ' + hex_color(col),
            'file': os.path.basename(fname), 'local_path': path,
            'color': [round(v, 4) for v in col], 'alpha': 1.0, 'translucent': False,
            'hidden': False, 'material': None, 'pixels': pixels.get(ci, 0),
            'verts': len(mb.verts), 'tris': len(mb.tris),
        })

    if edge:
        ec = palette[max(edge, key=lambda i: (edge[i], -i))]
    elif pixels:
        ec = palette[max(pixels, key=lambda i: (pixels[i], -i))]
    else:
        ec = (255, 255, 255)
    return parts, tuple(round(v / 255.0, 4) for v in ec)
