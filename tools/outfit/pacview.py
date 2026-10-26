"""pacview - render a pac3 outfit FILE the way pac places and draws it, to check the files themselves (not the generator that wrote them).

Everything here is ported from the pac3 source (develop, plus the server's old build where they differ):
  * the part tree is read from the saved .txt (pac_parse), parts take their class defaults from the pac property catalog (cat_dev.json)
  * bone names go through pac.BoneNameReplacements exactly like pac.GetAllBones (a Bone that does not resolve falls back to the entity origin, like pac)
  * world matrices follow base_movable.lua: base = parent's WorldMatrix (movable parents) / jiggle pos+ang / bone matrix of the parent OWNER (a model2 parent is its own entity,
    which sits at the parent's draw position) ;  W = base * T(Position) * R(Angles) * T(PositionOffset) * R(AngleOffset)
  * model2 OBJ urls are fetched from the live host (cached), vertices are drawn as  pos + R * (Scale*Size * v)  with pac's reversed winding
  * proxies run their expression (sin/cos/abs/max/min/time/command/voice_volume/owner_velocity_length) and write x,y,z into the target property like proxy.lua set()
  * entity2 Materials slot overrides (index = .mdl texture order, null hides), Color/Alpha; BoneMerge donors are skinned into the player's bones, Materials nulls and clip2 planes applied
  * sprites become camera facing glows; trails / particles are drawn as a static snapshot
The pictures go through the ax3d engine (ax_render), so the look is an approximation of the Source shaders - positions, sizes, colours and what is visible are the point.

    python pacview.py "<outfit.txt>" [--views front,34,back] [--focus body|head|hands] [--t 1.5] [--cmd name=value ...] [--out file.png]
"""
import argparse
import json
import math
import os
import re
import sys
import time
import urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ax_render as axr
import pac_parse as pp

PROJECT = os.path.join(HERE, 'adv', 'pv')
axr.PROJECT = PROJECT
CACHE = os.path.join(HERE, 'pv_cache')
PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'
STAGE_OBJ = os.path.join(HERE, 'stage_adv', 'obj', 'adv')
DONOR_ROOT = os.path.join(HERE, 'donor', 'ssm')
PACK_ROOT = 'C:/Users/poopy/Downloads/cg_scp_pm_combined_2830971578'

# ------------------------------------------------------------------------------------------------------------------------------ catalog / defaults
_CAT = json.load(open(os.path.join(HERE, 'cat_dev.json')))


def class_chain(cls):
    out, seen = [], set()
    while cls and cls in _CAT and cls not in seen:
        seen.add(cls)
        out.append(cls)
        cls = _CAT[cls].get('base')
    return out


def is_movable(cls):
    return 'base_movable' in class_chain(cls) or cls == 'base_movable'


def class_defaults(cls):
    d = {}
    for c in reversed(class_chain('material_' if cls.startswith('material_') else cls)):
        for k, v in _CAT[c].get('props', {}).items():
            d[k] = _conv_default(v)
    return d


def _conv_default(v):
    if isinstance(v, dict):
        if 'Vector' in v:
            return np.array(v['Vector'], float)
        if 'Angle' in v:
            return np.array(v['Angle'], float)
    return v


def conv(v):
    """pac_parse value -> python (Vector/Angle/Color tuples become float arrays)"""
    if isinstance(v, tuple) and len(v) == 2 and v[0] in ('Vector', 'Angle', 'Color'):
        return np.array(v[1], float)
    return v


MODEL_CLS = {'model2', 'model'}
ENTITY_CLS = {'entity2', 'entity'}
BONE_CLS = {'bone3', 'bone2', 'bone'}


# ------------------------------------------------------------------------------------------------------------------------------ math
def rotm(a):
    """Source Angle(pitch, yaw, roll) degrees -> 3x3  (R = Rz(yaw) Ry(pitch) Rx(roll), forward = (cp cy, cp sy, -sp))"""
    p, y, r = np.radians(a)
    Rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    Ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    return Rz @ Ry @ Rx


def M4(R=None, t=None):
    m = np.eye(4)
    if R is not None:
        m[:3, :3] = R
    if t is not None:
        m[:3, 3] = t
    return m


# ------------------------------------------------------------------------------------------------------------------------------ pac.BoneNameReplacements
_REPL = [('Anim_Attachment', 'attach'), ('RH', 'right hand'), ('LH', 'left hand'), ('_L_', ' left '), ('_R_', ' right '), ('%p', ' '), ('ValveBiped', ''), ('Bip01', ''), ('Neck1', 'neck'),
         ('Head1', 'head'), ('Toe0', 'toe'), ('lowerarm', 'lower arm'), ('Bip', ''), (' R', ' right'), (' L', ' left')]


def lua_friendly(name):
    s = name
    for a, b in _REPL:
        s = re.sub(r'[!-/:-@\[-`{-~]', ' ', s) if a == '%p' else s.replace(a, b)
    s = s.strip().lower()
    return re.sub(r'(.*?)(\d+)', r'\1 \2', s)


class Player:
    """the Ethics Assistant playermodel (femsuit_04) in the bind pose: bone matrices by pac's friendly names"""

    def __init__(self, sc):
        self.sc = sc
        self.rig = sc.rig
        self.shift = np.zeros(3)             # rigid shift of every bone: a bone3 on the pelvis (root bone) moves the whole skeleton; an entity2 offset only when the viewer is told bones follow it
        self.friendly = {}
        for i, n in enumerate(self.rig.names):
            self.friendly[lua_friendly(n)] = i
        self.raw = {n: i for i, n in enumerate(self.rig.names)}
        self.missing = set()

    def bone_matrix(self, name):
        i = self.friendly.get(name, self.raw.get(name))
        if i is None:
            self.missing.add(name)
            return M4()                      # pac.GetBonePosAng falls back to ent:GetPos(), view yaw (0 here)
        m = np.array(self.rig.world[i], float)
        m[:3, 3] += self.shift
        return m


