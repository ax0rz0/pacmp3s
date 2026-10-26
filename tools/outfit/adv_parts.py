"""PAC part builders + validator for the advanced Ethics Assistant outfits.

Every builder returns a part dict  {'children': {1: part, ...}, 'self': {...}}  (the format pac_write.dump writes).  Only the keys the class knows are written
(checked against the property catalog of the client's pac3, cat_dev.json), the banned classes (light, halo, projected texture, shake, sunbeams, ...) are refused, and
`validate()` counts the outfit against the PAC editor's "Outfit cost" table.

    stage = Stage(root, 'oni');  url = stage.obj('plates', mesh_local)         # writes obj/adv/oni_plates.obj, returns the raw github url
    tree = group('Cyber Oni', [...], notes=WM)
"""
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_geom as ag
import pac_write as pw
from ethics_acc import friendly
from material_template import MATERIAL_3D

REPO_RAW = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
WM = 'claude skill made by ax0rz0'
HERE = os.path.dirname(os.path.abspath(__file__))

BANNED = {'light', 'light2', 'halo', 'projected_texture', 'shake', 'sunbeams', 'script', 'lock', 'projectile', 'hitscan', 'damage_zone', 'health_modifier', 'weapon', 'physics',
          'player_movement', 'player_config', 'force', 'fog', 'motion_blur', 'woohoo'}

# the PAC editor's Outfit cost table: name -> (count, heavy above, limit)
LIMITS = {'parts': (None, 500, 3000), 'model parts': (None, 60, 150), 'bone-merged models': (None, 4, 8), 'events': (None, 150, None), 'trace events': (None, 10, None),
          'proxies': (None, 100, None), 'URL textures': (None, 8, 16), 'URL models': (None, 16, 32), 'lights': (None, 1, 2), 'particle emitters': (None, 4, 16),
          'beam endpoints': (None, None, 16), 'censor parts': (None, None, 2), '2D text parts': (None, None, 32), 'custom fonts': (None, 4, None)}
TRACE_EVENTS = {'ranger', 'eyetrace_entity_class', 'is_touching', 'is_touching_filter', 'is_touching_life', 'is_touching_scalable', 'seen_by_player', 'viewed_by_owner'}

_CAT = None


def catalog():
    global _CAT
    if _CAT is None:
        _CAT = json.load(open(os.path.join(HERE, 'cat_dev.json')))
    return _CAT


def class_props(name):
    """all property names of a part class (own + inherited)"""
    cat = catalog()
    out, seen = set(), set()
    cur = name
    while cur and cur in cat and cur not in seen:
        seen.add(cur)
        out |= set(cat[cur].get('props', {}))
        cur = cat[cur].get('base')
    return out


# ------------------------------------------------------------------------------------------------------------------------------ small helpers
def vec(x, y, z):
    return ('Vector', (float(x), float(y), float(z)))


def ang(p, y, r):
    return ('Angle', (float(p), float(y), float(r)))


def part(self_dict, children=None):
    return {'children': {i + 1: c for i, c in enumerate(children or [])}, 'self': self_dict}


_uid_counts = {}


def _uid(kind, name, uid):
    if uid:
        return uid
    base = '%s:%s' % (kind, name)
    n = _uid_counts.get(base, 0)
    _uid_counts[base] = n + 1
    return base if n == 0 else '%s#%d' % (base, n)


def reset_uids():
    _uid_counts.clear()


def _std(cls, name, kind, uid, extra, hide=False):
    d = {'ClassName': cls, 'Name': name, 'Hide': hide, 'UniqueID': _uid(kind, name, uid)}
    d.update(extra)
    return d


def group(name, children=(), notes=None, expand=True, uid=None):
    d = {'ClassName': 'group', 'Name': name, 'EditorExpand': expand, 'Hide': False, 'Duplicate': False, 'OwnerName': 'self', 'DrawOrder': 0, 'IsDisturbing': False,
         'TargetEntityUID': '', 'UniqueID': _uid('group', name, uid)}
    if notes:
        d['Notes'] = notes
    return part(d, list(children))


