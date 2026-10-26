import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_ghost as gh
import adv_geom as ag
import adv_scene as asn
import ax_render as axr

t0 = time.time()
sc = asn.Scene()
parts, ctx = gh.build_ghost(sc)
for k, v in parts.items():
    print('%-10s %6d verts %6d tris' % (k, len(v['mesh'].V), len(v['mesh'].F)))
# mirror chain for the right hand
parts['chain_r'] = dict(parts['chain_l'], mesh=ag.mirror_y(parts['chain_l']['mesh']))
body = axr.export_body(sc, skip=('eyeball_l', 'eyeball_r', 'fmouth'))
for it in body:
    it['tex'] = None
    it['color'] = (150, 200, 255)
    it['alpha'] = 0.22
    it['rough'] = 0.5
    it['emissive'] = (0.05, 0.12, 0.2)
items = body + axr.export_parts(parts, 'gh')
print('built %.1fs' % (time.time() - t0))
ax = axr.Ax()
try:
    views = sys.argv[1].split(',') if len(sys.argv) > 1 else ['front', '34', 'back']
    full = axr.render_item_views(ax, items, views=views, size=(440, 840), radius=38.0, fov=22, focus=(0, 0, 36.0), exposure=1.0, key=3.0, ambient=1.2, rim=(0.5, 0.8, 1.0), rim_i=1.5)
    Image.fromarray(full).save('adv/ref/ghost_full.png')
    head = axr.render_item_views(ax, items, views=['front', '34', 'back'], size=(420, 540), radius=10.0, fov=22, exposure=1.0, key=3.0, ambient=1.2, rim=(0.5, 0.8, 1.0), rim_i=1.5)
    Image.fromarray(head).save('adv/ref/ghost_head.png')
    print('done %.1fs' % (time.time() - t0))
finally:
    ax.close()
