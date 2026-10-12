"""Shared loading for the Ethics Assistant outfits: femsuit_04 (models/jericho/citizens/female_04.mdl) in the IN-GAME frame, its bind-pose bones, stock textures."""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdl_anim import cstr
from mdl_mesh import load_model_mesh
import preview as pv
import vtf
import vpk_tools as vt

PACK = r'C:\Users\poopy\Downloads\cg_scp_pm_combined_2830971578'
MODEL = os.path.join(PACK, 'models', 'jericho', 'citizens', 'female_04.mdl')
HL2_TEX = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\sourceengine\hl2_textures_dir.vpk'
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ethics', 'ref')

# BNA palette (https://www.color-hex.com palette "BNA Color Palette")
PINK = (252, 44, 157)       # #fc2c9d
MAGENTA = (198, 44, 128)    # #c62c80
INDIGO = (85, 78, 174)      # #554eae
ROYAL = (33, 56, 140)       # #21388c
NAVY = (15, 33, 94)         # #0f215e
PALETTE = dict(pink=PINK, magenta=MAGENTA, indigo=INDIGO, royal=ROYAL, navy=NAVY)


def rotz(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    M = np.eye(4)
    M[:2, :2] = [[c, -s], [s, c]]
    return M


G = rotz(90.0)           # bind frame (faces -Y) -> in-game frame (faces +X)
G3 = G[:3, :3]


def load_bones(raw=None):
    raw = raw or open(MODEL, 'rb').read()
    nb, bi = struct.unpack_from('<2i', raw, 156)
    names, parents, world = [], [], []
    for i in range(nb):
        o = bi + i * 216
        names.append(cstr(raw, o + struct.unpack_from('<i', raw, o)[0])[0])
        parents.append(struct.unpack_from('<i', raw, o + 4)[0])
        m = np.array(struct.unpack_from('<12f', raw, o + 96)).reshape(3, 4)
        T = np.vstack([m, [0, 0, 0, 1]])
        world.append(G @ np.linalg.inv(T))             # bone -> in-game world, bind pose
    return names, parents, world


class Rig:
    """Bind-pose bone frames in the in-game orientation + helpers to express a world-space part in a bone's local frame (what pac wants)."""

    def __init__(self, mdl_path=None):
        self.names, self.parents, self.world = load_bones(open(mdl_path or MODEL, 'rb').read())
        self.idx = {n: i for i, n in enumerate(self.names)}

    def bone(self, short):
        return self.idx['ValveBiped.Bip01_' + short] if 'ValveBiped.Bip01_' + short in self.idx else self.idx['ValveBiped.' + short]

    def local(self, short, pos_world, rot_world=None):
        """-> (Position (3,), Angles (p,y,r)) of a part sitting at pos_world with orientation rot_world (3x3, default world-aligned) relative to bone `short`."""
        W = self.world[self.bone(short)]
        R = W[:3, :3]
        p = R.T @ (np.asarray(pos_world, float) - W[:3, 3])
        Rl = R.T @ (np.eye(3) if rot_world is None else rot_world)
        return p, angles_from_matrix(Rl)


def angles_from_matrix(R):
    """Source Angle(pitch, yaw, roll) (degrees) of a rotation matrix (R = Rz(yaw) Ry(pitch) Rx(roll))."""
    sp = -R[2, 0]
    pitch = np.degrees(np.arcsin(np.clip(sp, -1, 1)))
    if abs(sp) < 0.99999:
        yaw = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
        roll = np.degrees(np.arctan2(R[2, 1], R[2, 2]))
    else:
        yaw = np.degrees(np.arctan2(-R[0, 1], R[1, 1]))
        roll = 0.0
    return np.array([pitch, yaw, roll])


def matrix_from_angles(p, y, r):
    p, y, r = np.radians([p, y, r])
    Rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
    Ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
    return Rz @ Ry @ Rx


class Body:
    def __init__(self):
        self.mesh = load_model_mesh(MODEL)
        self.rig = Rig()
        self.stock = {}
        tab, base = vt.entries(HL2_TEX)
        self._tab, self._base = tab, base
        for k, p in (('chau_facemap', 'materials/models/humans/female/group01/chau_facemap.vtf'), ('citizen_sheet', 'materials/models/humans/female/group01/citizen_sheet.vtf'),
                     ('eyeball_l', 'materials/models/humans/female/eyeball_l.vtf'), ('eyeball_r', 'materials/models/humans/female/eyeball_r.vtf'), ('fmouth', 'materials/models/humans/female/fmouth.vtf')):
            self.stock[k] = vtf.read(vt.read(HL2_TEX, tab, base, p))[0]
        for k in ('suit', 'skirt'):
            self.stock[k] = vtf.read(open(os.path.join(PACK, 'materials', 'models', 'jericho', 'citizens', k + '.vtf'), 'rb').read())[0]

    def triangles(self, skirt=True, skin=0):
        tr = self.mesh.triangles({'female_04': 0, 'torso': 0, 'skirt': 1 if skirt else 0, 'hands': 0}, skin=skin)
        tr = dict(tr)
        tr['pos'] = tr['pos'] @ G3.T
        tr['nrm'] = tr['nrm'] @ G3.T
        return tr

    def soup(self, skirt=True, textures=None, flat=None):
        """Triangle soup of the body. textures: material name -> RGB array (overrides the stock ones). Returns (soup, texlist)."""
        tr = self.triangles(skirt)
        names = self.mesh.textures
        tex = dict(self.stock)
        tex.update(textures or {})
        flat = dict({'eyeball_l': (235, 235, 235), 'eyeball_r': (235, 235, 235), 'handfemale': (222, 176, 150), 'fmouth': (150, 70, 70)}, **(flat or {}))
        texlist, texid = [], {}
        slot_tex = np.full(len(tr['slot']), -1, np.int64)
        col = np.tile(np.array((128, 128, 128), np.float64), (len(tr['slot']), 1))
        for slot in np.unique(tr['slot']):
            n = names[slot]
            sel = tr['slot'] == slot
            if n in tex and tex[n] is not None:
                if n not in texid:
                    texid[n] = len(texlist)
                    texlist.append(tex[n])
                slot_tex[sel] = texid[n]
            else:
                col[sel] = flat.get(n, (128, 128, 128))
        s = dict(pos=tr['pos'], nrm=tr['nrm'], uv=tr['uv'], tex=slot_tex, color=col, glow=np.zeros(len(slot_tex)))
        return s, texlist
