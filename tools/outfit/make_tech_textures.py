"""python make_tech_textures.py [OUT_DIR]: write the BNA tech expert textures (stage_bna/tex/bna/tech_*)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import tech_paint as tp
import tech_scene as ts
from mdl_mesh import ModelMesh

STAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_bna')


def originals():
    m = ModelMesh(ts.TECH)
    return {slot: ts.original_texture(m.textures[slot - 1]) for slot in tp.SLOT_FILES}, m


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(STAGE, 'tex', 'bna')
    orig, m = originals()
    files = tp.make_all(out, orig)
    tot = 0
    for slot in sorted(files):
        p = os.path.join(out, files[slot])
        tot += os.path.getsize(p)
        print('slot %2d %-30s -> %-18s %7d bytes' % (slot, m.textures[slot - 1], files[slot], os.path.getsize(p)))
    print('total %.2f MB' % (tot / 1e6))
