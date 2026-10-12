"""Verify 'tech expert bna.txt':  python verify_tech.py NEW.txt ORIGINAL.txt STAGE_DIR
[1] must be the material group (material_3d parts, image-url base textures present in STAGE_DIR), [2..n+1] the user's original groups unchanged apart from UID / Notes and the entity2
Materials (their entries kept, only the BNA slots added, by material part NAME), [n+2] the accessory group; format, UIDs, bones, OBJ sanity, no image urls in Material / Materials."""
import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ethics_acc as ea
import make_tech_outfit as mto
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
    n_orig = len(orig)
    ordered = [p for k in sorted(new) for p in pw.walk([new[k]])]
    ids = [p['self'].get('UniqueID', '') for p in ordered]
    if len(set(ids)) != len(ids) or any((not re.fullmatch(r'[0-9a-f]{64}', u)) or not u.endswith('a0c3f') for u in ids):
        bad('UIDs not unique / not 64 hex ending a0c3f')
    for k in sorted(new):
        if new[k]['self'].get('Notes') != 'claude skill made by ax0rz0':
            bad('top-level [%d] has no watermark Notes' % k)
    classes = {}
    for p in ordered:
        classes[p['self']['ClassName']] = classes.get(p['self']['ClassName'], 0) + 1
    print('  parts %d %s' % (len(ordered), dict(sorted(classes.items()))))
    if len(new) != n_orig + 2:
        bad('expected %d top-level groups, found %d' % (n_orig + 2, len(new)))
    # --- [1] the material group
    mats = {}
    urls = set()
    for p in pw.walk([new[1]]):
        s = p['self']
        if s['ClassName'] == 'group':
            continue
        if s['ClassName'] != 'material_3d':
            bad('group [1] holds a %s' % s['ClassName'])
            continue
        mats[s['Name']] = s
        if s.get('MaterialOverride') != 'all':
            bad('material %r has no MaterialOverride key' % s['Name'])
        if not str(s.get('basetexture', '')).startswith(REPO_RAW):
            bad('material %r basetexture %r is not a repo url' % (s['Name'], s.get('basetexture')))
        else:
            urls.add(s['basetexture'])
    names = mto.material_names()
    for slot, name in names.items():
        if name not in mats:
            bad('no material part %r for slot %d' % (name, slot))
        elif mats[name]['basetexture'] != mto.texture_urls()[slot]:
            bad('material %r points at %r' % (name, mats[name]['basetexture']))
    print('  group [1]: %d material_3d parts (%d body, %d accessory textures)' % (len(mats), len(names), len(mats) - len(names)))
    # --- the user's groups [2..n+1]
    for k in range(1, n_orig + 1):
        if strip(new[k + 1]) != strip(orig[k]):
            bad('original group [%d] changed' % k)
        else:
            print('  original group [%d] (now [%d]) identical apart from UID / Notes / entity2 Materials (%d parts)' % (k, k + 1, sum(1 for _ in pw.walk([new[k + 1]]))))
        for pn, po in zip(pw.walk([new[k + 1]]), pw.walk([orig[k]])):
            if po['self']['ClassName'] != 'entity2':
                continue
            mn = pn['self']['Materials'].split(';')
            mo = po['self']['Materials'].split(';')
            mo += [''] * (len(mn) - len(mo))
            for i, (a, b) in enumerate(zip(mn, mo)):
                slot = i + 1
                if slot in names:
                    if b != '':
                        bad('entity2 slot %d was set in the original (%r) and got replaced' % (slot, b))
                    if a != names[slot]:
                        bad('entity2 slot %d is %r, expected the material part %r' % (slot, a, names[slot]))
                elif a != b:
                    bad('entity2 slot %d changed: %r -> %r' % (slot, b, a))
                if 'http' in a:
                    bad('entity2 slot %d has an image url' % slot)
            print('    entity2 Materials: %d entries, BNA slots %s, original entries kept: %s' % (len(mn), sorted(s for s in names if mn[s - 1] == names[s]), [(i + 1, b) for i, b in enumerate(mo) if b]))
    # --- the accessory group
    rig = Rig(ts.TECH)
    friendly_names = {ea.friendly(n) for n in rig.names}
    for p in pw.walk([new[n_orig + 2]]):
        s = p['self']
        c = s['ClassName']
        if c in ('model2', 'sprite') and s.get('Bone') not in friendly_names:
            bad('unknown bone %r on %s' % (s.get('Bone'), s.get('Name')))
        if c == 'model2':
            if not s.get('Model', '').endswith('.obj'):
                bad('model url must end in .obj: %r' % s.get('Model'))
            else:
                urls.add(s['Model'])
            if abs(s.get('Size', 1.0) - 0.85) > 1e-9:
                bad('accessory Size %r != 0.85' % s.get('Size'))
            m = s.get('Material', '')
            if 'http' in m:
                bad('model2 %r Material is an image url' % s.get('Name'))
            elif not m.startswith('models/') and m not in mats:
                bad('model2 %r Material %r names no material part' % (s.get('Name'), m))
    total = 0
    tot_v = tot_f = 0
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