def model(name, url, bone='head', color=(1, 1, 1), material='models/debug/debugwhite', size=1.0, pos=None, ang_=None, nolight=False, alpha=None, translucent=False, nocull=False,
          scale=None, blend=None, hide=False, children=(), uid=None, bonemerge=False, extra=None):
    d = _std('model2', name, 'model', uid, {'Model': url, 'Bone': bone, 'Material': material, 'Color': vec(*color), 'Size': float(size), 'ForceObjUrl': True}, hide)
    if pos is not None:
        d['Position'] = vec(*pos)
    if ang_ is not None:
        d['Angles'] = ang(*ang_)
    if nolight:
        d['NoLighting'] = True
    if alpha is not None:
        d['Alpha'] = float(alpha)
    if translucent:
        d['Translucent'] = True
    if nocull:
        d['NoCulling'] = True
    if scale is not None:
        d['Scale'] = vec(*scale)
    if blend:
        d['BlendMode'] = blend
    if bonemerge:
        d['BoneMerge'] = True
    if extra:
        d.update(extra)
    return part(d, list(children))


def sprite(name, bone, pos, color255=(255, 255, 255), size=1.0, alpha=1.0, path='sprites/light_glow02_add', size_xy=None, translucent=True, ignorez=False, children=(), uid=None, extra=None):
    sx, sy = (size, size) if size_xy is None else size_xy
    d = _std('sprite', name, 'sprite', uid, {'Bone': bone, 'Position': vec(*pos), 'Color': vec(*color255), 'SizeX': float(sx), 'SizeY': float(sy), 'SpritePath': path})
    if alpha != 1.0:
        d['Alpha'] = float(alpha)
    if not translucent:
        d['Translucent'] = False
    if ignorez:
        d['IgnoreZ'] = True
    if extra:
        d.update(extra)
    return part(d, list(children))


def proxy(name, var, expr, axis='', children=(), uid=None, affect_children=False, target_uid=None):
    """a proxy driving property `var` of its parent (name == the pac_proxy command name for command() inputs on old builds)"""
    d = _std('proxy', name, 'proxy', uid, {'VariableName': var, 'Expression': expr})
    if axis:
        d['Axis'] = axis
    if affect_children:
        d['AffectChildren'] = True
    if target_uid:
        d['TargetPartUID'] = target_uid
    return part(d, list(children))


def event(name, ev, arguments, invert, children=(), operator='equal', uid=None, root_owner=True, extra=None):
    """an event that shows / hides its CHILDREN only (old builds default to hiding the parent). invert=True: children shown while the condition is true"""
    d = _std('event', name, 'event', uid, {'Event': ev, 'Arguments': arguments, 'Operator': operator, 'Invert': bool(invert), 'AffectChildrenOnly': True, 'RootOwner': bool(root_owner)})
    if extra:
        d.update(extra)
    return part(d, list(children))


def clip(name, bone, pos, ang_=(0, 0, 0), uid=None, extra=None):
    """a clip2 modifier: parented to a model2 it hides everything BEHIND its plane (the plane normal is the part's forward axis in the bone frame)"""
    d = _std('clip2', name, 'clip', uid, {'Bone': bone, 'Position': vec(*pos), 'Angles': ang(*ang_)})
    if extra:
        d.update(extra)
    return part(d)


def command(name, command_name, uid=None, on_wear=False, extra=None):
    d = _std('command', name, 'command', uid, {'CommandName': command_name, 'ExecuteOnWear': bool(on_wear)})
    if extra:
        d.update(extra)
    return part(d)


def jiggle(name, bone='head', children=(), strain=0.5, speed=1.0, pos=None, ang_=None, uid=None, extra=None):
    d = _std('jiggle', name, 'jiggle', uid, {'Bone': bone, 'Strain': float(strain), 'Speed': float(speed)})
    if pos is not None:
        d['Position'] = vec(*pos)
    if ang_ is not None:
        d['Angles'] = ang(*ang_)
    if extra:
        d.update(extra)
    return part(d, list(children))


