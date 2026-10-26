import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_seraph as sr
import adv_geom as ag
import adv_scene as asn
import ax_render as axr

t0 = time.time()
sc = asn.Scene()
parts, ctx = sr.build_seraph(sc)
for k, v in parts.items():
    print('%-14s %6d verts %6d tris' % (k, len(v['mesh'].V), len(v['mesh'].F)))
for k in ('wing', 'wing_glow', 'shoulder', 'shoulder_glow', 'holo'):
    parts[k + '_r'] = dict(parts[k], mesh=ag.mirror_y(parts[k]['mesh']))
body = axr.export_body(sc)
items = body + axr.export_parts(parts, 'sr')
ax = axr.Ax()
try:
    kw = dict(exposure=1.0, key=3.8, ambient=1.6, rim=(0.5, 0.8, 1.0), rim_i=1.6)
    full = axr.render_item_views(ax, items, views=['front', '34', 'back'], size=(460, 840), radius=44.0, fov=22, focus=(-1.0, 0, 40.0), **kw)
    Image.fromarray(full).save('adv/ref/sr_full.png')
    head = axr.render_item_views(ax, items, views=['front', '34'], size=(420, 540), radius=9.5, fov=22, **kw)
    Image.fromarray(head).save('adv/ref/sr_head.png')
    print('done %.1fs' % (time.time() - t0))
finally:
    ax.close()
