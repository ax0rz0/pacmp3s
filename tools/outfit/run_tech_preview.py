import colorsys
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw

import preview as pv
import tech_scene as ts

os.makedirs('tech/ref', exist_ok=True)
t0 = time.time()
te = ts.TechExpert()
print('loaded %.1fs; textures decoded: %s' % (time.time() - t0, sorted(te.tex)))
for i, n in enumerate(te.mesh.textures):
    print('  slot %2d %-34s %s' % (i + 1, n, 'tex %s' % (te.tex[n].shape,) if n in te.tex else '-'))

mode = sys.argv[1] if len(sys.argv) > 1 else 'orig'
views = sys.argv[2].split(',') if len(sys.argv) > 2 else ['front', '34', 'back']
if mode == 'orig':
    scn, tl = te.soup()
    out = 'tech/ref/tech_orig.png'
elif mode == 'slots':
    cols = {}
    for i in range(len(te.mesh.textures)):
        h = (i * 0.61803) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.95)
        cols[i] = (r * 255, g * 255, b * 255)
    scn, tl = te.soup(slot_colors=cols)
    out = 'tech/ref/tech_slots.png'
    leg = Image.new('RGB', (230, 24 * len(cols) + 8), (30, 33, 40))
    d = ImageDraw.Draw(leg)
    for i, c in cols.items():
        d.rectangle([6, 8 + 24 * i, 26, 26 + 24 * i], fill=tuple(int(x) for x in c))
        d.text((34, 10 + 24 * i), '%2d %s' % (i + 1, te.mesh.textures[i][:24]), fill=(235, 235, 235))
    leg.save('tech/ref/tech_slots_legend.png')
elif mode == 'bna':
    import tech_paint as tp
    tdir = os.path.join('stage_bna', 'tex', 'bna')
    over = {}
    for slot, fn in {**tp.SLOT_FILES, 14: 'tech_stripes'}.items():
        fn = fn + '.png'
        over[te.mesh.textures[slot - 1]] = np.asarray(Image.open(os.path.join(tdir, fn)).convert('RGB'))
    scn, tl = te.soup(textures=over)
    out = 'tech/ref/tech_bna.png'
else:
    raise SystemExit('mode?')
ims = [pv.render(scn, tl, v, height=760) for v in views]
Image.fromarray(np.concatenate(ims, axis=1)).save(out)
print('rendered %s %.1fs' % (out, time.time() - t0))