def trail(name, bone, pos, path='trails/laser', start_color=(255, 255, 255), end_color=(255, 255, 255), start_size=1.0, end_size=0.0, start_alpha=1.0, end_alpha=0.0, duration=1.0, spacing=0.25,
          stretch=1.0, uid=None, extra=None, children=()):
    d = _std('trail2', name, 'trail', uid, {'Bone': bone, 'Position': vec(*pos), 'TrailPath': path, 'StartColor': vec(*start_color), 'EndColor': vec(*end_color), 'StartSize': float(start_size),
                                           'EndSize': float(end_size), 'StartAlpha': float(start_alpha), 'EndAlpha': float(end_alpha), 'Duration': float(duration), 'Spacing': float(spacing),
                                           'Stretch': float(stretch)})
    if extra:
        d.update(extra)
    return part(d, list(children))


def particles(name, bone, pos, material='sprites/light_glow02_add', start_size=1.0, end_size=0.0, color1=(255, 255, 255), color2=(255, 255, 255), start_alpha=255, end_alpha=0, die_time=1.0,
              fire_delay=0.1, number=1, velocity=0.0, gravity=(0, 0, 0), spread=0.2, position_spread=0.0, additive=True, children=(), uid=None, extra=None, follow=True):
    d = _std('particles', name, 'particles', uid, {'Bone': bone, 'Position': vec(*pos), 'Material': material, 'StartSize': float(start_size), 'EndSize': float(end_size), 'Color1': vec(*color1),
                                                   'Color2': vec(*color2), 'StartAlpha': float(start_alpha), 'EndAlpha': float(end_alpha), 'DieTime': float(die_time),
                                                   'FireDelay': float(fire_delay), 'NumberParticles': int(number), 'Velocity': float(velocity), 'Gravity': vec(*gravity), 'Spread': float(spread),
                                                   'PositionSpread': float(position_spread), 'Lighting': False, 'Collide': False, 'AirResistance': 0.0, 'Follow': bool(follow), 'Additive': bool(additive)})
    if extra:
        d.update(extra)
    return part(d, list(children))


def material3d(name, basetexture='models/debug/debugwhite', uid=None, **params):
    """a material_3d part (VertexLitGeneric): used BY NAME from model2 `Material` / entity2 `Materials`; params are shader parameter names in lower case (phong, phongboost, ...)"""
    d = dict(MATERIAL_3D)
    d.update({'Name': name, 'basetexture': basetexture, 'MaterialOverride': 'all', 'EditorExpand': False, 'Hide': False, 'TargetEntityUID': '', 'UniqueID': _uid('material', name, uid)})
    for k, v in params.items():
        if k not in MATERIAL_3D and k not in ('basetexture',):
            raise KeyError('unknown material_3d parameter %r' % k)
        d[k] = vec(*v) if isinstance(v, tuple) and len(v) == 3 and not isinstance(v[0], str) else v
    return part(d)


def entity2(name, materials='', modifiers='', alpha=1.0, color=(1, 1, 1), brightness=1.0, size=1.0, material='', translucent=False, blend='', uid=None, extra=None, children=()):
    d = {'ClassName': 'entity2', 'Name': name, 'Materials': materials, 'ModelModifiers': modifiers, 'Skin': 0, 'Size': float(size), 'Color': vec(*color), 'Brightness': float(brightness),
         'Alpha': float(alpha), 'InverseKinematics': True, 'NoLighting': False, 'NoCulling': False, 'NoDraw': False, 'DrawShadow': True, 'IgnoreZ': False, 'Translucent': bool(translucent),
         'Invert': False, 'BlendMode': blend, 'AimPartUID': '', 'EyeTargetUID': '', 'TargetEntityUID': '', 'LevelOfDetail': 0, 'NoTextureFiltering': False, 'DrawOrder': 0,
         'LegacyTransform': False, 'IsDisturbing': False, 'Material': material, 'Model': '', 'Hide': False, 'EditorExpand': False, 'Position': vec(0, 0, 0), 'PositionOffset': vec(0, 0, 0),
         'Angles': ang(0, 0, 0), 'AngleOffset': ang(0, 0, 0), 'Scale': vec(1, 1, 1), 'StandingHullHeight': 72, 'CrouchingHullHeight': 36, 'HullWidth': 32,
         'UniqueID': _uid('entity2', name, uid)}
    if extra:
        d.update(extra)
    return part(d, list(children))