# ------------------------------------------------------------------------------------------------------------------------------ expressions
_ALLOWED = {'sin', 'cos', 'tan', 'abs', 'max', 'min', 'sqrt', 'floor', 'ceil', 'time', 'command', 'voice_volume', 'owner_velocity_length', 'pi', 'round', 'asin', 'acos', 'atan'}
_TOK = re.compile(r'\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)|([A-Za-z_][A-Za-z_0-9]*)|("(?:[^"\\]|\\.)*")|(\*\*|[-+*/%^(),]))')


def compile_expression(src):
    """Lua-ish arithmetic expression list 'a, b, c' -> list of python code strings (whitelisted tokens only)"""
    toks, pos = [], 0
    while pos < len(src):
        if src[pos:].strip() == '':
            break
        m = _TOK.match(src, pos)
        if not m:
            raise ValueError('cannot tokenise %r at %d' % (src, pos))
        pos = m.end()
        if m.group(1):
            toks.append(m.group(1))
        elif m.group(2):
            if m.group(2) not in _ALLOWED:
                raise ValueError('unknown name %r in %r' % (m.group(2), src))
            toks.append(m.group(2))
        elif m.group(3):
            toks.append(m.group(3))
        else:
            toks.append('**' if m.group(4) == '^' else m.group(4))
    out, cur, depth = [], [], 0
    for t in toks:
        if t == '(':
            depth += 1
        elif t == ')':
            depth -= 1
        if t == ',' and depth == 0:
            out.append(' '.join(cur))
            cur = []
        else:
            cur.append(t)
    out.append(' '.join(cur))
    return out


class Env:
    def __init__(self, t=0.0, commands=None, voice=0.0, velocity=0.0):
        self.t = t
        self.commands = dict(commands or {})
        self.voice = voice
        self.velocity = velocity
        self.ns = dict(sin=math.sin, cos=math.cos, tan=math.tan, abs=abs, max=max, min=min, sqrt=math.sqrt, floor=math.floor, ceil=math.ceil, pi=math.pi, round=round, asin=math.asin,
                       acos=math.acos, atan=math.atan, time=lambda: self.t, command=lambda n: float(self.commands.get(n, 0.0)), voice_volume=lambda: self.voice,
                       owner_velocity_length=lambda: self.velocity)

    def run(self, src):
        codes = compile_expression(src)
        return [float(eval(c, {'__builtins__': {}}, self.ns)) if c.strip() else None for c in codes][:3]


# ------------------------------------------------------------------------------------------------------------------------------ parts
class Part:
    def __init__(self, cls, s, parent):
        self.cls = cls
        self.parent = parent
        self.kids = []
        self.name = s.get('Name', '')
        self.defaults = class_defaults(cls)
        self.p = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in self.defaults.items()}
        for k, v in s.items():
            self.p[k] = conv(v)
        self.hidden = bool(s.get('Hide'))
        self.W = None
        self.notes = []

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()

    def get(self, k, default=None):
        return self.p.get(k, default)

    def vec(self, k, default=(0, 0, 0)):
        v = self.p.get(k)
        return np.array(default, float) if v is None else np.asarray(v, float)

    def has_prop(self, k):
        return k in self.defaults or k in self.p

    def is_hidden(self):
        return self.hidden or (self.parent is not None and self.parent.is_hidden())


def build_tree(path):
    parts = pp.load(path)
    roots = []

    def make(node, parent):
        s = node['self']
        part = Part(s.get('ClassName', '?'), s, parent)
        kids = node.get('children', {})
        for k in sorted(k for k in kids if isinstance(k, int)):
            part.kids.append(make(kids[k], part))
        return part

    if 'self' in parts:
        roots.append(make(parts, None))
    else:
        for k in sorted(k for k in parts if isinstance(k, int)):
            roots.append(make(parts[k], None))
    return roots


# ------------------------------------------------------------------------------------------------------------------------------ proxies (proxy.lua set())
def apply_proxies(roots, env, log):
    def setp(proxy, part, x, y, z, children=False):
        var = proxy.p.get('VariableName', '')
        if part.has_prop(var):
            val = part.p.get(var)
            if isinstance(val, bool):
                part.p[var] = (x or 0) > 0
            elif isinstance(val, (int, float)):
                part.p[var] = x if x is not None else val
            elif isinstance(val, np.ndarray):
                axis = proxy.p.get('Axis', '')
                val = val.copy()
                if axis and axis in ('x', 'y', 'z', 'p', 'r'):
                    val['xyz'.index(axis) if axis in 'xyz' else 'pyr'.index(axis)] = x or 0
                else:
                    if x is not None:
                        val[0] = x
                    if y is not None:
                        val[1] = y
                    if z is not None:
                        val[2] = z
                part.p[var] = val
        if children:
            for c in part.kids:
                setp(proxy, c, x, y, z, True)

    for root in roots:
        for pr in root.walk():
            if pr.cls != 'proxy' or pr.is_hidden():
                continue
            expr = pr.p.get('Expression', '')
            if not expr:
                continue
            try:
                vals = env.run(expr)
            except Exception as e:           # noqa
                log.append('ERROR proxy %s: expression failed: %s' % (pr.name, e))
                continue
            x, y, z = (vals + [None, None, None])[:3]
            tgt = pr.parent
            if pr.p.get('AffectChildren'):
                for c in pr.kids:
                    setp(pr, c, x, y, z, True)
            elif tgt is not None:
                setp(pr, tgt, x, y, z)


# ------------------------------------------------------------------------------------------------------------------------------ world matrices (base_movable.lua)
def parent_owner(part):
    """first ancestor that has its own entity (a model2 / entity2) -> that part, else None (= the player)"""
    cur = part.parent
    while cur is not None:
        if cur.cls in MODEL_CLS:
            return cur
        cur = cur.parent
    return None


