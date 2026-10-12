"""Source model mesh reader (MDL v44-48 + VVD v4 + VTX v7) and a small textured software renderer, for previewing playermodel re-textures without the game.

    from mdl_mesh import load_model_mesh, render
    m = load_model_mesh(r'C:/.../models/jericho/citizens/female_04.mdl')   # looks for female_04.vvd and female_04.dx90.vtx next to the mdl
    tris = m.triangles({'female_04': 0, 'torso': 0, 'skirt': 1, 'hands': 0}, skin=0)   # bodygroup name -> submodel index
    img = render(tris, textures={slot: RGBA_array}, view='front')

Frame: Source model space, +X forward, +Y left, +Z up. Textures are looked up by the material SLOT (texture index in the .mdl texture table, after the skin family remap).
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdl_anim import cstr


class ModelMesh:
    def __init__(self, mdl_path=None, mdl=None, vvd=None, vtx=None):
        if mdl is None:
            base = os.path.splitext(mdl_path)[0]
            mdl = open(mdl_path, 'rb').read()
            vvd = open(base + '.vvd', 'rb').read()
            vtx_path = base + '.dx90.vtx' if os.path.exists(base + '.dx90.vtx') else base + '.dx80.vtx'
            vtx = open(vtx_path, 'rb').read()
        self.mdl, self.vvd, self.vtx = mdl, vvd, vtx
        self._parse_mdl()
        self._parse_vvd()
        self._parse_vtx()

    # ------------------------------------------------------------------ MDL
    def _parse_mdl(self):
        raw = self.mdl
        self.version = struct.unpack_from('<i', raw, 4)[0]
        ntex, texidx = struct.unpack_from('<2i', raw, 204)
        self.textures = [cstr(raw, texidx + i * 64 + struct.unpack_from('<i', raw, texidx + i * 64)[0])[0] for i in range(ntex)]
        nskinref, nskinfam, skinidx = struct.unpack_from('<3i', raw, 220)
        self.skins = [struct.unpack_from('<%dh' % nskinref, raw, skinidx + f * nskinref * 2) for f in range(nskinfam)]
        nbody, bodyidx = struct.unpack_from('<2i', raw, 232)
        self.bodyparts = []
        for i in range(nbody):
            o = bodyidx + i * 16
            ni, nm, base, mi = struct.unpack_from('<4i', raw, o)
            name = cstr(raw, o + ni)[0]
            models = []
            for j in range(nm):
                mo = o + mi + j * 148
                mname = raw[mo:mo + 64].split(b'\0')[0].decode('latin1')
                nmesh, meshidx, nverts, vertidx = struct.unpack_from('<4i', raw, mo + 72)
                meshes = []
                for k in range(nmesh):
                    so = mo + meshidx + k * 116
                    material, modelindex, mnumverts, vertoffset = struct.unpack_from('<4i', raw, so)
                    meshes.append(dict(material=material, numverts=mnumverts, vertoffset=vertoffset))
                models.append(dict(name=mname, vertindex=vertidx // 48, meshes=meshes))
            self.bodyparts.append(dict(name=name, base=base, models=models))

    # ------------------------------------------------------------------ VVD
    def _parse_vvd(self):
        raw = self.vvd
        assert raw[:4] == b'IDSV', 'not a VVD'
        nlods = struct.unpack_from('<i', raw, 12)[0]
        lodverts = struct.unpack_from('<8i', raw, 16)
        nfix, fixstart, vstart, tstart = struct.unpack_from('<4i', raw, 48)
        n_total = lodverts[0]
        nv_all = ((tstart if tstart > vstart else len(raw)) - vstart) // 48
        a = np.frombuffer(raw, np.dtype([('w', '<f4', 3), ('b', 'u1', 3), ('nb', 'u1'), ('pos', '<f4', 3), ('nrm', '<f4', 3), ('uv', '<f4', 2)]), count=nv_all, offset=vstart)
        if nfix:
            parts = []
            for i in range(nfix):
                lod, src, cnt = struct.unpack_from('<3i', raw, fixstart + i * 12)
                if lod >= 0:
                    parts.append(a[src:src + cnt])
            a = np.concatenate(parts)
        self.vpos = a['pos'].astype(np.float64)
        self.vnrm = a['nrm'].astype(np.float64)
        self.vuv = a['uv'].astype(np.float64)
        self.vbones = a['b']
        self.vweights = a['w']

    # ------------------------------------------------------------------ VTX
    def _parse_vtx(self):
        raw = self.vtx
        ver, cache, mbs, mbt, mbv, chk, nlods, matrep, nbody, bodyoff = struct.unpack_from('<iiHHiiiiii', raw, 0)
        assert ver == 7, 'VTX version %d' % ver
        self.lod0 = []        # per bodypart -> per model -> per mesh -> {'tris': (N, 3) global vertex indices}
        for bi in range(nbody):
            bo = bodyoff + bi * 8
            nmodels, modeloff = struct.unpack_from('<2i', raw, bo)
            models = []
            for mi in range(nmodels):
                mo = bo + modeloff + mi * 8
                nl, lodoff = struct.unpack_from('<2i', raw, mo)
                lo = mo + lodoff                                # LOD 0
                nmeshes, meshoff, switch = struct.unpack_from('<iif', raw, lo)
                meshes = []
                for ki in range(nmeshes):
                    ko = lo + meshoff + ki * 9
                    nsg, sgoff, flags = struct.unpack_from('<iiB', raw, ko)
                    tris = []
                    for si in range(nsg):
                        so = ko + sgoff + si * 25
                        nverts, voff, nidx, ioff, nstrips, stripoff, sflags = struct.unpack_from('<6iB', raw, so)
                        verts = np.frombuffer(raw, np.dtype([('bwi', 'u1', 3), ('nb', 'u1'), ('orig', '<u2'), ('bid', 'i1', 3)]), count=nverts, offset=so + voff)
                        orig = verts['orig'].astype(np.int64)
                        idx = np.frombuffer(raw, '<u2', count=nidx, offset=so + ioff).astype(np.int64)
                        for ti in range(nstrips):
                            to = so + stripoff + ti * 27
                            sn_idx, s_ioff, sn_v, s_voff, s_nb, s_flags, s_nbsc, s_bsco = struct.unpack_from('<4ihBii', raw, to)
                            seg = idx[s_ioff:s_ioff + sn_idx]
                            if s_flags & 1:                      # triangle list
                                tris.append(orig[seg].reshape(-1, 3))
                            elif s_flags & 2:                    # triangle strip
                                t = seg
                                for k in range(len(t) - 2):
                                    tri = (t[k], t[k + 1], t[k + 2]) if k % 2 == 0 else (t[k + 1], t[k], t[k + 2])
                                    tris.append(orig[list(tri)][None, :])
                    meshes.append(np.concatenate(tris) if tris else np.zeros((0, 3), np.int64))
                models.append(meshes)
            self.lod0.append(models)

    # ------------------------------------------------------------------ queries
    def bodygroup_names(self):
        return [(bp['name'], [m['name'] for m in bp['models']]) for bp in self.bodyparts]

    def triangles(self, choice=None, skin=0, exclude_materials=(), with_skin=False):
        """choice: bodygroup name -> submodel index (default 0). Returns dict(pos (N,3,3), nrm (N,3,3), uv (N,3,2), slot (N,)); with_skin adds w (N,3,3) bone weights and b (N,3,3) bone indices."""
        choice = choice or {}
        P, Nn, UV, S, Wt, Bn = [], [], [], [], [], []
        for bi, bp in enumerate(self.bodyparts):
            mi = choice.get(bp['name'], 0)
            if mi is None or mi >= len(bp['models']):
                continue
            model = bp['models'][mi]
            if model['name'] in ('', 'blank') or not model['meshes']:
                continue
            for ki, mesh in enumerate(model['meshes']):
                tris = self.lod0[bi][mi][ki]
                if len(tris) == 0:
                    continue
                g = tris + model['vertindex'] + mesh['vertoffset']
                slot = self.skins[skin][mesh['material']]
                if self.textures[slot] in exclude_materials:
                    continue
                P.append(self.vpos[g])
                Nn.append(self.vnrm[g])
                UV.append(self.vuv[g])
                S.append(np.full(len(g), slot, np.int64))
                if with_skin:
                    Wt.append(self.vweights[g])
                    Bn.append(self.vbones[g])
        out = dict(pos=np.concatenate(P), nrm=np.concatenate(Nn), uv=np.concatenate(UV), slot=np.concatenate(S))
        if with_skin:
            out['w'] = np.concatenate(Wt)
            out['b'] = np.concatenate(Bn)
        return out

    def mesh_triangles(self, bodypart, model_index=0, mesh_index=None, skin=0):
        """Triangles of one bodygroup submodel (all its meshes, or one mesh): dict(pos, nrm, uv, slot)."""
        bi = [b['name'] for b in self.bodyparts].index(bodypart)
        model = self.bodyparts[bi]['models'][model_index]
        P, Nn, UV, S = [], [], [], []
        for ki, mesh in enumerate(model['meshes']):
            if mesh_index is not None and ki != mesh_index:
                continue
            tris = self.lod0[bi][model_index][ki]
            if len(tris) == 0:
                continue
            g = tris + model['vertindex'] + mesh['vertoffset']
            P.append(self.vpos[g]); Nn.append(self.vnrm[g]); UV.append(self.vuv[g])
            S.append(np.full(len(g), self.skins[skin][mesh['material']], np.int64))
        return dict(pos=np.concatenate(P), nrm=np.concatenate(Nn), uv=np.concatenate(UV), slot=np.concatenate(S))


def load_model_mesh(path):
    return ModelMesh(path)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------
# renderer: orthographic / simple perspective, z-buffer, bilinear texture sampling, half-lambert + a fill light
# ---------------------------------------------------------------------------------------------------------------------------------------------------------
VIEWS = {'front': (np.array([1.0, 0, 0]), np.array([0, 0, 1.0])), 'back': (np.array([-1.0, 0, 0]), np.array([0, 0, 1.0])), 'left': (np.array([0, 1.0, 0]), np.array([0, 0, 1.0])),
         'right': (np.array([0, -1.0, 0]), np.array([0, 0, 1.0])), '34': (np.array([0.8, 0.6, 0.15]), np.array([0, 0, 1.0])), '34b': (np.array([-0.8, -0.6, 0.15]), np.array([0, 0, 1.0]))}


def _sample(tex, uv):
    h, w = tex.shape[:2]
    u = (uv[..., 0] % 1.0) * (w - 1)
    v = (uv[..., 1] % 1.0) * (h - 1)          # VVD / VTF share the top-left origin after Source's v flip: v is already image-down
    x0 = np.clip(u.astype(int), 0, w - 2)
    y0 = np.clip(v.astype(int), 0, h - 2)
    fx = (u - x0)[..., None]
    fy = (v - y0)[..., None]
    t = tex.astype(np.float32)
    return (t[y0, x0] * (1 - fx) * (1 - fy) + t[y0, x0 + 1] * fx * (1 - fy) + t[y0 + 1, x0] * (1 - fx) * fy + t[y0 + 1, x0 + 1] * fx * fy)


def render(tris, textures, view='front', size=720, bounds=None, flat_colors=None, bg=(46, 50, 60), extra=None):
    """tris from ModelMesh.triangles(); textures: slot -> RGBA/RGB uint8 array (slots without one use flat_colors[slot] or grey). Returns an RGB uint8 image.
    extra: optional list of (V (n,3), F (m,3), color (3,)) meshes in model space drawn with the same z-buffer (accessories)."""
    d, up = VIEWS[view]
    d = d / np.linalg.norm(d)
    right = np.cross(up, d)       # camera looks along -d (camera sits at +d): screen right
    right = right / np.linalg.norm(right)
    up2 = np.cross(d, right)
    pos = tris['pos']
    allp = pos.reshape(-1, 3)
    sx = pos @ right
    sy = pos @ up2
    if bounds is None:
        bounds = (float(sx.min()), float(sx.max()), float(sy.min()), float(sy.max()))
    x0, x1, y0, y1 = bounds
    H = size
    scale = H * 0.94 / (y1 - y0)
    W = int(size * 0.62)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    img = np.zeros((H, W, 3), np.float32)
    img[:] = np.array(bg, np.float32)
    zbuf = np.full((H, W), -1e9, np.float32)
    X = (sx - cx) * scale + W / 2
    Y = H / 2 - (sy - cy) * scale
    Z = pos @ d
    light = np.array([0.35, 0.25, 0.9])
    light = light / np.linalg.norm(light)

    def draw(px, py, pz, uv, nrm, tex, color):
        minx = int(max(np.floor(px.min()), 0)); maxx = int(min(np.ceil(px.max()), W - 1))
        miny = int(max(np.floor(py.min()), 0)); maxy = int(min(np.ceil(py.max()), H - 1))
        if minx > maxx or miny > maxy:
            return
        xs = np.arange(minx, maxx + 1) + 0.5
        ys = np.arange(miny, maxy + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        den = (py[1] - py[2]) * (px[0] - px[2]) + (px[2] - px[1]) * (py[0] - py[2])
        if abs(den) < 1e-9:
            return
        w0 = ((py[1] - py[2]) * (gx - px[2]) + (px[2] - px[1]) * (gy - py[2])) / den
        w1 = ((py[2] - py[0]) * (gx - px[2]) + (px[0] - px[2]) * (gy - py[2])) / den
        w2 = 1 - w0 - w1
        ins = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not ins.any():
            return
        z = w0 * pz[0] + w1 * pz[1] + w2 * pz[2]
        yy, xx = np.nonzero(ins)
        ok = z[ins] > zbuf[miny + yy, minx + xx]
        yy, xx = yy[ok], xx[ok]
        if len(yy) == 0:
            return
        a0, a1, a2 = w0[yy, xx], w1[yy, xx], w2[yy, xx]
        n = a0[:, None] * nrm[0] + a1[:, None] * nrm[1] + a2[:, None] * nrm[2]
        n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        lam = np.clip(n @ light, -1, 1) * 0.5 + 0.5                  # half-lambert
        shade = 0.38 + 0.78 * lam ** 1.4
        if tex is not None:
            uvp = a0[:, None] * uv[0] + a1[:, None] * uv[1] + a2[:, None] * uv[2]
            col = _sample(tex[:, :, :3], uvp)
        else:
            col = np.tile(np.array(color, np.float32), (len(yy), 1))
        img[miny + yy, minx + xx] = np.clip(col * shade[:, None], 0, 255)
        zbuf[miny + yy, minx + xx] = z[ins][ok]

    order = np.argsort(Z.mean(axis=1))
    for t in order:
        slot = int(tris['slot'][t])
        tex = textures.get(slot)
        color = (flat_colors or {}).get(slot, (128, 128, 128))
        draw(X[t], Y[t], Z[t], tris['uv'][t], tris['nrm'][t], tex, color)
    if extra:
        for V, F, col in extra:
            ex = (V @ right - cx) * scale + W / 2
            ey = H / 2 - (V @ up2 - cy) * scale
            ez = V @ d
            Vn = np.zeros_like(V)
            for f in F:
                nn = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
                nn = nn / max(np.linalg.norm(nn), 1e-9)
                draw(ex[f], ey[f], ez[f], None, np.tile(nn, (3, 1)), None, col)
    return np.clip(img, 0, 255).astype(np.uint8)
