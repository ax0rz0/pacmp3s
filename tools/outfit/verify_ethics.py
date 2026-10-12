"""Verify the generated BNA outfits: python verify_ethics.py STAGE_DIR OUTFIT.txt [...]"""
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
        parts = list(pw.walk(t))
        ids = [p['self'].get('UniqueID', '') for p in parts]
        if len(set(ids)) != len(ids) or any((not re.fullmatch(r'[0-9a-f]{64}', u)) or not u.endswith('a0c3f') for u in ids):
            bad('UIDs')
        if t[1]['self'].get('Notes') != 'claude skill made by ax0rz0':
            bad('root Notes')
        classes = {}
        for p in parts:
            classes[p['self']['ClassName']] = classes.get(p['self']['ClassName'], 0) + 1
        print('  parts %d %s' % (len(parts), dict(sorted(classes.items()))))
        urls = set()
        tot_v = tot_f = 0
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
                if s.get('Model'):
                    bad('entity2 Model must stay empty (it would change the player model)')
            for key in ('Model', 'Material', 'Materials'):
                v = s.get(key)
                if isinstance(v, str):
                    for piece in v.split(';'):
                        piece = piece.replace(' noclamp', '').strip()
                        if piece.startswith(REPO_RAW):
                            urls.add(piece)
            if c == 'model2' and not (s.get('Model', '').endswith('.obj')):
                bad('model url must end in .obj: %r' % s.get('Model'))
        for u in sorted(urls):
            rel = u[len(REPO_RAW):]
            f = os.path.join(stage, *rel.split('/'))
            if not os.path.exists(f):
                bad('missing asset ' + rel)
            elif rel.endswith('.obj'):
                nv, nf = check_obj(f)
                tot_v += nv
                tot_f += nf
        sizes = sum(os.path.getsize(os.path.join(stage, *u[len(REPO_RAW):].split('/'))) for u in urls if os.path.exists(os.path.join(stage, *u[len(REPO_RAW):].split('/'))))
        print('  asset urls %d (%.2f MB to download), obj vertices %d, triangles %d' % (len(urls), sizes / 1e6, tot_v, tot_f))
    print('PROBLEMS: %d' % problems)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
