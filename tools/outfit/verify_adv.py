"""Checks of the advanced outfits: python verify_adv.py [STAGE_DIR]
  * every outfit parses and re-dumps byte-identically, no banned part class, every model url points at a staged OBJ of the same name
  * every material name used by a model2 / entity2 is a material part of the same outfit (or a stock path / null)
  * every OBJ: indices in range, <= 24000 vertices, finite numbers, unit-ish normals, sane extent
  * prints the console commands (proxy names) each outfit listens to
"""
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_parts as ap
import pac_parse
import pac_write as pw

stage = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_adv')
out_dir = os.path.join(stage, 'outfits')
obj_dir = os.path.join(stage, 'obj', 'adv')
tex_dir = os.path.join(stage, 'tex', 'adv')
used_tex = set()
errors = []


def err(msg):
    errors.append(msg)
    print('  ERROR', msg)


used_files = set()
for fn in sorted(os.listdir(out_dir)):
    path = os.path.join(out_dir, fn)
    raw = open(path, encoding='utf-8', newline='').read()
    parts = pac_parse.load(path)
    if pw.dump(parts, watermark=ap.WM) != raw and not fn.startswith('eca '):          # `eca ...` files are editor saves of the user's outfit (own key order) plus an appended block
        err('%s: re-dump differs' % fn)
    for e in ap.check_text(raw):
        err('%s: %s' % (fn, e))
    names = {p['self'].get('Name') for p in pw.walk(parts) if p['self'].get('ClassName', '').startswith('material_')}
    classes = {}
    cmds = set()
    for p in pw.walk(parts):
        s = p['self']
        cls = s.get('ClassName')
        classes[cls] = classes.get(cls, 0) + 1
        if cls in ap.BANNED:
            err('%s: banned class %s' % (fn, cls))
        if cls == 'model2':
            m = s.get('Model', '')
            if m.startswith('http'):
                base = m.rsplit('/', 1)[-1]
                used_files.add(base)
                if not os.path.exists(os.path.join(obj_dir, base)):
                    err('%s: model url %s has no staged file' % (fn, base))
                if not m.startswith(ap.REPO_RAW + 'obj/adv/'):
                    err('%s: unexpected url %s' % (fn, m))
            mat = s.get('Material', '')
            if mat and '/' not in mat and mat not in names:
                err('%s: model2 %s uses unknown material %r' % (fn, s.get('Name'), mat))
            for entry in (s.get('Materials') or '').split(';'):
                if entry and entry != 'null' and '/' not in entry and entry not in names:
                    err('%s: model2 %s Materials entry %r' % (fn, s.get('Name'), entry))
        if cls == 'entity2':
            for entry in (s.get('Materials') or '').split(';'):
                if entry and entry != 'null' and '/' not in entry and entry not in names:
                    err('%s: entity2 Materials entry %r is no material part' % (fn, entry))
        if cls == 'proxy':
            for c in re.findall(r'command\("([^"]+)"\)', s.get('Expression', '')):
                cmds.add(c)
        if cls == 'material_3d':
            bt = s.get('basetexture', '')
            if bt.startswith('http'):
                base = bt.rsplit('/', 1)[-1]
                used_tex.add(base)
                if not bt.startswith(ap.REPO_RAW + 'tex/adv/'):
                    err('%s: unexpected texture url %s' % (fn, bt))
                elif not os.path.exists(os.path.join(tex_dir, base)):
                    err('%s: texture url %s has no staged file' % (fn, base))
                elif os.path.getsize(os.path.join(tex_dir, base)) > 1024 * 1024:
                    err('%s: texture %s is over 1 MB' % (fn, base))
    print('%-42s %6d bytes  parts %3d  commands %s' % (fn, len(raw), sum(classes.values()), sorted(cmds)))

