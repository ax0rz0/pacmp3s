"""Fast software preview of a playermodel plus accessory meshes (point splatting with a depth sort, supersampled).

Scene triangles are given in the IN-GAME frame (+X forward, +Y left, +Z up). Everything is a "triangle soup" dict:
    pos (T,3,3)  nrm (T,3,3) or None (flat normals)  uv (T,3,2) or None  tex (T,) int index into `textures` (-1 = flat colour)  color (T,3) 0..255  glow (T,) 0..1 (self-lit)
The body uses VVD texture coordinates (v is image-down); accessory OBJ uv uses the OBJ convention (v up) and is converted here with flip_v.
"""
import numpy as np

VIEWS = {'front': ((1.0, 0.0, 0.0), (0, 0, 1.0)), 'back': ((-1.0, 0, 0), (0, 0, 1.0)), 'left': ((0, 1.0, 0), (0, 0, 1.0)), 'right': ((0, -1.0, 0), (0, 0, 1.0)),
         '34': ((0.82, 0.57, 0.12), (0, 0, 1.0)), '34b': ((-0.75, -0.6, 0.15), (0, 0, 1.0)), '34r': ((0.82, -0.57, 0.12), (0, 0, 1.0))}


def soup(pos, nrm=None, uv=None, tex=-1, color=(150, 150, 150), glow=0.0, flip_v=False):
    pos = np.asarray(pos, np.float64)
    T = len(pos)
    if nrm is None:
        e1 = pos[:, 1] - pos[:, 0]
        e2 = pos[:, 2] - pos[:, 0]
        n = np.cross(e1, e2)
        n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        nrm = np.repeat(n[:, None, :], 3, axis=1)
    if uv is None:
        uv = np.zeros((T, 3, 2))
    else:
        uv = np.asarray(uv, np.float64).copy()
        if flip_v:
            uv[..., 1] = 1.0 - uv[..., 1]
    return dict(pos=pos, nrm=np.asarray(nrm, np.float64), uv=uv, tex=np.full(T, tex, np.int64) if np.isscalar(tex) else np.asarray(tex, np.int64),
                color=np.tile(np.asarray(color, np.float64), (T, 1)) if np.asarray(color).ndim == 1 else np.asarray(color, np.float64),
                glow=np.full(T, glow) if np.isscalar(glow) else np.asarray(glow, np.float64))


def concat(soups):
    return {k: np.concatenate([s[k] for s in soups]) for k in soups[0]}


def mesh_to_soup(V, F, N=None, UV=None, **kw):
    """indexed mesh -> triangle soup. UV (n,2) per vertex in OBJ convention."""
    V = np.asarray(V, float)
    F = np.asarray(F, int)
    pos = V[F]
    nrm = None if N is None else np.asarray(N, float)[F]
    uv = None if UV is None else np.asarray(UV, float)[F]
    return soup(pos, nrm, uv, flip_v=UV is not None, **kw)


def _bilinear(tex, uv):
    h, w = tex.shape[:2]
    u = (uv[:, 0] % 1.0) * w - 0.5
    v = (uv[:, 1] % 1.0) * h - 0.5
    x0 = np.floor(u).astype(int)
    y0 = np.floor(v).astype(int)
    fx = (u - x0)[:, None]
    fy = (v - y0)[:, None]
    x0m, x1m = x0 % w, (x0 + 1) % w
    y0m, y1m = y0 % h, (y0 + 1) % h
    t = tex[:, :, :3].astype(np.float32)
    return t[y0m, x0m] * (1 - fx) * (1 - fy) + t[y0m, x1m] * fx * (1 - fy) + t[y1m, x0m] * (1 - fx) * fy + t[y1m, x1m] * fx * fy


def view_basis(view):
    d, up = VIEWS[view] if isinstance(view, str) else view
    d = np.asarray(d, float) / np.linalg.norm(d)
    right = np.cross(up, d)
    right /= np.linalg.norm(right)
    up2 = np.cross(d, right)
    return d, right, up2


def fit_bounds(pos, view, pad=0.04):
    d, right, up2 = view_basis(view)
    p = pos.reshape(-1, 3)
    sx, sy = p @ right, p @ up2
    return (sx.min(), sx.max(), sy.min(), sy.max())


