import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_oni2 as oni
import adv_scene as asn
import ax_render as axr

t0 = time.time()
sc = asn.Scene()
parts, ctx = oni.build_oni2(sc)
for n, p in parts.items():
    print('%-10s %6d verts %6d tris' % (n, len(p['mesh'].V), len(p['mesh'].F)))
jaw_deg = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
if jaw_deg:
    for k in ('jaw', 'jaw_black', 'jaw_steel', 'jaw_glow'):
        parts[k]['mesh'] = oni.rotate_about_y(parts[k]['mesh'], oni.JAW_PIVOT, jaw_deg)
body = axr.export_body(sc)
items = body + axr.export_parts(parts, 'oni2')
print('built %.1fs' % (time.time() - t0))
ax = axr.Ax()
try:
    views = sys.argv[1].split(',') if len(sys.argv) > 1 else ['front', '34']
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    img = axr.render_item_views(ax, items, views=views, size=(size, int(size * 1.25)), radius=8.6, fov=22, exposure=0.8)
    Image.fromarray(img).save('adv/ref/oni2.png')
    print('saved', img.shape, '%.1fs' % (time.time() - t0))
finally:
    ax.close()
