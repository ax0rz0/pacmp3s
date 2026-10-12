"""UV-space "position maps": rasterise a mesh into texture space so every texel knows its 3D position / normal / region id.
    pm = uv_raster(uv (T,3,2), {'pos': (T,3,3), 'nrm': (T,3,3), 'rid': (T,3,1)}, size=1024)  ->  dict(cover (H,W) bool, pos (H,W,3), nrm (H,W,3), rid (H,W)) after dilation by `pad` texels
UV rows follow the VVD convention (v is image-down). Coordinates are taken modulo 1 (the skirt atlas uses u in 1..2).
"""
import numpy as np


def uv_raster(uv, attrs, size=1024, density=1.7, pad=4):
    uv = np.asarray(uv, np.float64).copy()
    # triangles that straddle an integer UV boundary are rare; shift each triangle by the floor of its centroid so it stays contiguous
    cen = uv.mean(axis=1)
    uv -= np.floor(cen)[:, None, :]
    X = uv[..., 0] * size
    Y = uv[..., 1] * size
    e = np.stack([np.hypot(X[:, 1] - X[:, 0], Y[:, 1] - Y[:, 0]), np.hypot(X[:, 2] - X[:, 1], Y[:, 2] - Y[:, 1]), np.hypot(X[:, 0] - X[:, 2], Y[:, 0] - Y[:, 2])], axis=1).max(axis=1)
    nper = np.clip(np.ceil(e * density).astype(int), 1, 400)
    out = {k: np.zeros((size, size) + np.asarray(v).shape[2:], np.float32) for k, v in attrs.items()}
    cover = np.zeros((size, size), bool)
    for n in np.unique(nper):
        idx = np.nonzero(nper == n)[0]
        ii, jj = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij')
        m = (ii + jj) <= n
        b1 = ii[m] / n
        b2 = jj[m] / n
        B = np.stack([1 - b1 - b2, b1, b2], axis=1)
        px = np.floor(X[idx] @ B.T).astype(int)
        py = np.floor(Y[idx] @ B.T).astype(int)
        ok = (px >= 0) & (px < size) & (py >= 0) & (py < size)
        for k, v in attrs.items():
            v = np.asarray(v, np.float64)[idx]
            val = np.einsum('kj,tj...->tk...', B, v)
            out[k][py[ok], px[ok]] = val[ok]
        cover[py[ok], px[ok]] = True
    # dilate (gutter padding): copy attributes from covered neighbours into empty texels
    cov = cover.copy()
    for _ in range(pad):
        add = np.zeros_like(cov)
        new = {k: v.copy() for k, v in out.items()}
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                src = np.roll(np.roll(cov, dy, 0), dx, 1)
                take = src & ~cov & ~add
                for k in out:
                    sh = np.roll(np.roll(out[k], dy, 0), dx, 1)
                    new[k][take] = sh[take]
                add |= take
        out = new
        cov |= add
    out['cover'] = cover
    out['padded'] = cov
    return out
