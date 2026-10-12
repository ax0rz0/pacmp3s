"""Verify the generated BNA outfits (Ethics Assistant looks):  python verify_ethics.py STAGE_DIR OUTFIT.txt [...]
Format, UIDs, watermark; material_3d parts (image url base textures present in STAGE_DIR, created BEFORE anything that uses them by name); entity2 Materials / model2 Material only
name material parts or engine materials (no image urls: those would go through pac's unreliable hidden-browser loader); bones; OBJ sanity."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import ethics_acc as ea
import pac_parse as pp
import pac_write as pw
from ethics_common import Rig

REPO_RAW = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
problems = 0


def bad(m):
    global problems
    problems += 1
    print('  PROBLEM:', m)


def ordered(top):
    """parts in the order pac creates them: top-level keys ascending, children depth first"""
    for k in sorted(top):
        yield from pw.walk([top[k]])


def check_obj(path):
    nv = nvt = nvn = nf = 0
    maxidx = 0
    for line in open(path, encoding='utf-8'):
        if line.startswith('v '):
            nv += 1
        elif line.startswith('vt '):
            nvt += 1
        elif line.startswith('vn '):
            nvn += 1
        elif line.startswith('f '):
            nf += 1
            for tok in line.split()[1:]:
                for i in tok.split('/'):
                    maxidx = max(maxidx, int(i))
    ok = nv > 0 and nv == nvt == nvn and maxidx <= nv and nv <= 24000
    if not ok:
        bad('%s: v=%d vt=%d vn=%d f=%d maxidx=%d' % (os.path.basename(path), nv, nvt, nvn, nf, maxidx))
    return nv, nf


def check_material_use(parts, tag=''):
    """material_3d parts first, every name used later exists; returns the set of asset urls (basetexture) and the number of material parts"""
    seen = {}
    urls = set()
    for p in parts:
        s = p['self']
        c = s['ClassName']
        if c == 'material_3d':
            name = s.get('Name', '')
            if not name or name in seen:
                bad('material_3d name %r empty or duplicated' % name)
            seen[name] = s
            bt = s.get('basetexture', '')
            if not bt.startswith(REPO_RAW):
                bad('material %r basetexture is not a repo url: %r' % (name, bt))
            else:
                urls.add(bt)
            if s.get('MaterialOverride') != 'all':
                bad('material %r MaterialOverride %r (the key must be present: it makes pac match name references)' % (name, s.get('MaterialOverride')))
        elif c == 'entity2':
            for i, m in enumerate(s['Materials'].split(';')):
                if m == '' or m == 'null':
                    continue
                if 'http' in m:
                    bad('entity2 slot %d has an image url (%r): use a material part' % (i + 1, m))
                elif m not in seen:
                    bad('entity2 slot %d names %r, no material part of that name exists before the entity2' % (i + 1, m))
            if s.get('Model'):
                bad('entity2 Model must stay empty (it would change the player model)')
        elif c == 'model2':
            m = s.get('Material', '')
            if 'http' in m:
                bad('model2 %r Material is an image url (%r): use a material part' % (s.get('Name'), m))
            elif m and not m.startswith('models/') and m not in seen:
                bad('model2 %r Material names %r, no material part of that name exists before it' % (s.get('Name'), m))
    return urls, len(seen)


def main():
    stage = sys.argv[1]
    rig = Rig()
    friendly_names = {ea.friendly(n) for n in rig.names}
    for path in sys.argv[2:]:
        print('==', os.path.basename(path))
        raw = open(path, 'rb').read()
        if raw[:3] == b'\xef\xbb\xbf':
            bad('BOM')
        if b'\r' in raw:
            bad('CR')
        text = raw.decode('utf-8')
        if not text.startswith('-- claude skill made by ax0rz0\n\n[1] = {'):
            bad('header')
        t = pp.parse(text)
        parts = list(ordered(t))
        ids = [p['self'].get('UniqueID', '') for p in parts]
        if len(set(ids)) != len(ids) or any((not re.fullmatch(r'[0-9a-f]{64}', u)) or not u.endswith('a0c3f') for u in ids):
            bad('UIDs')
        if t[1]['self'].get('Notes') != 'claude skill made by ax0rz0':
            bad('root Notes')
        classes = {}
        for p in parts:
            classes[p['self']['ClassName']] = classes.get(p['self']['ClassName'], 0) + 1
        print('  parts %d %s' % (len(parts), dict(sorted(classes.items()))))
        urls, n_mat = check_material_use(parts)
        for p in parts:
            s = p['self']
            c = s['ClassName']
            if c in ('model2', 'sprite') and s.get('Bone') not in friendly_names:
                bad('unknown bone %r on %s' % (s.get('Bone'), s.get('Name')))
            if c == 'entity2':
                mats = s['Materials'].split(';')
                if len(mats) != 21:
                    bad('Materials has %d slots, expected 21' % len(mats))
                filled = [(i + 1, m) for i, m in enumerate(mats) if m]
                print('  entity2 Materials: %d slots set: %s' % (len(filled), [i for i, _ in filled]))
                print('  entity2 ModelModifiers: %s' % s['ModelModifiers'])
            if c == 'model2':
                if not s.get('Model', '').endswith('.obj'):
                    bad('model url must end in .obj: %r' % s.get('Model'))
                if s['Model'].startswith(REPO_RAW):
                    urls.add(s['Model'])
        tot_v = tot_f = 0
        total = 0
        for u in sorted(urls):
            rel = u[len(REPO_RAW):]
            f = os.path.join(stage, *rel.split('/'))
            if not os.path.exists(f):
                bad('missing asset ' + rel)
                continue
            total += os.path.getsize(f)
            if rel.endswith('.obj'):
                nv, nf = check_obj(f)
                tot_v += nv
                tot_f += nf
        print('  material parts %d, asset urls %d (%.2f MB to download), obj vertices %d, triangles %d' % (n_mat, len(urls), total / 1e6, tot_v, tot_f))
    print('PROBLEMS: %d' % problems)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