def base_matrix(part, player, ent_offset):
    par = part.parent
    if par is not None and par.cls in ('jiggle', 'interpolated_multibone'):
        return par.W.copy() if par.W is not None else M4()
    if par is not None and par.cls not in MODEL_CLS | ENTITY_CLS | BONE_CLS and part.cls not in BONE_CLS and par.W is not None and is_movable(par.cls):
        return par.W.copy()
    own = parent_owner(part)
    bone = part.get('Bone', 'head')
    if own is None or own.get('BoneMerge'):
        return player.bone_matrix(bone)
    # a model2 parent is its own entity: bone lookups on it miss (an OBJ model) and pac falls back to ent:GetPos()/GetAngles() = the parent's draw position
    return own.W.copy() if own.W is not None else M4()


def compute_world(part, player, ent_offset):
    if part.cls in ('group', 'proxy', 'event', 'command', 'material_3d', 'material_2d') or not is_movable(part.cls):
        part.W = None
    elif part.cls in ENTITY_CLS:
        pos = part.vec('Position') + part.vec('PositionOffset')
        part.W = M4(rotm(part.vec('Angles') + part.vec('AngleOffset')), pos)
        ent_offset[:] = pos
    else:
        base = base_matrix(part, player, ent_offset)
        m = base @ M4(rotm(part.vec('Angles')), part.vec('Position'))
        m = m @ M4(None, part.vec('PositionOffset')) @ M4(rotm(part.vec('AngleOffset')))
        part.W = m
    for k in part.kids:
        compute_world(k, player, ent_offset)


# ------------------------------------------------------------------------------------------------------------------------------ OBJ models
class Obj:
    def __init__(self, text, name=''):
        V, VT, VN, F = [], [], [], []
        for line in text.splitlines():
            if line.startswith('v '):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('vt '):
                VT.append([float(x) for x in line.split()[1:3]])
            elif line.startswith('vn '):
                VN.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('f '):
                toks = line.split()[1:]
                idx = []
                for tk in toks:
                    q = (tk.split('/') + ['', ''])[:3]
                    idx.append([int(q[0]) - 1, int(q[1]) - 1 if q[1] else -1, int(q[2]) - 1 if q[2] else -1])
                for i in range(1, len(idx) - 1):
                    F.append([idx[0], idx[i], idx[i + 1]])
        self.V = np.array(V, float)
        self.VT = np.array(VT, float) if VT else np.zeros((0, 2))
        self.VN = np.array(VN, float) if VN else np.zeros((0, 3))
        self.F = np.array(F, int)
        self.name = name


_obj_cache = {}


def fetch_obj(url, notes):
    if url in _obj_cache:
        return _obj_cache[url]
    fn = url.rsplit('/', 1)[-1]
    if os.environ.get('PV_LOCAL') and os.path.exists(os.path.join(STAGE_OBJ, fn)):      # preview unpushed assets from the staging folder
        o = Obj(open(os.path.join(STAGE_OBJ, fn), encoding='utf-8').read(), fn)
        _obj_cache[url] = (o, 'local')
        return o, 'local'
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, fn)
    status = 'cached'
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={'User-Agent': 'pacview'})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        open(path, 'wb').write(data)
        status = 'fetched %d bytes' % len(data)
    data = open(path, 'rb').read()
    loc = os.path.join(STAGE_OBJ, fn)
    if os.path.exists(loc) and open(loc, 'rb').read() != data:
        notes.append('LIVE %s DIFFERS from the staged file' % fn)
    o = Obj(data.decode('utf-8'), fn)
    _obj_cache[url] = (o, status)
    return o, status


_tex_cache = {}
STAGE_TEX = os.path.join(HERE, 'stage_adv', 'tex', 'adv')


def fetch_tex(url, notes):
    """texture url -> path relative to the ax project (png, rgba); PV_LOCAL=1 reads unpushed files from stage_adv/tex/adv"""
    if url in _tex_cache:
        return _tex_cache[url]
    fn = url.rsplit('/', 1)[-1]
    data = None
    if os.environ.get('PV_LOCAL') and os.path.exists(os.path.join(STAGE_TEX, fn)):
        data = open(os.path.join(STAGE_TEX, fn), 'rb').read()
    else:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, fn)
        if not os.path.exists(path):
            req = urllib.request.Request(url, headers={'User-Agent': 'pacview'})
            with urllib.request.urlopen(req, timeout=60) as r:
                open(path, 'wb').write(r.read())
        data = open(path, 'rb').read()
        loc = os.path.join(STAGE_TEX, fn)
        if os.path.exists(loc) and open(loc, 'rb').read() != data:
            notes.append('LIVE texture %s DIFFERS from the staged file' % fn)
    import io
    im = Image.open(io.BytesIO(data)).convert('RGBA')
    rel = 'tex/pvtex_%s.png' % os.path.splitext(fn)[0]
    os.makedirs(os.path.join(PROJECT, 'tex'), exist_ok=True)
    im.save(os.path.join(PROJECT, rel))
    _tex_cache[url] = rel
    return rel


# ------------------------------------------------------------------------------------------------------------------------------ material mapping (Source shader params -> ax3d PBR, approximate)
def phong_rough(exp):
    return float(np.clip(0.95 - 0.115 * math.log2(max(float(exp), 1.0)), 0.15, 0.9))


def style_of(part, mats, ent_color=(1, 1, 1), ent_alpha=1.0):
    """-> dict of ax item fields for a model2 / body slot using material part `Material`"""
    mname = part.get('Material', '') if part is not None else ''
    mp = mats.get(mname)
    col = np.array(part.vec('Color', (1, 1, 1)) if part is not None else (1, 1, 1), float) * float(part.get('Brightness', 1.0) if part is not None else 1.0) * np.array(ent_color)
    st = dict(rough=0.6, metal=0.0, double=False, glow=False, additive=False)
    alpha = float(part.get('Alpha', 1.0)) * ent_alpha if part is not None else ent_alpha
    if mp is not None:
        col = col * np.clip(mp.vec('color', (1, 1, 1)), 0, 1)
        if mp.get('phong'):
            st['rough'] = phong_rough(mp.get('phongexponent', 20))
        else:
            st['rough'] = 0.75
        if mp.get('envmap'):
            tint = np.clip(mp.vec('envmaptint', (1, 1, 1)), 0, 1)
            st['metal'] = float(np.clip(tint.mean() * 1.5, 0.0, 0.9))
        if mp.get('nocull'):
            st['double'] = True
        if mp.get('additive'):
            st['additive'] = True
        alpha *= float(mp.get('alpha', 1.0))
        bt = mp.get('basetexture', '')
        if isinstance(bt, str) and bt.startswith('http'):
            st['tex_url'] = bt
            st['alphatest'] = bool(mp.get('alphatest'))
            st['cutoff'] = float(mp.get('alphatestreference', 0.5))
            st['translucent'] = bool(mp.get('translucent'))
    if part is not None and part.get('NoLighting'):
        st['glow'] = True
    if part is not None and part.get('NoCulling'):
        st['double'] = True
    st['color'] = tuple(float(c) for c in np.clip(col * 255.0, 0, 255))
    st['alpha'] = alpha if (alpha < 0.999) else None
    return st