# ------------------------------------------------------------------------------------------------------------------------------ asset staging
class Stage:
    """writes bone-local OBJs under <root>/obj/adv/<prefix>_<key>.obj and returns their raw github urls"""

    def __init__(self, root, prefix):
        self.root = root
        self.prefix = prefix
        self.files = {}
        os.makedirs(os.path.join(root, 'obj', 'adv'), exist_ok=True)

    def obj(self, key, mesh_local, comment='', smooth_deg=40.0):
        fn = '%s_%s.obj' % (self.prefix, key)
        path = os.path.join(self.root, 'obj', 'adv', fn)
        nv, nt = ag.write_obj_smooth(mesh_local, path, '%s_%s' % (self.prefix, key), comment=comment or key, smooth_deg=smooth_deg)
        if nv > 24000:
            raise ValueError('%s has %d vertices (limit 24000)' % (fn, nv))
        self.files[fn] = (nv, nt, os.path.getsize(path))
        return REPO_RAW + 'obj/adv/' + fn


def to_bone_local(rig, bone_short, mesh_world, pivot=None):
    """mesh in the in-game world frame (bind pose) -> bone-local OBJ mesh (optionally relative to a pivot given in world space)"""
    from meshgen import Mesh
    W = rig.world[rig.bone(bone_short)]
    R = W[:3, :3]
    origin = W[:3, 3] if pivot is None else np.asarray(pivot, float)
    return Mesh((mesh_world.V - origin) @ R, mesh_world.UV.copy() if len(mesh_world.UV) else np.zeros((len(mesh_world.V), 2)), mesh_world.F.copy())


def local_point(rig, bone_short, p_world):
    W = rig.world[rig.bone(bone_short)]
    return (np.asarray(p_world, float) - W[:3, 3]) @ W[:3, :3]


def bone_name(bone_short):
    return friendly('ValveBiped.Bip01_' + bone_short) if bone_short not in ('forward',) else bone_short


# ------------------------------------------------------------------------------------------------------------------------------ validation / cost
def _is_uid(s):
    return bool(re.fullmatch(r'[0-9a-f]{64}', s)) and s.endswith('a0c3f')