def render(scene, textures, view='front', height=900, ss=2, bounds=None, bg=(38, 42, 54), aspect=0.62, light=(0.45, 0.35, 0.85)):
    """Returns an RGB uint8 image (height x width). textures: list of RGB(A) arrays indexed by scene['tex']."""
    d, right, up2 = view_basis(view)
    pos = scene['pos']
    sx = pos @ right
    sy = pos @ up2
    z = pos @ d
    if bounds is None:
        bounds = (sx.min(), sx.max(), sy.min(), sy.max())
    x0, x1, y0, y1 = bounds
    H = height * ss
    W = int(height * aspect) * ss
    scale = H * 0.95 / (y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    X = (sx - cx) * scale + W / 2
    Y = H / 2 - (sy - cy) * scale
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    # edge lengths -> samples per edge
    e = np.stack([np.hypot(X[:, 1] - X[:, 0], Y[:, 1] - Y[:, 0]), np.hypot(X[:, 2] - X[:, 1], Y[:, 2] - Y[:, 1]), np.hypot(X[:, 0] - X[:, 2], Y[:, 0] - Y[:, 2])], axis=1).max(axis=1)
    nper = np.clip(np.ceil(e * 1.9).astype(int), 1, 90)
    xs_all, ys_all, zs_all, col_all = [], [], [], []
    chunks = []                                                      # (samples per edge, triangle indices) with a bounded number of samples per chunk
    for n in np.unique(nper):
        idx_all = np.nonzero(nper == n)[0]
        step = max(1, int(1_500_000 // ((n + 1) * (n + 2) // 2)))
        for s0 in range(0, len(idx_all), step):
            chunks.append((n, idx_all[s0:s0 + step]))
    for n, idx in chunks:
        ii, jj = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing='ij')
        m = (ii + jj) <= n
        b1 = (ii[m] / n).astype(np.float64)
        b2 = (jj[m] / n).astype(np.float64)
        B = np.stack([1 - b1 - b2, b1, b2], axis=1)                  # (K,3)
        # sample positions
        px = X[idx] @ B.T
        py = Y[idx] @ B.T
        pz = z[idx] @ B.T
        nrm = np.einsum('kj,tjc->tkc', B, scene['nrm'][idx])
        nl = np.linalg.norm(nrm, axis=2, keepdims=True)
        nrm = nrm / np.maximum(nl, 1e-9)
        # two-sided: flip normals that face away from the camera
        facing = (nrm @ d)
        nrm = np.where(facing[..., None] < 0, -nrm, nrm)
        lam = np.clip(nrm @ L, -1, 1) * 0.5 + 0.5
        shade = 0.34 + 0.80 * lam ** 1.35
        rim = np.clip(1 - np.abs(nrm @ d), 0, 1) ** 3 * 0.10
        uvs = np.einsum('kj,tjc->tkc', B, scene['uv'][idx])
        K = len(B)
        col = np.repeat(scene['color'][idx][:, None, :], K, axis=1).astype(np.float32)
        texid = scene['tex'][idx]
        for t in np.unique(texid):
            if t < 0:
                continue
            sel = np.nonzero(texid == t)[0]
            col[sel] = _bilinear(textures[t], uvs[sel].reshape(-1, 2)).reshape(len(sel), K, 3)
        glow = scene['glow'][idx][:, None]
        lit = col * shade[..., None] + rim[..., None] * 255.0
        col = lit * (1 - glow[..., None]) + col * glow[..., None] * 1.0
        # keep only what is needed, in compact types (a full-body render has ~25 million samples)
        xi_c = np.floor(px.ravel()).astype(np.int32)
        yi_c = np.floor(py.ravel()).astype(np.int32)
        ok_c = (xi_c >= 0) & (xi_c < W) & (yi_c >= 0) & (yi_c < H)
        xs_all.append(xi_c[ok_c].astype(np.int16)); ys_all.append(yi_c[ok_c].astype(np.int16)); zs_all.append(pz.ravel()[ok_c].astype(np.float32))
        col_all.append(np.clip(col.reshape(-1, 3)[ok_c] + 0.5, 0, 255).astype(np.uint8))
        del px, py, pz, nrm, uvs, col, lit
    xi = np.concatenate(xs_all).astype(np.int64); yi = np.concatenate(ys_all).astype(np.int64); zs = np.concatenate(zs_all); cols = np.concatenate(col_all)
    del xs_all, ys_all, zs_all, col_all
    order = np.argsort(zs, kind='stable')                            # far -> near, last write wins
    img = np.zeros((H, W, 3), np.float32)
    img[:] = np.asarray(bg, np.float32)
    cover = np.zeros((H, W), bool)
    img[yi[order], xi[order]] = cols[order]
    cover[yi[order], xi[order]] = True
    # fill pin-holes: a pixel with no sample takes the mean of covered neighbours
    holes = ~cover
    if holes.any():
        acc = np.zeros_like(img)
        cnt = np.zeros((H, W), np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                sh = np.roll(np.roll(cover, dy, 0), dx, 1)
                shc = np.roll(np.roll(img, dy, 0), dx, 1)
                acc += shc * sh[..., None]
                cnt += sh
        fill = holes & (cnt >= 5)
        img[fill] = acc[fill] / cnt[fill][:, None]
    img = img.reshape(height, ss, W // ss, ss, 3).mean(axis=(1, 3))
    return np.clip(img, 0, 255).astype(np.uint8)