# ------------------------------------------------------------------------------------------------------------------------------ the scene builder
def to_ax(V):
    return axr.to_ax(V)


def ax_n(N):
    N = np.asarray(N, float)
    return np.stack([-N[..., 1], N[..., 2], -N[..., 0]], -1)


class Build:
    def __init__(self, path, t=1.5, commands=None, voice=0.0, velocity=0.0, follow_entity_offset=False, quiet=False):
        import adv_scene as asn
        self.path = path
        self.env = Env(t, commands, voice, velocity)
        self.roots = build_tree(path)
        self.sc = asn.Scene()
        self.player = Player(self.sc)
        self.log = []
        self.items = []                # static meshes (ax items)
        self.sprites = []              # (pos_src, (sx, sy), color255, alpha)
        self.follow = follow_entity_offset
        self.n = 0
        self.stats = dict(models=0, urls=0, sprites=0, trails=0, particles=0, proxies=0, bonemerge=0)
        apply_proxies(self.roots, self.env, self.log)
        self.bone3_shift = np.zeros(3)
        for r in self.roots:
            for p in r.walk():
                if p.cls == 'bone3' and not p.is_hidden():
                    i = self.player.friendly.get(p.get('Bone'))
                    if i == 0:                # the pelvis is the root bone of this skeleton: its translation (in its own axes) moves every bone rigidly
                        R = np.array(self.sc.rig.world[0], float)[:3, :3]
                        self.bone3_shift += R @ (p.vec('Position') + p.vec('PositionOffset'))
                    else:
                        self.log.append('NOTE bone3 on %r: only a pelvis translation is modelled by the viewer' % p.get('Bone'))
        self.player.shift = self.bone3_shift.copy()
        self.ent_offset = np.zeros(3)
        for r in self.roots:                      # first pass finds the entity2 offset
            compute_world(r, self.player, self.ent_offset)
        if self.follow:
            self.player.shift = self.bone3_shift + self.ent_offset
            for r in self.roots:
                compute_world(r, self.player, self.ent_offset)
        self.mats = {}
        for r in self.roots:
            for p in r.walk():
                if p.cls.startswith('material_'):
                    self.mats[p.name] = p
        self.entity = None
        for r in self.roots:
            for p in r.walk():
                if p.cls == 'entity2' and not p.is_hidden():
                    self.entity = p
        self.lint()
        self.body()
        for r in self.roots:
            self.collect(r)
        self.finish_notes()

    # ---------------------------------------------------------------- lint
    def lint(self):
        names = {}
        for r in self.roots:
            for p in r.walk():
                if p.cls == 'proxy':
                    self.stats['proxies'] += 1
                    cmds = re.findall(r'command\("([^"]+)"\)', p.get('Expression', ''))
                    for c in cmds:
                        if p.name != c:
                            self.log.append('WARN proxy %r reads command("%s") but is named differently (the server build reads the proxy\'s own Name)' % (p.name, c))
                if p.cls == 'model2' and not p.is_hidden():
                    m = p.get('Material', '')
                    if m and '/' not in m and m not in self.mats:
                        self.log.append('WARN model2 %r: material part %r not found' % (p.name, m))

    # ---------------------------------------------------------------- the playermodel
    def planes_of(self, part):
        """clip2 children -> [(normal, constant)] in the unshifted bind frame (pac: LocalToWorld(Position+Offset, Angles+AngleOffset, bone pos/ang), normal = forward, keeps n.p >= c)"""
        planes = []
        for k in part.kids:
            if k.cls == 'clip2' and not k.is_hidden():
                B = self.player.bone_matrix(k.get('Bone', 'head'))
                m = B @ M4(rotm(k.vec('Angles') + k.vec('AngleOffset')), k.vec('Position') + k.vec('PositionOffset'))
                nrm = m[:3, :3] @ np.array([1.0, 0, 0])
                planes.append((nrm, float(nrm @ (m[:3, 3] - self.player.shift))))
        return planes

    def body(self):
        ent = self.entity
        entries = (ent.get('Materials', '') if ent is not None else '').split(';')
        ent_col = ent.vec('Color', (1, 1, 1)) * float(ent.get('Brightness', 1.0)) if ent is not None else np.ones(3)
        ent_alpha = float(ent.get('Alpha', 1.0)) if ent is not None else 1.0
        translucent = bool(ent.get('Translucent')) if ent is not None else False
        off = np.array(self.bone3_shift, float)
        if ent is not None:
            off = off + np.array(self.ent_offset, float)
        planes = self.planes_of(ent) if ent is not None else []
        self.draw_player_model('body', entries, planes, ent_col, ent_alpha, translucent, off, ent.get('Material', '') if ent is not None else '')

    def draw_player_model(self, tag, entries, planes, ent_col, ent_alpha, translucent, off, material=''):
        """the playermodel (or a bone-merged copy of it) slot by slot: Materials entries (null hides, a material part name re-skins), clip planes cut the triangles"""
        sc = self.sc
        if not hasattr(self, '_btr'):
            self._btr = sc.b.triangles(skirt=False)
            self._base = {it['name'][5:]: it for it in axr.export_body(sc, skirt=False)}
        tr, base = self._btr, self._base
        names = list(sc.b.mesh.textures)
        for slot, name in enumerate(names):
            sel = np.nonzero(tr['slot'] == slot)[0]
            if len(sel) == 0 or name not in base:
                continue
            entry = entries[slot] if slot < len(entries) else ''
            if entry == 'null':
                continue
            P, N, UV = tr['pos'][sel], tr['nrm'][sel], tr['uv'][sel]
            for nrm, c in planes:
                P, N, UV = clip_soup(P, N, UV, nrm, c)
                if len(P) == 0:
                    break
            if len(P) == 0:
                continue
            it0 = base[name]
            it = axr.export_soup('pv_%s_%s' % (tag, name), to_ax(P), ax_n(N), UV, tex_png=None, color=it0['color'], rough=it0['rough'], metal=0.0, double=True)
            it['tex'] = it0.get('tex')
            it['offset'] = tuple(to_ax(off)) if np.any(off) else (0.0, 0.0, 0.0)
            mname = entry or (material if material in self.mats else '')
            if mname and mname in self.mats:
                mp = self.mats[mname]
                col = np.clip(mp.vec('color', (1, 1, 1)), 0, 1) * ent_col
                it['color'] = tuple(float(c) for c in np.clip(col * 255, 0, 255))
                it['tex'] = None
                it['rough'] = phong_rough(mp.get('phongexponent', 20)) if mp.get('phong') else 0.75
                if mp.get('envmap'):
                    it['metal'] = float(np.clip(np.clip(mp.vec('envmaptint', (1, 1, 1)), 0, 1).mean() * 1.5, 0, 0.9))
                if mp.get('additive'):
                    it['additive'] = True
                    it['glow'] = True
                    it['emissive'] = tuple(float(c) / 255.0 * 0.85 for c in it['color'])
                    it['alpha'] = max(0.05, ent_alpha * 0.6)
                elif ent_alpha < 0.999 and translucent:
                    it['alpha'] = ent_alpha
            else:
                if entry and '/' not in entry:
                    self.log.append('WARN Materials slot %d: %r is not a material part' % (slot + 1, entry))
                if np.any(ent_col != 1.0):
                    it['color'] = tuple(float(c) for c in np.clip(np.array(it['color'], float) * ent_col, 0, 255))
                if ent_alpha < 0.999 and translucent:
                    it['alpha'] = ent_alpha
            self.items.append(it)

    # ---------------------------------------------------------------- walking the tree
    def collect(self, part):
        if part.is_hidden():
            return
        if part.cls == 'model2':
            self.model(part)
        elif part.cls == 'sprite':
            self.sprite(part)
        elif part.cls == 'trail2':
            self.stats['trails'] += 1
        elif part.cls == 'particles':
            self.stats['particles'] += 1
            self.particles(part)
        for k in part.kids:
            self.collect(k)

    def next_name(self, base):
        self.n += 1
        return 'p%03d_%s' % (self.n, re.sub(r'[^A-Za-z0-9]+', '_', base).strip('_')[:28])

    def model(self, part):
        self.stats['models'] += 1
        url = part.get('Model', '')
        if part.get('BoneMerge'):
            self.stats['bonemerge'] += 1
            if os.path.basename(url).lower() == 'female_04.mdl':
                entries = part.get('Materials', '').split(';')
                self.draw_player_model('plug%d' % self.stats['bonemerge'], entries, self.planes_of(part), np.ones(3), float(part.get('Alpha', 1.0)), False, np.array(self.player.shift, float),
                                       part.get('Material', ''))
                self.log.append('NOTE bonemerged copy of the playermodel %r: slots %s' % (part.name, [i + 1 for i, e in enumerate(entries) if e != 'null']))
                return
            self.donor(part)
            return
        if float(part.get('Alpha', 1.0)) == 0 or float(part.get('Size', 1.0)) == 0:
            return
        if not url.startswith('http'):
            self.stock(part, url)
            return
        self.stats['urls'] += 1
        try:
            obj, status = fetch_obj(url, self.log)
        except Exception as e:               # noqa
            self.log.append('ERROR model %r: cannot fetch %s (%s)' % (part.name, url, e))
            return
        S = part.vec('Scale', (1, 1, 1)) * float(part.get('Size', 1.0))
        W = part.W
        if W is None:
            return
        R, t = W[:3, :3], W[:3, 3]
        Vw = (obj.V * S) @ R.T + t
        has_n = len(obj.VN) > 0
        Nw = None
        if has_n:
            Nw = (obj.VN / S) @ R.T
            Nw /= np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-12)
        flip = np.prod(np.sign(S)) < 0
        nm = self.next_name(part.name)
        rel = 'models/%s.obj' % nm
        self.write_obj(rel, nm, Vw, Nw, obj, flip)
        self.items.append(self.model_item(nm, rel, part))

    def model_item(self, nm, rel, part):
        st = style_of(part, self.mats)
        it = dict(name=nm, obj=rel, color=st['color'], glow=st['glow'], rough=st['rough'], metal=st['metal'], alpha=st['alpha'], emissive=None, double=st['double'], pivot=None, tex=None,
                  additive=st['additive'])
        if st['additive'] and not st['glow']:        # an additive material adds its colour to what is behind it
            it['glow'] = True
            it['emissive'] = tuple(float(c) / 255.0 * 0.85 for c in st['color'])
            it['alpha'] = min(st['alpha'] if st['alpha'] is not None else 1.0, 0.6)
        if st.get('tex_url'):
            try:
                it['tex'] = fetch_tex(st['tex_url'], self.log)
            except Exception as e:               # noqa
                self.log.append('ERROR texture %s: %s' % (st['tex_url'], e))
            if st.get('alphatest'):
                it['mask'] = True
                it['cutoff'] = st.get('cutoff', 0.5)
            elif st.get('translucent'):
                it['blend'] = True
            it['color'] = (255, 255, 255)
        return it

    def write_obj(self, rel, nm, Vw, Nw, obj, flip):
        path = os.path.join(PROJECT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        A = to_ax(Vw)
        An = ax_n(Nw) if Nw is not None else None
        with open(path, 'w', newline='\n') as f:
            f.write('o %s\n' % nm)
            for v in A:
                f.write('v %.5f %.5f %.5f\n' % tuple(v))
            for t_ in obj.VT:
                f.write('vt %.5f %.5f\n' % tuple(t_))
            if An is not None:
                for n in An:
                    f.write('vn %.5f %.5f %.5f\n' % tuple(n))
            for tri in obj.F:
                if flip:
                    tri = tri[[0, 2, 1]]
                f.write('f ' + ' '.join(('%d/%s/%s' % (c[0] + 1, c[1] + 1 if c[1] >= 0 else '', c[2] + 1 if c[2] >= 0 else '')) if An is not None else ('%d/%s' % (c[0] + 1, c[1] + 1 if c[1] >= 0 else '')) for c in tri) + '\n')

    def stock(self, part, mdl):
        """a stock .mdl: only the hunter sphere used for the orbs has a stand-in"""
        m = re.search(r'sphere(\d+)x(\d+)', mdl)
        if not m or part.W is None:
            self.log.append('NOTE stock model %s on %r has no stand-in here' % (mdl, part.name))
            return
        r = 47.45 * 0.25 / 2.0                 # hunter 1x1 plate = 47.45 units, sphere025x025 is a quarter of it across
        S = float(part.get('Size', 1.0)) * part.vec('Scale', (1, 1, 1))
        n_u, n_v = 24, 16
        verts, norms, faces = [], [], []
        for j in range(n_v + 1):
            th = math.pi * j / n_v
            for i in range(n_u + 1):
                ph = 2 * math.pi * i / n_u
                verts.append([math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)])
        verts = np.array(verts)
        for j in range(n_v):
            for i in range(n_u):
                a = j * (n_u + 1) + i
                b = a + n_u + 1
                faces.append([[a, -1, a], [a + 1, -1, a + 1], [b, -1, b]])
                faces.append([[a + 1, -1, a + 1], [b + 1, -1, b + 1], [b, -1, b]])
        o = Obj('', 'sphere')
        o.V, o.VN, o.VT, o.F = verts * r, verts, np.zeros((0, 2)), np.array(faces)
        W = part.W
        R, t = W[:3, :3], W[:3, 3]
        Vw = (o.V * S) @ R.T + t
        Nw = (o.VN / S) @ R.T
        Nw /= np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-12)
        nm = self.next_name(part.name)
        rel = 'models/%s.obj' % nm
        self.write_obj(rel, nm, Vw, Nw, o, False)
        self.items.append(self.model_item(nm, rel, part))

    # ---------------------------------------------------------------- sprites, particles
    def sprite(self, part):
        self.stats['sprites'] += 1
        if part.W is None:
            return
        size = float(part.get('Size', 1.0))
        sx, sy = float(part.get('SizeX', 1.0)) * size, float(part.get('SizeY', 1.0)) * size
        col = np.clip(part.vec('Color', (255, 255, 255)), 0, 255)
        self.sprites.append((part.W[:3, 3].copy(), (sx, sy), tuple(col), float(part.get('Alpha', 1.0)), True))

    def particles(self, part):
        """a static snapshot of an emitter: deterministic spread of particles along their life"""
        if part.W is None:
            return
        rng = np.random.RandomState(abs(hash(part.name)) % (2 ** 31))
        die = float(part.get('DieTime', 1.0))
        delay = max(float(part.get('FireDelay', 0.1)), 0.02)
        num = int(part.get('NumberParticles', 1))
        count = int(min(max(die / delay * num, 1), 60))
        pos = part.W[:3, 3]
        R = part.W[:3, :3]
        vel = float(part.get('Velocity', 0.0))
        spread = float(part.get('Spread', 0.0))
        grav = part.vec('Gravity', (0, 0, 0))
        pspread = float(part.get('PositionSpread', 0.0))
        c1 = np.clip(part.vec('Color1', (255, 255, 255)), 0, 255)
        sa, ea = float(part.get('StartAlpha', 255)) / 255.0, float(part.get('EndAlpha', 0)) / 255.0
        ss, es = float(part.get('StartSize', 1.0)), float(part.get('EndSize', 0.0))
        follow = bool(part.get('Follow'))
        for i in range(count):
            age = rng.uniform(0, die)
            f = age / die
            d = rng.normal(size=3) * spread
            d = d + np.array([1.0, 0, 0]) * 1.0
            d = d / np.linalg.norm(d)
            d_w = R @ d
            p0 = pos + rng.uniform(-1, 1, 3) * pspread
            p = p0 + d_w * vel * age + 0.5 * grav * age * age
            size = ss + (es - ss) * f
            a = sa + (ea - sa) * f
            if size > 0.01 and a > 0.01:
                self.sprites.append((p, (size, size), tuple(c1), a * 0.9, bool(part.get('Additive'))))

    # ---------------------------------------------------------------- bonemerged donor head (Song So Mi)
    def donor(self, part):
        import donor_tools as dt
        import run_donor_preview as rdp
        from PIL import Image as _I
        mdl = part.get('Model', '')
        local = os.path.join(DONOR_ROOT, mdl.replace('/', os.sep))
        if not os.path.exists(local):                                  # the server's SCP playermodel pack (job models) is on this PC too
            local = os.path.join(PACK_ROOT, mdl.replace('/', os.sep))
        if not os.path.exists(local):
            self.log.append('NOTE bonemerge model %s not available locally (it comes from the workshop addon)' % mdl)
            return
        d, tr, P, N = rdp.load(local)
        entries = part.get('Materials', '').split(';')
        planes = self.planes_of(part)
        used, hidden = [], []
        for si, name in enumerate(d.tex):
            if si < len(entries) and entries[si] == 'null':
                hidden.append(name)
                continue
            sel = np.nonzero(tr['slot'] == si)[0]
            if len(sel) == 0:
                continue
            Pp, Nn, UV = P[sel], N[sel], tr['uv'][sel]
            UV = UV - np.floor(UV.min(axis=1, keepdims=True))                     # source textures repeat: bring every triangle's uvs into [0, 1)
            for nrm, c in planes:
                Pp, Nn, UV = clip_soup(Pp, Nn, UV, nrm, c)
                if len(Pp) == 0:
                    break
            if len(Pp) == 0:
                continue
            arr = d.texture_array(name)
            im = None
            if arr is not None:
                im = _I.fromarray(np.asarray(arr).astype(np.uint8))
                if im.mode != 'RGBA':
                    im = im.convert('RGBA')
                if max(im.size) > 1024:
                    im.thumbnail((1024, 1024))
            shader, params = d.vmt_params(name)
            masked = name in rdp.MASKED or 'alphatest' in params or 'translucent' in params
            tint = vmt_tint(params)
            if im is not None and tint is not None:                  # $color2 / $color multiply the albedo (hair 2.5, lipstick dark rose, cyberware 0.1 ...)
                arr = np.asarray(im).astype(float)
                arr[..., :3] = np.clip(arr[..., :3] * np.array(tint), 0, 255)
                im = _I.fromarray(arr.astype(np.uint8), 'RGBA')
            it = axr.export_soup('pv_donor_%s' % name, to_ax(Pp), ax_n(Nn), UV, tex_png=im, color=(200, 200, 200), rough=0.45, mask=masked, double=True)
            it['offset'] = tuple(to_ax(self.player.shift))
            self.items.append(it)
            used.append(name)
        self.log.append('NOTE donor %s: drawn slots %s ; hidden by Materials: %s ; clip planes %d' % (os.path.basename(mdl), used, hidden, len(planes)))

    def finish_notes(self):
        for b in sorted(self.player.missing):
            self.log.append('WARN Bone %r does not exist on the playermodel (the part would sit at the feet)' % b)


