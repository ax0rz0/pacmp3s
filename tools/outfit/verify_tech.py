"""Verify 'tech expert bna.txt':  python verify_tech.py NEW.txt ORIGINAL.txt STAGE_DIR
Format (no BOM / CR, watermark, UIDs), the user's original groups unchanged apart from UID / Notes and the entity2 Materials (their entries kept, only the BNA slots added),
every accessory bone a valid pac bone name of the rig, every asset url present in STAGE_DIR, OBJ sanity."""
import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ethics_acc as ea
import pac_parse as pp
import pac_write as pw
import tech_paint as tp
import tech_scene as ts
from ethics_common import Rig

REPO_RAW = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
problems = []


def bad(m):
    problems.append(m)
    print('  PROBLEM:', m)


def strip(p):
    p = copy.deepcopy(p)
    for q in pw.walk([p]):
        for k in list(q['self']):
            if k == 'UniqueID' or k.endswith('UID') or k == 'Notes' or (k == 'Materials' and q['self'].get('ClassName') == 'entity2'):
                q['self'].pop(k)
    return p


def check_obj(path):
    nv = nvt = nvn = nf = maxidx = 0
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
    if not (nv > 0 and nv == nvt == nvn and maxidx <= nv and nv <= 24000):
        bad('%s: v=%d vt=%d vn=%d f=%d maxidx=%d' % (os.path.basename(path), nv, nvt, nvn, nf, maxidx))
    return nv, nf


def main():
    new_path, orig_path, stage = sys.argv[1:4]
    raw = open(new_path, 'rb').read()
    if raw[:3] == b'\xef\xbb\xbf':
        bad('BOM')
    if b'\r' in raw:
        bad('CR characters')
    text = raw.decode('utf-8')
    if not text.startswith('-- claude skill made by ax0rz0\n\n[1] = {') or not text.endswith('\n'):
        bad('header / trailing newline')
    new = pp.parse(text)
    orig = pp.load(orig_path)
    parts = list(pw.walk(new))
    ids = [p['self'].get('UniqueID', '') for p in parts]
    if len(set(ids)) != len(ids) or any((not re.fullmatch(r'[0-9a-f]{64}', u)) or not u.endswith('a0c3f') for u in ids):
        bad('UIDs not unique / not 64 hex ending a0c3f')
    for k in sorted(new):
        if new[k]['self'].get('Notes') != 'claude skill made by ax0rz0':
            bad('top-level [%d] has no watermark Notes' % k)
    classes = {}
    for p in parts:
        classes[p['self']['ClassName']] = classes.get(p['self']['ClassName'], 0) + 1
    print('  parts %d %s' % (len(parts), dict(sorted(classes.items()))))
    n_orig = len(orig)
    if len(new) != n_orig + 1:
        bad('expected %d top-level groups, found %d' % (n_orig + 1, len(new)))
    # --- the user's groups
    bna_slots = set(tp.SLOTS)
    for k in range(1, n_orig + 1):
        if strip(new[k]) != strip(orig[k]):
            bad('original group [%d] changed' % k)
        else:
            print('  original group [%d] identical apart from UID / Notes / entity2 Materials (%d parts)' % (k, sum(1 for _ in pw.walk([new[k]]))))
        for pn, po in zip(pw.walk([new[k]]), pw.walk([orig[k]])):
            if po['self']['ClassName'] != 'entity2':
                continue
            mn = pn['self']['Materials'].split(';')
            mo = po['self']['Materials'].split(';')
            mo += [''] * (len(mn) - len(mo))
            for i, (a, b) in enumerate(zip(mn, mo)):
                if (i + 1) in bna_slots:
                    if b != '':
                        bad('entity2 slot %d was set in the original (%r) and got replaced' % (i + 1, b))
                    if not a.startswith(REPO_RAW + 'tex/bna/' + tp.slot_filename(i + 1).split('.')[0]):
                        bad('entity2 slot %d is %r' % (i + 1, a))
                    if (i + 1 in (5, 6)) != a.endswith(' noclamp'):
                        bad('entity2 slot %d noclamp flag wrong: %r' % (i + 1, a))
                elif a != b:
                    bad('entity2 slot %d changed: %r -> %r' % (i + 1, b, a))
            print('    entity2 Materials: %d entries, BNA slots %s, original entries kept: %s' % (len(mn), sorted(i + 1 for i, a in enumerate(mn) if a.startswith('http')), [(i + 1, b) for i, b in enumerate(mo) if b]))
    # --- the accessory group
    rig = Rig(ts.TECH)
    friendly_names = {ea.friendly(n) for n in rig.names}
    urls = set()
    tot_v = tot_f = 0
    for p in pw.walk([new[n_orig + 1]]):
        s = p['self']
        c = s['ClassName']
        if c in ('model2', 'sprite') and s.get('Bone') not in friendly_names:
            bad('unknown bone %r on %s' % (s.get('Bone'), s.get('Name')))
        if c == 'model2':
            if not s.get('Model', '').endswith('.obj'):
                bad('model url must end in .obj: %r' % s.get('Model'))
            if abs(s.get('Size', 1.0) - 0.85) > 1e-9:
                bad('accessory Size %r != 0.85' % s.get('Size'))
        for key in ('Model', 'Material', 'Materials'):
            v = s.get(key)
            if isinstance(v, str):
                for piece in v.split(';'):
                    piece = piece.replace(' noclamp', '').strip()
                    if piece.startswith(REPO_RAW):
                        urls.add(piece)
    for p in pw.walk(new):                                   # body texture urls of the entity2 parts too
        v = p['self'].get('Materials')
        if p['self']['ClassName'] == 'entity2' and isinstance(v, str):
            for piece in v.split(';'):
                piece = piece.replace(' noclamp', '').strip()
                if piece.startswith(REPO_RAW):
                    urls.add(piece)
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
    print('  asset urls %d (%.2f MB to download), accessory obj vertices %d, triangles %d' % (len(urls), total / 1e6, tot_v, tot_f))
    print('PROBLEMS: %d' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
