"""Preview scene for the D-class outfit: models/player/cheddar/class_d/class_d_mike.mdl in the low-sec uniform + the HL2 Female_04 head swap (bonemerged to the head)."""
import os

import numpy as np

import preview as pv
import vpk_tools as vt
import vtf
from ethics_common import G3, HL2_TEX, PACK, Rig, load_bones
from mdl_mesh import ModelMesh

MIKE = os.path.join(PACK, 'models', 'player', 'cheddar', 'class_d', 'class_d_mike.mdl')
HL2_MISC = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\sourceengine\hl2_misc_dir.vpk'
HEAD_MATS = ('mouth', 'eyeball_l', 'mike_facemap', 'eyeball_r', 'hair_diff_000_a_uni', 'hair_diff_001_a_uni')


def pack_tex(rel):
    return vtf.read(open(os.path.join(PACK, 'materials', 'models', 'class_d', *rel.split('/')) + '.vtf', 'rb').read())[0]


class DClass:
    def __init__(self):
        self.mesh = ModelMesh(MIKE)
        self.rig = Rig(MIKE)
        tab, base = vt.entries(HL2_MISC)
        self.fmdl = ModelMesh(mdl=vt.read(HL2_MISC, tab, base, 'models/humans/group01/female_04.mdl'), vvd=vt.read(HL2_MISC, tab, base, 'models/humans/group01/female_04.vvd'),
                              vtx=vt.read(HL2_MISC, tab, base, 'models/humans/group01/female_04.dx90.vtx'))
        self.frig = Rig.__new__(Rig)
        self.frig.names, self.frig.parents, self.frig.world = load_bones(self.fmdl.mdl)
        self.frig.idx = {n: i for i, n in enumerate(self.frig.names)}
        ttab, tbase = vt.entries(HL2_TEX)
        self.tex = {'class_d_uniform': pack_tex('body/class_d_uniform_lowsec'), 'inner_class_d_shirt': pack_tex('body/inner_class_d_shirt'), 'class_d_hands': pack_tex('misc/class_d_hands'),
                    'belt_class_d': pack_tex('misc/belt_class_d')}
        self.head_tex = {'chau_facemap': vtf.read(vt.read(HL2_TEX, ttab, tbase, 'materials/models/humans/female/group01/chau_facemap.vtf'))[0],
                         'fmouth': vtf.read(vt.read(HL2_TEX, ttab, tbase, 'materials/models/humans/female/fmouth.vtf'))[0]}

    def body_triangles(self, belts=0, hats=2):
        tr = dict(self.mesh.triangles({'belts': belts, 'hats': hats}, skin=0, exclude_materials=HEAD_MATS))
        tr['pos'] = tr['pos'] @ G3.T
        tr['nrm'] = tr['nrm'] @ G3.T
        return tr

    def head_triangles(self, world=None):
        """Female_04 head (face, eyes, mouth, pupils) moved onto the mike skeleton like bonemerge: v' = sum_i w_i W_mike[b_i] W_f[b_i]^-1 v
        (world: the target skeleton's bone matrices, default the bind pose; pass a deformed skeleton's matrices to bonemerge onto a scaled rig)"""
        f = self.fmdl
        world = self.rig.world if world is None else world
        P, N, UV, S, W3, B3 = [], [], [], [], [], []
        for bi, bp in enumerate(f.bodyparts):
            model = bp['models'][0]
            for ki, mesh in enumerate(model['meshes']):
                tris = f.lod0[bi][0][ki]
                if len(tris) == 0:
                    continue
                g = tris + model['vertindex'] + mesh['vertoffset']
                slot = f.skins[0][mesh['material']]
                if f.textures[slot] in ('citizen_sheet', 'glint'):
                    continue
                P.append(f.vpos[g])
                N.append(f.vnrm[g])
                UV.append(f.vuv[g])
                S.append(np.full(len(g), slot))
                W3.append(f.vweights[g])
                B3.append(f.vbones[g])
        P, N, UV, S, W3, B3 = (np.concatenate(a) for a in (P, N, UV, S, W3, B3))
        Pg, Ng = P @ G3.T, N @ G3.T
        out = np.zeros_like(Pg)
        outn = np.zeros_like(Ng)
        for k in range(3):
            w, b = W3[..., k], B3[..., k]
            for bi, name in enumerate(self.frig.names):
                if name not in self.rig.idx:
                    continue
                sel = (b == bi) & (w > 0)
                if not sel.any():
                    continue
                M = world[self.rig.idx[name]] @ np.linalg.inv(self.frig.world[bi])
                out[sel] += w[sel][..., None] * (Pg[sel] @ M[:3, :3].T + M[:3, 3])
                outn[sel] += w[sel][..., None] * (Ng[sel] @ M[:3, :3].T)
        tot = W3.sum(axis=-1)
        out = out / np.maximum(tot, 1e-6)[..., None]
        return dict(pos=out, nrm=outn, uv=UV, slot=S)

    def _soup_from(self, tr, names, textures, ids, texlist, special=None):
        tid = np.full(len(tr['slot']), -1, np.int64)
        col = np.tile(np.array((120, 120, 120), float), (len(tr['slot']), 1))
        for slot in np.unique(tr['slot']):
            n = names[slot]
            sel = tr['slot'] == slot
            if n in textures:
                if n not in ids:
                    ids[n] = len(texlist)
                    texlist.append(textures[n])
                tid[sel] = ids[n]
            elif special and n in special:
                col[sel] = special[n]
        return dict(pos=tr['pos'], nrm=tr['nrm'], uv=tr['uv'], tex=tid, color=col, glow=np.zeros(len(tid)))

    def soup(self, belts=0, hats=2):
        texlist, ids = [], {}
        a = self._soup_from(self.body_triangles(belts, hats), self.mesh.textures, self.tex, ids, texlist)
        b = self._soup_from(self.head_triangles(), self.fmdl.textures, self.head_tex, ids, texlist,
                            special={'eyeball_l': (235, 235, 235), 'eyeball_r': (235, 235, 235), 'pupil_l': (40, 28, 26), 'pupil_r': (40, 28, 26)})
        return pv.concat([a, b]), texlist