def vmt_tint(params):
    """$color2 (or $color) of a VMT as an rgb multiplier, e.g. '[ .3 .13 .16 ]' -> (0.3, 0.13, 0.16); None when absent"""
    for k in ('color2', 'color'):
        v = params.get(k)
        if v:
            nums = re.findall(r'-?\d*\.?\d+(?:[eE][+-]?\d+)?', v)
            if len(nums) >= 3:
                return tuple(float(x) for x in nums[:3])
            if len(nums) == 1:
                return (float(nums[0]),) * 3
    return None


def clip_soup(P, N, UV, n, c):
    """keep n.p >= c ; triangles (T,3,3) with normals and uvs, clipped exactly (Sutherland-Hodgman on the straddling triangles only)"""
    d = np.einsum('tkj,j->tk', P, n) - c
    inside = (d >= 0).all(1)
    outside = (d < 0).all(1)
    cross = ~(inside | outside)
    out_P, out_N, out_U = [P[inside]], [N[inside]], [UV[inside]]
    cp, cn, cu = [], [], []
    for t in np.nonzero(cross)[0]:
        dd = d[t]
        polyP, polyN, polyU = [], [], []
        for i in range(3):
            j = (i + 1) % 3
            if dd[i] >= 0:
                polyP.append(P[t][i]); polyN.append(N[t][i]); polyU.append(UV[t][i])
            if (dd[i] >= 0) != (dd[j] >= 0):
                f = dd[i] / (dd[i] - dd[j])
                polyP.append(P[t][i] + (P[t][j] - P[t][i]) * f)
                nn = N[t][i] + (N[t][j] - N[t][i]) * f
                polyN.append(nn / max(np.linalg.norm(nn), 1e-9))
                polyU.append(UV[t][i] + (UV[t][j] - UV[t][i]) * f)
        for i in range(1, len(polyP) - 1):
            cp.append([polyP[0], polyP[i], polyP[i + 1]])
            cn.append([polyN[0], polyN[i], polyN[i + 1]])
            cu.append([polyU[0], polyU[i], polyU[i + 1]])
    if cp:
        out_P.append(np.array(cp)); out_N.append(np.array(cn)); out_U.append(np.array(cu))
    return np.concatenate(out_P), np.concatenate(out_N), np.concatenate(out_U)


