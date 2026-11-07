"""eca main 4 = the user's eca main 3 (text untouched) + two new roots: [7] the Xbox pac and [8] the guitar pac.  Never modifies eca main 3."""
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import outfit_lib as ol
import xbox_outfit as xo
import guitar_outfit as go
import guitar_build as gb

PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'
SRC = os.path.join(PAC_DIR, 'eca main 3.txt')
DST = os.path.join(PAC_DIR, 'eca main 4.txt')


def build_text():
    t3 = open(SRC, encoding='utf-8', newline='').read()
    assert '\r' not in t3 and t3.endswith('},\n'), 'eca main 3 does not end like a multi-root file'
    assert re.findall(r'(?m)^\[(\d+)\] = \{$', t3) == ['1', '2', '3', '4', '5', '6'], 'unexpected root numbering'
    G, jsA, infoA, jsB, infoB, expr, terms, beats = gb.build(go.FAMILY)
    x_children = ol.indent_block(xo.build_children(xo.SLUG, 1), 1)
    g_children = ol.indent_block(go.build_children(G, expr, go.SLUG, 1), 1)
    r7 = ol.root_block(7, xo.SLUG, 'xbox: turn on the console and watch it boot (pac_event xbox 2)', x_children)
    r8 = ol.root_block(8, go.SLUG, 'guitar: play Brain Damage (instrumental) on a Martin D-45 (pac_event guitar 2)', g_children)
    return t3, t3 + r7 + r8


def local_path(url):
    for base in (ol.RAW, ol.GH):
        if url.startswith(base):
            return os.path.join(ol.REPO, url[len(base):].replace('/', os.sep))
    return None


def check(path):
    pp = ol.pp
    tree = pp.load(path)
    roots = sorted(k for k in tree if isinstance(k, int))
    print('roots:', roots)
    ids = []
    cmds = {}
    urls = []
    per_root = {}
    for r in roots:
        n = 0
        for depth, s, node in pp.walk(tree[r]):
            n += 1
            ids.append(s.get('UniqueID'))
            if s.get('ClassName') == 'event' and s.get('Event') == 'command':
                cmds.setdefault(s.get('Arguments'), []).append(r)
            for key in ('URL', 'Path', 'Model', 'basetexture'):
                v = s.get(key)
                if isinstance(v, str) and v.startswith('http'):
                    urls.append((r, s.get('ClassName'), key, v))
        per_root[r] = n
    print('parts per root:', per_root, 'total', sum(per_root.values()))
    dup = {i for i in ids if ids.count(i) > 1}
    print('UniqueIDs: %d, duplicates: %s' % (len(ids), sorted(dup)[:5] if dup else 'none'))
    clash = {c: rs for c, rs in cmds.items() if len(rs) > 1}
    print('command events: %d, same command in several roots: %s' % (len(cmds), clash if clash else 'none'))
    print('new commands:', {c: r for c, r in cmds.items() if c in ('xbox', 'guitar')})
    missing = []
    for r, cls, key, url in urls:
        if r < 7:
            continue
        p = local_path(url)
        ok = p is not None and os.path.exists(p)
        print('  root %d %-16s %-11s -> %s %s' % (r, cls, key, url.split('main/')[-1], ('%d bytes' % os.path.getsize(p)) if ok else 'MISSING'))
        if not ok:
            missing.append(url)
    return not dup and not missing and not clash


def main():
    t3, out = build_text()
    assert out.startswith(t3)
    with open(DST, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('wrote', DST, len(out), 'bytes (eca main 3 was %d); added %d bytes' % (len(t3), len(out) - len(t3)))
    probs = []
    if out.count('{') != out.count('}'):
        probs.append('unbalanced braces')
    if '\r' in out:
        probs.append('CR')
    print('text checks:', probs or 'OK')
    ok = check(DST)
    print('semantic checks:', 'OK' if ok else 'PROBLEMS')
    # eca main 3 must be byte-identical to before
    import hashlib
    print('eca main 3 sha256 (unchanged, read-only here): %s' % hashlib.sha256(open(SRC, 'rb').read()).hexdigest()[:16])


if __name__ == '__main__':
    main()