print('\nOBJ files: %d staged, %d referenced' % (len(os.listdir(obj_dir)), len(used_files)))
uv_info = []
for fn in sorted(os.listdir(obj_dir)):
    if fn not in used_files:
        print('  note: %s is not referenced by any outfit' % fn)
    V, VT, VN, F = [], [], [], []
    for line in open(os.path.join(obj_dir, fn), encoding='utf-8'):
        if line.startswith('v '):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('vt '):
            VT.append([float(x) for x in line.split()[1:3]])
        elif line.startswith('vn '):
            VN.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('f '):
            corners = [[int(i) for i in tok.split('/')] for tok in line.split()[1:]]
            for i in range(1, len(corners) - 1):                  # pac fans a polygon from its first corner
                F.append([corners[0], corners[i], corners[i + 1]])
    V, VN = np.array(V), np.array(VN)
    if len(V) > 24000:
        err('%s: %d vertices' % (fn, len(V)))
    if not np.isfinite(V).all() or not np.isfinite(VN).all():
        err('%s: non finite numbers' % fn)
    Fa = np.array(F)
    if Fa.min() < 1 or Fa[:, :, 0].max() > len(V) or Fa[:, :, 1].max() > len(VT) or Fa[:, :, 2].max() > len(VN):
        err('%s: face index out of range' % fn)
    nl = np.linalg.norm(VN, axis=1)
    if nl.min() < 0.9 or nl.max() > 1.1:
        err('%s: normals not unit length (%.2f..%.2f)' % (fn, nl.min(), nl.max()))
    ext = np.ptp(V, axis=0)
    if ext.max() > 120:
        err('%s: extent %s' % (fn, np.round(ext, 1)))
    if os.path.getsize(os.path.join(obj_dir, fn)) > 1024 * 1024:
        msg = '%s: %d bytes (over 1 MiB; a player with pac_webcontent_limit 1024 would not download it)' % (fn, os.path.getsize(os.path.join(obj_dir, fn)))
        if fn.startswith('hd_'):
            err(msg)
        else:
            print('  note:', msg)
    if fn.startswith('hd_') and len(VT) and (np.array(VT).min() < 0 or np.array(VT).max() >= 1.0):          # the textured head assets; the other obj parts are flat coloured, their uvs are unused
        err('%s: texture coordinates outside [0, 1) (pac wraps them per vertex)' % fn)
    if len(VT):
        # urlobj builds tangents per triangle with r = 1 / (s1 t2 - s2 t1): a triangle whose uvs are collinear gets infinite / NaN tangents.  The textured head assets must have none
        # (the first neck of the head package had 91 % of its triangles like that and rendered black with a grid of tan squares in game); the flat coloured parts are listed for information.
        VTa = np.array(VT)
        ui = Fa[:, :, 1] - 1
        uu, vv = VTa[ui, 0] % 1.0, (1.0 - VTa[ui, 1]) % 1.0
        det = (uu[:, 1] - uu[:, 0]) * (vv[:, 2] - vv[:, 0]) - (uu[:, 2] - uu[:, 0]) * (vv[:, 1] - vv[:, 0])
        n_bad = int((np.abs(det) < 1e-10).sum())
        if n_bad and fn.startswith('hd_'):
            err('%s: %d of %d triangles have collinear uvs (NaN tangents in pac)' % (fn, n_bad, len(Fa)))
        elif n_bad:
            uv_info.append((fn, n_bad, len(Fa)))

if os.path.isdir(tex_dir):
    print('\ntextures: %d staged, %d referenced' % (len(os.listdir(tex_dir)), len(used_tex)))
    for fn in sorted(os.listdir(tex_dir)):
        print('  %-18s %8d bytes%s' % (fn, os.path.getsize(os.path.join(tex_dir, fn)), '' if fn in used_tex else '   (not referenced by any outfit)'))
if uv_info:
    print('\nnote: flat coloured parts with collinear-uv triangles (harmless for untextured materials as far as known): %s' % ', '.join('%s %d/%d' % t for t in uv_info[:6]) + (' ...' if len(uv_info) > 6 else ''))
print('\n%d errors' % len(errors))
sys.exit(1 if errors else 0)