# ------------------------------------------------------------------------------------------------------------------------------ rendering
_GLOW_PNG = None


def glow_texture():
    global _GLOW_PNG
    rel = 'tex/pv_glow.png'
    full = os.path.join(PROJECT, rel)
    if not os.path.exists(full):
        n = 128
        y, x = np.mgrid[0:n, 0:n]
        r = np.hypot(x - (n - 1) / 2, y - (n - 1) / 2) / (n / 2)
        a = np.clip(1 - r, 0, 1) ** 2.2
        core = np.exp(-(r * 3.2) ** 2)
        a = np.clip(a * 0.85 + core * 0.6, 0, 1)
        rgba = np.zeros((n, n, 4), np.uint8)
        rgba[..., :3] = 255
        rgba[..., 3] = (a * 255).astype(np.uint8)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        Image.fromarray(rgba, 'RGBA').save(full)
    return rel


def sprite_items(sprites, cam_src, base_idx=0):
    """camera facing glow quads for one view (Source frame positions) -> ax items"""
    items = []
    rel_tex = glow_texture()
    up_hint = np.array([0, 0, 1.0])
    for i, (p, (sx, sy), col, alpha, add) in enumerate(sprites):
        to_cam = cam_src - p
        dist = np.linalg.norm(to_cam)
        if dist < 1e-6:
            continue
        f = to_cam / dist
        right = np.cross(up_hint, f)
        if np.linalg.norm(right) < 1e-6:
            right = np.array([0, 1.0, 0])
        right /= np.linalg.norm(right)
        up = np.cross(f, right)
        hx, hy = sx / 2 * 1.0, sy / 2 * 1.0
        corners = np.array([p - right * hx - up * hy, p + right * hx - up * hy, p + right * hx + up * hy, p - right * hx + up * hy])
        A = to_ax(corners)
        nm = 'spr%03d' % i
        rel = 'models/%s.obj' % nm
        path = os.path.join(PROJECT, rel)
        nrm = to_ax(f)  # direction only matters up to sign for an unlit quad
        nrm = ax_n(f)
        with open(path, 'w', newline='\n') as fh:
            fh.write('o %s\n' % nm)
            for v in A:
                fh.write('v %.5f %.5f %.5f\n' % tuple(v))
            for uv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                fh.write('vt %d %d\n' % uv)
            fh.write('vn %.5f %.5f %.5f\n' % tuple(nrm))
            fh.write('f 1/1/1 2/2/1 3/3/1\nf 1/1/1 3/3/1 4/4/1\n')
        c = np.array(col, float) / 255.0
        if not add:                       # smoke style particles: dim, less opaque
            c, alpha = c * 0.45, alpha * 0.55
        items.append(dict(name=nm, obj=rel, color=tuple(c * 255), glow=True, rough=0.8, metal=0.0, alpha=float(np.clip(alpha, 0, 1)), emissive=tuple(c * 2.2), double=True, pivot=None, tex=rel_tex,
                          sprite=True))
    return items