def validate(parts, name, strict_catalog=True, verbose=True):
    """-> (errors, warnings, counts). parts: the {1: root, ...} dict (after remap_uids)"""
    errors, warns = [], []
    counts = {k: 0 for k in LIMITS}
    uids = {}
    obj_urls, tex_urls = set(), set()
    cat = catalog()
    for p in pw.walk(parts):
        s = p['self']
        cls = s.get('ClassName', '')
        nm = s.get('Name', '?')
        counts['parts'] += 1
        if cls in BANNED:
            errors.append('banned class %s (%s)' % (cls, nm))
        u = s.get('UniqueID', '')
        if not _is_uid(u):
            errors.append('bad UniqueID on %s (%r)' % (nm, u))
        if u in uids:
            errors.append('duplicate UniqueID %s: %s / %s' % (u[:12], nm, uids[u]))
        uids[u] = nm
        # property names
        if strict_catalog:
            if cls.startswith('material_'):
                known = set(MATERIAL_3D) | class_props('material_') | class_props('base') | {'basetexture', 'Name', 'UniqueID', 'EditorExpand', 'Hide', 'TargetEntityUID', 'MaterialOverride'}
            else:
                known = class_props(cls) | {'ClassName', 'UniqueID', 'EditorExpand', 'Notes'}
            for k in s:
                if k not in known:
                    errors.append('%s (%s): unknown property %s' % (cls, nm, k))
        if cls == 'model2':
            counts['model parts'] += 1
            if s.get('BoneMerge'):
                counts['bone-merged models'] += 1
            m = s.get('Model', '')
            if m.startswith('http'):
                obj_urls.add(m)
                counts['URL models'] += 1
                if not m.endswith('.obj'):
                    errors.append('%s: model url must end with .obj' % nm)
                if not m.startswith('https://'):
                    errors.append('%s: model url must be https' % nm)
            c = s.get('Color')
            if c and max(c[1]) > 1.0 + 1e-9:
                errors.append('%s: model2 Color must be 0..1' % nm)
        elif cls == 'sprite':
            c = s.get('Color')
            if c and max(c[1]) <= 1.0 and max(c[1]) > 0:
                warns.append('%s: sprite Color looks like 0..1 (sprites use 0..255)' % nm)
        elif cls == 'event':
            counts['events'] += 1
            if s.get('Event') in TRACE_EVENTS:
                counts['trace events'] += 1
            if not s.get('AffectChildrenOnly'):
                errors.append('%s: event without AffectChildrenOnly (old builds hide the parent)' % nm)
        elif cls == 'proxy':
            counts['proxies'] += 1
            ex = s.get('Expression', '')
            for bad in ('extra1', 'extra2', 'extra3', 'clamp', 'nsin', 'ncos', 'feedback', 'sample_and_hold', 'if_event'):
                if re.search(r'\b%s\s*\(' % bad, ex):
                    errors.append('%s: expression uses %s() which old pac builds lack' % (nm, bad))
            if s.get('Axis') and ',' in ex:
                errors.append('%s: Axis combined with a multi-axis expression' % nm)
            if ex.count('(') != ex.count(')'):
                errors.append('%s: unbalanced parentheses' % nm)
        elif cls in ('material_3d', 'material_2d'):
            b = s.get('basetexture', '')
            if b.startswith('http'):
                tex_urls.add(b)
                counts['URL textures'] += 1
        elif cls == 'particles':
            counts['particle emitters'] += 1
        elif cls == 'text':
            counts['2D text parts'] += 1
            if s.get('CreateCustomFont'):
                counts['custom fonts'] += 1
        elif cls == 'beam':
            counts['beam endpoints'] += 1
    # notes mark on root groups
    for k, root in (parts.items() if isinstance(parts, dict) else enumerate(parts, 1)):
        if root['self'].get('ClassName') == 'group' and root['self'].get('Notes') != WM:
            errors.append('root group %s lacks the Notes mark' % root['self'].get('Name'))
    # cost table
    for key, (_, heavy, limit) in LIMITS.items():
        n = counts[key]
        if limit is not None and n > limit:
            errors.append('%s: %d is over the limit %d' % (key, n, limit))
        elif heavy is not None and n > heavy:
            errors.append('%s: %d is over the heavy threshold %d' % (key, n, heavy))
    if verbose:
        print('--- %s: %d errors, %d warnings' % (name, len(errors), len(warns)))
        for e in errors:
            print('  ERROR', e)
        for w in warns:
            print('  warn ', w)
        print('  cost: ' + ', '.join('%s %d' % (k, v) for k, v in counts.items() if v))
    return errors, warns, counts


def finalize(root_parts, slug, out_path=None):
    """remap UIDs (deterministic, 64 hex ending a0c3f), dump with the header mark; returns (text, parts)"""
    parts = {1: root_parts} if 'self' in root_parts else root_parts
    pw.remap_uids(parts, slug)
    text = pw.dump(parts, watermark=WM)
    if out_path:
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, parts


def check_text(text):
    """file-level checks of the generated outfit text"""
    errs = []
    if not text.startswith('-- %s\n\n' % WM):
        errs.append('header mark missing')
    if '\r' in text:
        errs.append('CR in file')
    if text.startswith('﻿'):
        errs.append('BOM')
    if not text.endswith('\n'):
        errs.append('no trailing newline')
    tail = text.rstrip('\n').splitlines()[-1].strip()
    if tail.startswith('--'):
        errs.append('trailing comment')
    return errs
