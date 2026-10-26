"""Head-donor tools: load another playermodel (extracted folder), map its head into the Ethics Assistant's bind frame the way pac's BoneMerge does, export a head OBJ with textures for previews.

BoneMerge skins the donor's vertices with the PLAYER's bone matrices:   v_world = M_player_head(t) * inv(B_donor_head) * v_donor        (B = bind-world matrix of the bone in its own model space)
For the player in the fitting configuration M_player_head = G * B_player_head (G = bind frame -> in-game frame, see ethics_common), so the donor head in the same frame as every accessory is
        v' = G * B_player_head * inv(B_donor_head) * v_donor
"""
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdl_anim import cstr
from mdl_mesh import load_model_mesh
import vtf as vtfmod

NUL = bytes([0])


def read_bones(raw):
    nb, bi = struct.unpack_from('<2i', raw, 156)
    names, parents, B = [], [], []
    for i in range(nb):
        o = bi + i * 216
        names.append(cstr(raw, o + struct.unpack_from('<i', raw, o)[0])[0])
        parents.append(struct.unpack_from('<i', raw, o + 4)[0])
        m = np.array(struct.unpack_from('<12f', raw, o + 96)).reshape(3, 4)     # poseToBone
        T = np.vstack([m, [0, 0, 0, 1]])
        B.append(np.linalg.inv(T))                                                # bone -> model space in the bind pose
    return names, parents, B


class Donor:
    def __init__(self, mdl_path, root=None):
        self.path = mdl_path
        self.root = root or os.path.dirname(mdl_path)
        self.raw = open(mdl_path, 'rb').read()
        self.names, self.parents, self.B = read_bones(self.raw)
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.mesh = load_model_mesh(mdl_path)
        ntex, texidx = struct.unpack_from('<2i', self.raw, 204)
        self.tex = [cstr(self.raw, texidx + i * 64 + struct.unpack_from('<i', self.raw, texidx + i * 64)[0])[0] for i in range(ntex)]
        ncd, cdidx = struct.unpack_from('<2i', self.raw, 212)
        self.cdmaterials = [cstr(self.raw, struct.unpack_from('<i', self.raw, cdidx + i * 4)[0])[0] for i in range(ncd)]

    def bone(self, name):
        for n in ('ValveBiped.Bip01_' + name, name):
            if n in self.idx:
                return self.idx[n]
        raise KeyError(name)

    def descendants(self, bone_idx):
        out = {bone_idx}
        changed = True
        while changed:
            changed = False
            for i, p in enumerate(self.parents):
                if p in out and i not in out:
                    out.add(i)
                    changed = True
        return out

    def triangles(self, choice=None, skin=0):
        return self.mesh.triangles(choice or {}, skin=skin, with_skin=True)

    # ------------------------------------------------------------------ materials
    def vmt(self, slot_name):
        for cd in self.cdmaterials:
            p = os.path.join(self.root_materials(), cd.replace('\\', '/').strip('/'), slot_name + '.vmt')
            if os.path.exists(p):
                return p
        # case-insensitive search
        for cd in self.cdmaterials:
            d = os.path.join(self.root_materials(), cd.replace('\\', '/').strip('/'))
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower() == slot_name.lower() + '.vmt':
                        return os.path.join(d, f)
        return None

    def root_materials(self):
        r = self.root
        while r and os.path.basename(r).lower() != 'models':
            r = os.path.dirname(r)
        return os.path.join(os.path.dirname(r), 'materials')

    def vmt_params(self, slot_name):
        p = self.vmt(slot_name)
        if not p:
            return None, {}
        txt = open(p, 'r', errors='replace').read()
        params = {}
        for m in re.finditer(r'"?\$?([A-Za-z_0-9]+)"?\s+"?([^"\r\n]*?)"?\s*(?:[\r\n]|$)', txt):
            params[m.group(1).lower()] = m.group(2).strip()
        shader = re.search(r'^\s*"?([A-Za-z_]+)"?\s*\{', txt, re.M)
        return (shader.group(1) if shader else '?'), params

    def basetexture(self, slot_name):
        shader, params = self.vmt_params(slot_name)
        bt = params.get('basetexture')
        if not bt:
            return None
        p = os.path.join(self.root_materials(), bt.replace('\\', '/') + '.vtf')
        if os.path.exists(p):
            return p
        d, f = os.path.split(p)
        if os.path.isdir(d):
            for ff in os.listdir(d):
                if ff.lower() == f.lower():
                    return os.path.join(d, ff)
        return None

    def texture_array(self, slot_name):
        p = self.basetexture(slot_name)
        if not p:
            return None
        return vtfmod.read(open(p, 'rb').read())[0]


def to_player_frame(donor_tris_pos, donor, d_head, player_B_head, G3, nrm=None):
    """map donor bind-pose points into the player's in-game fitting frame (see module docstring)"""
    M = G3 @ (player_B_head @ np.linalg.inv(donor.B[d_head]))[:3, :]
    A = M[:, :3]
    t = M[:, 3]
    P = np.asarray(donor_tris_pos, float)
    out = P @ A.T + t
    if nrm is not None:
        return out, np.asarray(nrm, float) @ A.T
    return out


# ------------------------------------------------------------------------------------------------------------------------------ full skinning into the player's frame
class Merger:
    """donor -> player-frame transform per bone (BoneMerge by name; unmatched bones follow their nearest matched ancestor)"""

    def __init__(self, donor, player_names, player_B, G3):
        self.d = donor
        self.M = np.zeros((len(donor.names), 3, 4))
        pidx = {n: i for i, n in enumerate(player_names)}
        for i, n in enumerate(donor.names):
            j = i
            while j >= 0 and donor.names[j] not in pidx:
                j = donor.parents[j]
            if j < 0:
                self.M[i] = np.hstack([np.eye(3), np.zeros((3, 1))])[:3]
                continue
            full = player_B[pidx[donor.names[j]]] @ np.linalg.inv(donor.B[j])
            self.M[i] = (G3 @ full[:3, :])

    def skin(self, pos, nrm, w, b):
        """pos/nrm (N,3,3) per triangle vertex, w,b (N,3,3): returns transformed pos, nrm"""
        N = pos.shape[0]
        P = pos.reshape(-1, 3)
        Nn = nrm.reshape(-1, 3)
        W = w.reshape(-1, 3)
        B = b.reshape(-1, 3).astype(int)
        outP = np.zeros_like(P)
        outN = np.zeros_like(Nn)
        tot = W.sum(1)
        tot = np.where(tot > 1e-6, tot, 1.0)
        for k in range(3):
            Mk = self.M[B[:, k]]                      # (V,3,4)
            wk = (W[:, k] / tot)[:, None]
            outP += wk * (np.einsum('vij,vj->vi', Mk[:, :, :3], P) + Mk[:, :, 3])
            outN += wk * np.einsum('vij,vj->vi', Mk[:, :, :3], Nn)
        outN /= np.maximum(np.linalg.norm(outN, axis=1, keepdims=True), 1e-9)
        return outP.reshape(N, 3, 3), outN.reshape(N, 3, 3)
