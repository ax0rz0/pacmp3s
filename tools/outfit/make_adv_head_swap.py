"""Head replacement only, for the Ethics Assistant (femsuit_04): the donor head package of adv_head_pkg.py (Song So Mi, workshop 3283215678) without anything else.

  * `ethics asst custom head`  : entity2 (hides the player's head slots) + the package, nothing else.
  * `eca cool 2 custom head`   : the user's own `eca cool 2.txt` with the package added.  Done as a TEXT edit so every other byte of their file stays: the entity2 Materials string gets
                                 `null` in the four head slots and one new group (`custom head`) is appended to the root group.  The original file is never touched.

    python make_adv_head_swap.py [path to the user's outfit]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adv_head_pkg as hp
import adv_parts as ap
import pac_parse as pp
import pac_write as pw

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE_DIR = os.path.join(HERE, 'stage_adv')
OUT_DIR = os.path.join(STAGE_DIR, 'outfits')
PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'


def head_group(stage):
    mats, parts = hp.head_parts(stage)
    return ap.group('custom head', [ap.group('materials', mats, expand=False)] + parts)


def build_head_only(write=True):
    ap.reset_uids()
    st = ap.Stage(STAGE_DIR, 'hd')
    ent = ap.entity2('Ethics Assistant body (head hidden)', materials=hp.head_materials())
    root = ap.group('Ethics Assistant - Custom Head (Song So Mi)', [ent, head_group(st)], notes=ap.WM)
    text, tree = ap.finalize(root, 'ethics_adv_head_only')
    errs, warns, counts = ap.validate(tree, 'custom head only')
    errs += ap.check_text(text)
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, 'ethics asst custom head.txt'), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, errs, counts, st


def add_head_to_user_outfit(src_path, out_name, slug):
    """text edit of an editor-saved outfit: head slots -> null in the (single) entity2 Materials, the head package appended to the root group"""
    raw = open(src_path, encoding='utf-8', newline='').read()
    parts = pp.load(src_path)
    root = parts[1]
    ents = [p for p in pw.walk(parts) if p['self'].get('ClassName') == 'entity2']
    if len(ents) != 1:
        raise SystemExit('expected exactly one entity2 in %s, found %d' % (src_path, len(ents)))
    old_mats = ents[0]['self']['Materials']
    entries = old_mats.split(';')
    entries += [''] * (hp.N_SLOTS - len(entries))
    for i in hp.HEAD_SLOTS_NULL:
        entries[i - 1] = 'null'
    new_mats = ';'.join(entries)
    old_line = '["Materials"] = "%s",' % old_mats
    new_line = '["Materials"] = "%s",' % new_mats
    if raw.count(old_line) != 1:
        raise SystemExit('Materials line not found exactly once')
    text = raw.replace(old_line, new_line)

    ap.reset_uids()
    st = ap.Stage(STAGE_DIR, 'hd')
    grp = head_group(st)
    used = {p['self'].get('UniqueID') for p in pw.walk(parts)}
    names = {p['self'].get('Name') for p in pw.walk(parts)}
    for i, p in enumerate(pw.walk([grp])):
        p['self']['UniqueID'] = pw.new_uid(slug, 'head%d' % i)
        assert p['self']['UniqueID'] not in used
        if p['self'].get('ClassName', '').startswith('material_') and p['self'].get('Name') in names:
            raise SystemExit('material name %r already used in the outfit' % p['self'].get('Name'))
    n_kids = len(root['children'])
    block = '\t\t[%d] = ' % (n_kids + 1) + pw.dump_part(grp, 2).lstrip('\t')
    boundary = '\t},\n\t["self"] = {\n'
    i = text.find(boundary)
    if i < 0:
        raise SystemExit('root children boundary not found')
    text = text[:i] + block + text[i:]
    same = text.replace(block, '', 1).replace(new_line, old_line, 1) == raw          # only the Materials line and the appended block differ from the user's file
    text = '-- %s\n\n' % ap.WM + text
    out = os.path.join(OUT_DIR, out_name)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    return text, raw, out, same, st


if __name__ == '__main__':
    t, errs, counts, st = build_head_only()
    print('ethics asst custom head.txt: %d bytes' % len(t), {k: v for k, v in counts.items() if v})
    for fn, (nv, nt, sz) in st.files.items():
        print('  %-18s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS', errs)
        sys.exit(1)
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PAC_DIR, 'eca cool 2.txt')
    text, raw, out, same, st = add_head_to_user_outfit(src, 'eca cool 2 custom head.txt', 'eca_cool_2_head')
    print('wrote', out, len(text), 'bytes (source %d)' % len(raw))
    print('everything else byte-identical to the source:', same)
    for e in ap.check_text(text):
        print('CHECK', e)