def patch_scene_text():
    """ax_render.scene_text with per-item offsets, additive and textured-alpha sprites"""
    def _mat_line(it):
        col = it['color']
        f = []
        if it.get('sprite'):
            e = it['emissive']
            a = int(round(255 * it['alpha']))
            return 'Material basecolourtexture=%s basecolour=#000000 emissive=%.3f,%.3f,%.3f alphamode=Blend doublesided=true roughness=0.9 metallic=0.0' % (it['tex'], *e)
        if it.get('tex'):
            f.append('basecolourtexture=%s' % it['tex'])
            f.append('basecolour=#FFFFFF')
        else:
            f.append('basecolour=%s' % axr.hexcol(col))
        f.append('roughness=%.3f metallic=%.3f' % (it['rough'], it['metal']))
        if it.get('glow'):
            e = it.get('emissive')
            if e is None:
                e = tuple(c / 255.0 * 3.2 for c in col)
            f = ['basecolour=#000000', 'roughness=0.8', 'emissive=%.3f,%.3f,%.3f' % tuple(e)]
        if it.get('alpha') is not None:
            f.append('alphamode=Blend')
            c = it['color']
            f = [x for x in f if not x.startswith('basecolour=')]
            base = '#%02X%02X%02X%02X' % (int(c[0]), int(c[1]), int(c[2]), int(round(255 * it['alpha'])))
            if it.get('glow'):
                base = '#000000%02X' % int(round(255 * it['alpha']))
            f.append('basecolour=%s' % base)
        if it.get('blend') and it.get('tex'):
            f.append('alphamode=Blend')
        if it.get('mask'):
            f.append('alphamode=Mask alphacutoff=%.2f' % it.get('cutoff', 0.5))
        if it.get('double'):
            f.append('doublesided=true')
        return 'Material ' + ' '.join(f)
    axr._mat_line = _mat_line

    orig = axr.scene_text

    def scene_text(items, *a, **k):
        text = orig(items, *a, **k)
        # per-item offsets
        for it in items:
            off = it.get('offset')
            if off and any(off):
                text = text.replace('  %s:\n    Transform position=0,0,0\n' % it['name'], '  %s:\n    Transform position=%.5f,%.5f,%.5f\n' % (it['name'], *off))
        return text
    axr.scene_text = scene_text


