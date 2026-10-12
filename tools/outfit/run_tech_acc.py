"""python run_tech_acc.py MODE FOCUS [views]   MODE: bind | game   FOCUS: full | head | arm | pack | chest"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

import tech_acc as ta
import tech_deform as td
import tech_preview as tpv
import tech_scene as ts

OUTFIT = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3\tech expert.txt'
mode = sys.argv[1] if len(sys.argv) > 1 else 'bind'
focus_name = sys.argv[2] if len(sys.argv) > 2 else 'full'
t0 = time.time()
te = ts.TechExpert()
scales = td.bone_scales_from_outfit(OUTFIT, te.rig)
drig = td.DeformedRig(ts.TECH, scales)
acc, spr = ta.build_tech(te)
print('built %d accessories, %d sprites (%.1fs)' % (len(acc), len(spr), time.time() - t0))
for a in acc:
    print('   %-14s bone %-12s verts %5d tris %5d%s' % (a.name, a.bone.split('_', 1)[-1], len(a.mesh.V), len(a.mesh.F), '  texture' if a.material == 'texture' else ''))
tex = tpv.bna_textures(te)
scene, tl = tpv.full_scene(te, tex, acc, spr, drig if mode == 'game' else None)
FOCI = {'full': (None, ['front', '34', 'back']),
        'head': (lambda p: p[:, 2] > 62.5, ['front', '34', 'left']),
        'arm': (lambda p: (p[:, 1] > 8) & (p[:, 2] < 52) & (p[:, 2] > 36), ['front', 'left', '34']),
        'pack': (lambda p: (p[:, 0] < -4) & (p[:, 2] > 36), ['back', '34', 'left']),
        'chest': (lambda p: (p[:, 2] > 44) & (p[:, 2] < 64) & (np.abs(p[:, 1]) < 10) & (p[:, 0] > -4), ['front', '34', 'left'])}
sel, views = FOCI[focus_name]
if len(sys.argv) > 3:
    views = sys.argv[3].split(',')
height = int(sys.argv[4]) if len(sys.argv) > 4 else (720 if focus_name == 'full' else 640)
im = tpv.render_views(scene, tl, views, height=height, focus=sel)
out = 'tech/ref/acc_%s_%s.png' % (mode, focus_name)
Image.fromarray(im).save(out)
print('rendered %s (%.1fs)' % (out, time.time() - t0))
