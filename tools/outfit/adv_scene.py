"""Scene helpers for the advanced PAC outfits: the Ethics Assistant body (femsuit_04, in-game frame, bind pose), its surfaces, landmarks and a lean preview renderer."""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshgen as mg
import preview as pv
import scene as sc
from ethics_acc import Acc, Surface
from ethics_common import Body

HEAD_CENTRE = np.array([0.4, 0.0, 65.0])


class Scene:
    def __init__(self):
        self.b = Body()
        self.rig = self.b.rig
        tr = self.b.triangles(skirt=False)
        self.tr = tr
        names = np.array(self.b.mesh.textures)
        self.slot_name = names[tr['slot']]
        pos = tr['pos']
        self.pos = pos
        self.S_all = Surface(pos)
        self.S_head = Surface(pos[self.slot_name == 'chau_facemap'])
        self.S_suit = Surface(pos[self.slot_name == 'suit'])
        self.S_hands = Surface(pos[np.isin(self.slot_name, ('citizen_sheet', 'handfemale'))])
        # landmarks measured on the mesh (game frame)
        self.eye_l = np.array([4.06, 1.31, 65.10])
        self.eye_r = np.array([4.05, -1.38, 65.07])
        self.nose_tip = np.array([5.28, 0.0, 63.6])
        self.mouth = np.array([3.68, 0.0, 62.12])
        self.chin = np.array([2.73, 0.0, 60.26])
        self.crown_z = 69.8

    def soup(self, flat=None):
        s, tl = self.b.soup(skirt=False, flat=flat or {'eyeball_l': (40, 28, 26), 'eyeball_r': (40, 28, 26)})
        return s, tl

    def acc_scene(self, accs, sprites=()):
        s, tl = self.soup()
        parts = [s]
        for a in accs:
            parts.append(sc.acc_soup(a, tl))
        for sp in sprites:
            parts.append(sc.sprite_soup(sp))
        return pv.concat(parts), tl

    def render(self, accs, path, views=('front', '34', 'left'), height=560, focus=None, sprites=(), pad=0.0):
        scene, tl = self.acc_scene(accs, sprites)
        pts = scene['pos'].reshape(-1, 3)
        if focus is not None:
            pts = pts[focus(pts)]
        ims = []
        for v in views:
            bnd = pv.fit_bounds(pts.reshape(-1, 1, 3), v)
            if pad:
                x0, x1, y0, y1 = bnd
                bnd = (x0 - pad, x1 + pad, y0 - pad, y1 + pad)
            ims.append(pv.render(scene, tl, v, height=height, bounds=bnd))
        out = np.concatenate(ims, axis=1)
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        Image.fromarray(out).save(path)
        return out


def head_focus(p):
    return (p[:, 2] > 57.5) & (p[:, 2] < 80)


def acc(name, mesh, bone, color, nolight=False, alpha=None, nocull=False, translucent=False):
    return Acc(name, mesh, 'ValveBiped.Bip01_' + bone, color=color, nolight=nolight, alpha=alpha, nocull=nocull, translucent=translucent)
