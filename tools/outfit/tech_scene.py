"""Preview scene for the tech expert outfit: sanctum/site_staff/technical_expert/technical_expert.mdl + the HL2 Female_04 head swap (bonemerged to the head), in the in-game frame."""
import os
import re

import numpy as np

import preview as pv
import vpk_tools as vt
import vtf
from dclass_scene import DClass, HL2_MISC
from ethics_common import G3, HL2_TEX, PACK, Rig, load_bones
from mdl_mesh import ModelMesh

TECH = os.path.join(PACK, 'models', 'sanctum', 'site_staff', 'technical_expert', 'technical_expert.mdl')
MAT_DIRS = [os.path.join(PACK, 'materials', 'sanctum', 'site_staff', 'technical_expert'), os.path.join(PACK, 'materials', 'sanctum', 'site_staff', 'shared')]
HEAD_MATS = ('mouth', 'eyeball_l', 'mike_facemap', 'eyeball_r')       # the male head the user hides / swaps for the Female_04 head
# the user's tech expert bodygroups (ModelModifiers 'Stripes=0;Gas Mask=1;Kneepads=1;'), everything else at its default (0)
USER_BODYGROUPS = {'Stripes': 0, 'Gas Mask': 1, 'Kneepads': 1}


def find_file(rel_base, exts):
    for d in MAT_DIRS:
        for ext in exts:
            p = os.path.join(d, rel_base + ext)
            if os.path.exists(p):
                return p
    return None


def read_vmt(name):
    p = find_file(name, ('.vmt', '.VMT'))
    if p is None:
        return {}
    text = open(p, encoding='utf-8', errors='replace').read()
    text = re.sub(r'//[^\n]*', '', text)
    out = {}
    for m in re.finditer(r'"?\$(\w+)"?\s+"([^"]*)"', text):
        out[m.group(1).lower()] = m.group(2)
    return out


def load_vtf_path(path_in_vmt):
    """a $basetexture path from a vmt ('sanctum\\site_staff\\technical_expert\\x_rgb') -> RGBA uint8 array, or None"""
    rel = path_in_vmt.replace('\\', '/')
    p = os.path.join(PACK, 'materials', *rel.split('/')) + '.vtf'
    if not os.path.exists(p):
        p2 = find_file(os.path.basename(rel), ('.vtf',))
        p = p2
    if p is None or not os.path.exists(p):
        return None
    return vtf.read(open(p, 'rb').read())[0]


def tint_of(vmt):
    m = re.match(r'\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]', vmt.get('color2', ''))
    return np.array([float(x) for x in m.groups()]) if m else None


def original_texture(name):
    """the texture as the engine shows it (base colour with the $color2 tint applied by the base alpha)"""
    v = read_vmt(name)
    base = v.get('basetexture', '')
    t = tint_of(v)
    if base.lower().replace('/', '\\') in ('color\\white',):
        c = np.array([255, 255, 255, 255], np.uint8)
        img = np.tile(c, (16, 16, 1))
    else:
        img = load_vtf_path(base) if base else None
    if img is None:
        return None
    rgb = img[..., :3].astype(np.float32)
    if t is not None and v.get('blendtintbybasealpha', '0') == '1':
        a = img[..., 3:4].astype(np.float32) / 255.0
        rgb = rgb * (1 - a + a * t[None, None, :])
    elif t is not None:
        rgb = rgb * t[None, None, :]
    return np.clip(rgb, 0, 255).astype(np.uint8)


class TechExpert(DClass):
    def __init__(self):
        self.mesh = ModelMesh(TECH)
        self.rig = Rig(TECH)
        tab, base = vt.entries(HL2_MISC)
        self.fmdl = ModelMesh(mdl=vt.read(HL2_MISC, tab, base, 'models/humans/group01/female_04.mdl'), vvd=vt.read(HL2_MISC, tab, base, 'models/humans/group01/female_04.vvd'),
                              vtx=vt.read(HL2_MISC, tab, base, 'models/humans/group01/female_04.dx90.vtx'))
        self.frig = Rig.__new__(Rig)
        self.frig.names, self.frig.parents, self.frig.world = load_bones(self.fmdl.mdl)
        self.frig.idx = {n: i for i, n in enumerate(self.frig.names)}
        ttab, tbase = vt.entries(HL2_TEX)
        self.tex = {}
        for n in self.mesh.textures:
            if n in HEAD_MATS:
                continue
            t = original_texture(n)
            if t is not None:
                self.tex[n] = t
        self.head_tex = {'chau_facemap': vtf.read(vt.read(HL2_TEX, ttab, tbase, 'materials/models/humans/female/group01/chau_facemap.vtf'))[0],
                         'fmouth': vtf.read(vt.read(HL2_TEX, ttab, tbase, 'materials/models/humans/female/fmouth.vtf'))[0]}

    def body_triangles(self, choice=None, skin=0, exclude=HEAD_MATS):
        ch = dict(USER_BODYGROUPS)
        ch.update(choice or {})
        tr = dict(self.mesh.triangles(ch, skin=skin, exclude_materials=exclude))
        tr['pos'] = tr['pos'] @ G3.T
        tr['nrm'] = tr['nrm'] @ G3.T
        return tr

    def soup(self, choice=None, textures=None, slot_colors=None):
        texlist, ids = [], {}
        tr = self.body_triangles(choice)
        names = self.mesh.textures
        tex = dict(self.tex)
        tex.update(textures or {})
        tid = np.full(len(tr['slot']), -1, np.int64)
        col = np.tile(np.array((120, 120, 120), float), (len(tr['slot']), 1))
        for slot in np.unique(tr['slot']):
            n = names[slot]
            sel = tr['slot'] == slot
            if slot_colors is not None:
                col[sel] = slot_colors[slot]
            elif n in tex and tex[n] is not None:
                if n not in ids:
                    ids[n] = len(texlist)
                    texlist.append(tex[n])
                tid[sel] = ids[n]
        a = dict(pos=tr['pos'], nrm=tr['nrm'], uv=tr['uv'], tex=tid, color=col, glow=np.zeros(len(tid)))
        b = self._soup_from(self.head_triangles(), self.fmdl.textures, self.head_tex, ids, texlist,
                            special={'eyeball_l': (235, 235, 235), 'eyeball_r': (235, 235, 235), 'pupil_l': (40, 28, 26), 'pupil_r': (40, 28, 26)})
        return pv.concat([a, b]), texlist
