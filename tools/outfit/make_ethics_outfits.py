"""Build the three BNA Ethics Assistant outfits for models/jericho/citizens/female_04 ("femsuit_04").

Each outfit = one root group holding material_3d parts (image urls as base textures, downloaded by pac over plain HTTP), an entity2 (re-textured suit / skirt / face-and-hair through those
material parts used BY NAME, bodygroup choice) plus own-geometry accessories (bone-local OBJ urls; textured ones use their own material part). Assets are staged under STAGE
(obj/bna, tex/bna) for the repo; the outfits link them by raw GitHub URL.
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

import bna_parts as bp
import ethics_styles as es
import pac_write as pw
import scene as sc

PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'
STAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_bna')

STYLES = {
    'formal': dict(title='Ethics Assistant - BNA Formal', file='ethics asst bna formal', builder=es.build_formal, skirt=True),
    'anima': dict(title='Ethics Assistant - BNA Anima (ears)', file='ethics asst bna anima', builder=es.build_anima, skirt=True),
    'neon': dict(title='Ethics Assistant - BNA Neon', file='ethics asst bna neon', builder=es.build_neon, skirt=False),
}
# material slots of femsuit_04 (1-based, the order of the .mdl texture table): suit-like and skirt-like slots of every skin family
SUIT_SLOTS = (5, 9, 11, 13, 15, 16, 18, 20)
SKIRT_SLOTS = (7, 10, 12, 14, 17, 19, 21)
FACE_SLOT = 1
N_SLOTS = 21


def save_png(arr, path):
    """PNG: the format pac's material parts are known to load from a url (each texture stays under 1 MB)"""
    Image.fromarray(np.asarray(arr)[..., :3]).save(path, 'PNG', optimize=True)


def entity2_part(materials, modifiers, name='femsuit_04 body (textures + bodygroups)'):
    d = {'ClassName': 'entity2', 'Name': name, 'Materials': materials, 'ModelModifiers': modifiers, 'Skin': 0, 'Size': 1.0, 'Color': bp.vec(1, 1, 1), 'Brightness': 1.0, 'Alpha': 1.0,
         'InverseKinematics': True, 'NoLighting': False, 'NoCulling': False, 'NoDraw': False, 'DrawShadow': True, 'IgnoreZ': False, 'Translucent': False, 'Invert': False, 'BlendMode': '',
         'AimPartUID': '', 'EyeTargetUID': '', 'TargetEntityUID': '', 'LevelOfDetail': 0, 'NoTextureFiltering': False, 'DrawOrder': 0, 'LegacyTransform': False, 'IsDisturbing': False,
         'Material': '', 'Model': '', 'Hide': False, 'EditorExpand': False, 'Position': bp.vec(0, 0, 0), 'PositionOffset': bp.vec(0, 0, 0), 'Angles': bp.ang(0, 0, 0),
         'AngleOffset': bp.ang(0, 0, 0), 'Scale': bp.vec(1, 1, 1), 'StandingHullHeight': 72, 'CrouchingHullHeight': 36, 'HullWidth': 32, 'UniqueID': 'entity2:body'}
    return bp.part(d)


def materials_string(face_mat, suit_mat, skirt_mat):
    """the entity2 Materials list: the NAMES of material_3d parts (one entry per model material slot)"""
    slots = [''] * N_SLOTS
    slots[FACE_SLOT - 1] = face_mat
    for s in SUIT_SLOTS:
        slots[s - 1] = suit_mat
    if skirt_mat:
        for s in SKIRT_SLOTS:
            slots[s - 1] = skirt_mat
    return ';'.join(slots)


def build_style(style, out_dir=None, stage=STAGE, textures=None):
    cfg = STYLES[style]
    b, tex = sc.body()
    tex = textures or tex[style]
    tdir = os.path.join(stage, 'tex', 'bna')
    os.makedirs(tdir, exist_ok=True)
    # --- body textures
    base = 'ethics_%s_' % style
    save_png(tex['suit'], os.path.join(tdir, base + 'suit.png'))
    save_png(tex['chau_facemap'], os.path.join(tdir, base + 'face.png'))
    face_url = bp.REPO_RAW + 'tex/bna/' + base + 'face.png'
    suit_url = bp.REPO_RAW + 'tex/bna/' + base + 'suit.png'
    skirt_url = None
    if cfg['skirt']:
        save_png(tex['skirt'], os.path.join(tdir, base + 'skirt.png'))
        skirt_url = bp.REPO_RAW + 'tex/bna/' + base + 'skirt.png'                  # the skirt UVs run from 1 to 2: the material route loads textures wrapping (noclamp)
    # --- accessories
    S, S_suit = sc.surfaces(b, cfg['skirt'])
    acc, spr = cfg['builder'](b, S, S_suit)
    for a in acc:
        a.name = '%s_%s' % (style, a.name)
    for s in spr:
        s.name = '%s_%s' % (style, s.name)
    urls = bp.stage_assets(stage, 'bna', acc, b.rig, 'ethics')
    # material_3d parts first (they are used by name and must exist before the parts that use them), then the entity2, the accessories, the glows
    tag = 'bna %s' % style
    mat_names = {'suit': tag + ' suit', 'face': tag + ' face', 'skirt': tag + ' skirt' if skirt_url else None}
    kids = [bp.material_part(mat_names['face'], face_url), bp.material_part(mat_names['suit'], suit_url)]
    if skirt_url:
        kids.append(bp.material_part(mat_names['skirt'], skirt_url))
    acc_mat_parts, tex_names = bp.texture_material_parts(acc, urls, 'bna')
    kids += acc_mat_parts
    kids.append(entity2_part(materials_string(mat_names['face'], mat_names['suit'], mat_names['skirt']), 'skirt=%d;' % (1 if cfg['skirt'] else 0)))
    kids += bp.parts_for(acc, urls, size=1.0, tex_names=tex_names)
    kids += bp.sprite_parts(spr, b.rig)
    # nicer names in the editor
    for k in kids:
        s = k['self']
        if s['ClassName'] in ('model2', 'sprite'):
            s['Name'] = s['Name'].split('_', 1)[-1].replace('_', ' ')
    root = bp.group(cfg['title'], kids, notes=bp.WATERMARK)
    parts = {1: root}
    pw.remap_uids(parts, 'ethics_bna_' + style)
    text = pw.dump(parts, watermark=bp.WATERMARK)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, cfg['file'] + '.txt'), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, parts, acc, spr, urls


if __name__ == '__main__':
    only = sys.argv[1:] or list(STYLES)
    for style in only:
        text, parts, acc, spr, urls = build_style(style, os.path.join(STAGE, 'outfits'))
        n = sum(1 for _ in pw.walk(parts))
        print('%-7s %-32s %7d bytes, %2d parts (%d accessories, %d sprites)' % (style, STYLES[style]['file'] + '.txt', len(text), n, len(acc), len(spr)))