patch_scene_text()

VIEW_FOCUS = {'body': ((0.4, 0.0, 37.0), 38.0, 30.0), 'head': ((0.4, 0.0, 65.0), 9.5, 22.0), 'hands': ((8.0, 0.0, 32.0), 24.0, 30.0), 'upper': ((0.4, 0.0, 52.0), 20.0, 26.0)}


def render(build, views=('front', '34'), focus='body', size=(480, 680), ax=None, exposure=1.0, key=3.6, ambient=1.3, radius=None, **extra):
    own = ax is None
    ax = ax or axr.Ax(project=PROJECT)
    foc, rad, fov = VIEW_FOCUS[focus] if isinstance(focus, str) else focus
    rad = radius or rad
    ims = []
    try:
        ax.call('render.settings', dict(bloom=True, bloom_threshold=1.7, bloom_strength=0.45, ssao=True, ssao_radius=0.12, ssao_strength=1.2, msaa=4, shadows=True, shadow_map_size=4096,
                                        shadow_distance=6.0, ibl=True))
        dist = rad / np.tan(np.radians(fov) / 2) * 1.08
        for v in views:
            d = np.asarray(axr.VIEWS[v] if isinstance(v, str) else v, float)
            d = d / np.linalg.norm(d)
            cam_src = np.asarray(foc, float) + d * dist
            items = list(build.items) + sprite_items(build.sprites, cam_src)
            img = axr.render_item_views(ax, items, views=[v], focus=foc, radius=rad, fov=fov, size=size, key=key, ambient=ambient, exposure=exposure, **extra)
            ims.append(img)
    finally:
        if own:
            ax.close()
    return np.concatenate(ims, axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outfit')
    ap.add_argument('--views', default='front,34')
    ap.add_argument('--focus', default='body')
    ap.add_argument('--t', type=float, default=1.5)
    ap.add_argument('--cmd', action='append', default=[])
    ap.add_argument('--out', default=None)
    ap.add_argument('--size', default='480x680')
    ap.add_argument('--follow-entity-offset', action='store_true')
    a = ap.parse_args()
    path = a.outfit if os.path.exists(a.outfit) else os.path.join(PAC_DIR, a.outfit)
    cmds = {}
    for c in a.cmd:
        k, v = c.split('=')
        cmds[k] = float(v)
    t0 = time.time()
    b = Build(path, t=a.t, commands=cmds, follow_entity_offset=a.follow_entity_offset)
    print('%s: %s  (%.1fs)' % (os.path.basename(path), b.stats, time.time() - t0))
    for line in b.log:
        print('  ', line)
    w, h = (int(x) for x in a.size.split('x'))
    img = render(b, views=a.views.split(','), focus=a.focus, size=(w, h))
    out = a.out or os.path.join(HERE, 'adv', 'pv_out', os.path.splitext(os.path.basename(path))[0].replace(' ', '_') + '_%s.png' % a.focus)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    Image.fromarray(img).save(out)
    print('wrote', out)


if __name__ == '__main__':
    main()
