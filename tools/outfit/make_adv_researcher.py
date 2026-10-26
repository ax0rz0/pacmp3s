"""Ethics Assistant - Researcher: the small, blend-in outfit.  Like the Sr. Researcher in the lobby screenshot: a white lab coat over dark clothes, and a custom head.

Nothing is modelled here, no glow, no neon: the coat, the shirt and the tie are the Armacham scientist model (models/armacham/scientists/scientists_1.mdl, part of the SCP playermodel pack that the
server's job models come from) bone-merged onto the Ethics Assistant with only its coat / suit_shirt / tiesandties slots drawn; the Ethics Assistant's own head slots and her suit are hidden by the
entity2; the head is the donor package of adv_head_pkg.py (Song So Mi: skin neck + head clipped under the skull + unclipped hair).

    python make_adv_researcher.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adv_head_pkg as hp
import adv_parts as ap
import pac_write as pw

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE_DIR = os.path.join(HERE, 'stage_adv')
OUT_DIR = os.path.join(STAGE_DIR, 'outfits')
FILE = 'ethics asst researcher'
TITLE = 'Ethics Assistant - Researcher'
SCIENTIST = 'models/armacham/scientists/scientists_1.mdl'
# .mdl texture order (1-based): ted_facemap 1, mouth 2, eyeball_r 3, eyeball_l 4, lynch_hands 5, suit_shirt 6, body_scientist 7 (the lab coat), tiesandties 8, scrubs1_sheet 9, stripe 10,
# glassesside_walter 11, glassesfront_walter 12, glasslens 13, glasses_d 14, ted_facemap2 15, ted_facemap3 16
SCIENTIST_SLOTS = 16
SCIENTIST_SHOW = (6, 7, 8)
PLAYER_SUIT = 5                      # entity2 slot 5 = the Ethics Assistant's own suit (jacket and trousers)


def build(write=True):
    ap.reset_uids()
    st = ap.Stage(STAGE_DIR, 'hd')
    mats, head_parts = hp.head_parts(st)
    ent = ap.entity2('Ethics Assistant body (head + suit hidden)', materials=hp.head_materials(extra_null=(PLAYER_SUIT,)))
    s = ['null'] * SCIENTIST_SLOTS
    for i in SCIENTIST_SHOW:
        s[i - 1] = ''
    coat = ap.model('researcher coat + clothes', SCIENTIST, ap.bone_name('Head1'), color=(1, 1, 1), material='', bonemerge=True, extra={'Materials': ';'.join(s)})
    coat['self'].pop('ForceObjUrl', None)
    coat['self'].pop('Material', None)
    head = ap.group('custom head', [ap.group('materials', mats, expand=False)] + head_parts)
    root = ap.group(TITLE, [ent, coat, head], notes=ap.WM)
    text, tree = ap.finalize(root, 'ethics_adv_researcher')
    errs, warns, counts = ap.validate(tree, TITLE)
    errs += ap.check_text(text)
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, FILE + '.txt'), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, tree, st, errs, counts


if __name__ == '__main__':
    text, tree, st, errs, counts = build()
    print('%d bytes, %d parts' % (len(text), sum(1 for _ in pw.walk(tree))))
    for fn, (nv, nt, sz) in st.files.items():
        print('  %-18s %6d verts %6d tris %8d bytes' % (fn, nv, nt, sz))
    if errs:
        print('ERRORS:', errs)
        sys.exit(1)
