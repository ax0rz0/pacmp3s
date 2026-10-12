"""pac3 part dicts (pac_parse / pac_write format) for the BNA accessory groups, plus the asset staging helpers (OBJ + texture files linked by raw GitHub URL)."""
import os

import numpy as np
from PIL import Image

from ethics_acc import friendly

REPO_RAW = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
WATERMARK = 'claude skill made by ax0rz0'


def vec(x, y, z):
    return ('Vector', (float(x), float(y), float(z)))


def ang(p, y, r):
    return ('Angle', (float(p), float(y), float(r)))


def part(self_dict, children=None):
    return {'children': {i + 1: c for i, c in enumerate(children or [])}, 'self': self_dict}


def group(name, children, notes=None, expand=True):
    d = {'ClassName': 'group', 'Name': name, 'EditorExpand': expand, 'Hide': False, 'Duplicate': False, 'OwnerName': 'self', 'DrawOrder': 0, 'IsDisturbing': False, 'TargetEntityUID': '',
         'UniqueID': 'group:' + name}
    if notes:
        d['Notes'] = notes
    return part(d, children)


def model_part(name, url, bone, color01=(1, 1, 1), material='models/debug/debugwhite', size=1.0, nolight=False, alpha=None, translucent=False, nocull=False, uid=None, position=None):
    d = {'ClassName': 'model2', 'Name': name, 'Model': url, 'Bone': bone, 'Material': material, 'Color': vec(*color01), 'Size': float(size), 'Hide': False, 'ForceObjUrl': True,
         'UniqueID': uid or 'model:' + name}
    if position is not None:
        d['Position'] = vec(*position)
    if nolight:
        d['NoLighting'] = True
    if alpha is not None:
        d['Alpha'] = float(alpha)
    if translucent:
        d['Translucent'] = True
    if nocull:
        d['NoCulling'] = True
    return part(d)


def sprite_part(name, bone, position, color255, size, alpha=1.0, path='sprites/light_glow02_add', uid=None):
    d = {'ClassName': 'sprite', 'Name': name, 'Bone': bone, 'Position': vec(*position), 'Color': vec(*color255), 'SizeX': float(size), 'SizeY': float(size), 'SpritePath': path, 'Hide': False,
         'UniqueID': uid or 'sprite:' + name}
    if alpha != 1.0:
        d['Alpha'] = float(alpha)
    return part(d)


def stage_assets(stage_dir, subdir, acc_list, rig, prefix):
    """write bone-local OBJs (and textures) for every accessory under stage_dir/obj/<subdir>/ and stage_dir/tex/<subdir>/. Returns {acc.name: (obj_url, texture_url_or_None)}"""
    out = {}
    od = os.path.join(stage_dir, 'obj', subdir)
    td = os.path.join(stage_dir, 'tex', subdir)
    os.makedirs(od, exist_ok=True)
    os.makedirs(td, exist_ok=True)
    for a in acc_list:
        fn = '%s_%s' % (prefix, a.name)
        lm = a.local_mesh(rig)
        lm.write_obj(os.path.join(od, fn + '.obj'), fn, comment=a.note or a.name)
        tex_url = None
        if a.material == 'texture' and a.texture is not None:
            Image.fromarray(np.asarray(a.texture)).save(os.path.join(td, fn + '.png'), optimize=True)
            tex_url = REPO_RAW + 'tex/%s/%s.png' % (subdir, fn)
        out[a.name] = (REPO_RAW + 'obj/%s/%s.obj' % (subdir, fn), tex_url)
    return out


def parts_for(acc_list, urls, size=1.0, name_prefix=''):
    """model2 parts for a list of Acc using staged urls"""
    kids = []
    for a in acc_list:
        obj_url, tex_url = urls[a.name]
        col = tuple(c / 255.0 for c in (a.color or (255, 255, 255)))
        if tex_url:
            kids.append(model_part(name_prefix + a.name, obj_url, friendly(a.bone), color01=(1, 1, 1), material=tex_url, size=size, nolight=a.nolight, nocull=a.nocull))
        else:
            kids.append(model_part(name_prefix + a.name, obj_url, friendly(a.bone), color01=col, size=size, nolight=a.nolight, alpha=a.alpha, translucent=a.translucent, nocull=a.nocull))
    return kids


def sprite_parts(spr_list, rig, name_prefix=''):
    kids = []
    for sp in spr_list:
        if hasattr(rig, 'localize'):                      # a DeformedRig (tech_deform.py)
            local = rig.localize(sp.bone, sp.pos[None, :])[0]
        else:
            W = rig.world[rig.idx[sp.bone]]
            local = W[:3, :3].T @ (sp.pos - W[:3, 3])
        kids.append(sprite_part(name_prefix + sp.name, friendly(sp.bone), local, sp.color, sp.size, sp.alpha))
    return kids
