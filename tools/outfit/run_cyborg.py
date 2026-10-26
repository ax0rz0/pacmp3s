import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_cyborg as cb
import adv_geom as ag
import adv_scene as asn
import ax_render as axr

t0 = time.time()
sc = asn.Scene()
parts, ctx = cb.build_cyborg(sc)
for k, v in parts.items():
    print('%-14s %6d verts %6d tris' % (k, len(v['mesh'].V), len(v['mesh'].F)))
body = axr.export_body(sc)
items = body + axr.export_parts(parts, 'cb')
print('built %.1fs' % (time.time() - t0))
ax = axr.Ax()
try:
    kw = dict(exposure=1.0, key=3.8, ambient=1.7, rim=(1.0, 0.6, 0.3), rim_i=1.4)
    head = axr.render_item_views(ax, items, views=['front', '34', 'left'], size=(420, 540), radius=9.5, fov=22, **kw)
    Image.fromarray(head).save('adv/ref/cb_head.png')
    full = axr.render_item_views(ax, items, views=['front', '34', 'back'], size=(420, 840), radius=38.0, fov=22, focus=(0, 0, 36.0), **kw)
    Image.fromarray(full).save('adv/ref/cb_full.png')
    arm = axr.render_item_views(ax, items, views=['front', '34', 'top'], size=(420, 540), radius=11.5, fov=24, focus=(-1.5, 11.0, 49.0), **kw)
    Image.fromarray(arm).save('adv/ref/cb_arm.png')
    print('done %.1fs' % (time.time() - t0))
finally:
    ax.close()
