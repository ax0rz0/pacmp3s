import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_net_arms as arms
import adv_geom as ag
import adv_scene as asn
import ax_render as axr

t0 = time.time()
sc = asn.Scene()
m, ctx = arms.build_arm(sc)
parts = {}
for k, v in m.items():
    col = arms.GLOW if k.startswith('glow') else arms.DARK
    parts[k] = dict(mesh=v, color=col, nolight=k.startswith('glow'), rough=0.35, metal=0.4, smooth=40)
    parts[k + '_r'] = dict(mesh=ag.mirror_y(v), color=col, nolight=k.startswith('glow'), rough=0.35, metal=0.4, smooth=40)
    print('%-10s %6d verts %6d tris' % (k, len(v.V), len(v.F)))
body = axr.export_body(sc)
# glove material: black body hands (slot 'citizen_sheet') for the preview
for it in body:
    if it['name'] in ('body_citizen_sheet', 'body_handfemale'):
        it['tex'] = None
        it['color'] = (14, 14, 18)
        it['rough'] = 0.3
items = body + axr.export_parts(parts, 'netarm')
ax = axr.Ax()
try:
    imgs = []
    for v in ('front', '34', 'top', 'low'):
        imgs.append(axr.render_item_views(ax, items, views=[v], size=(420, 520), radius=8.5, fov=24, focus=(-1.6, 15.5, 43.0), exposure=1.0, key=3.8, ambient=1.5, rim=(0.8, 0.5, 0.9), rim_i=1.6))
    Image.fromarray(np.concatenate(imgs, axis=1)).save('adv/ref/net_arm.png')
    full = axr.render_item_views(ax, items, views=['front', '34'], size=(520, 800), radius=36.0, fov=22, focus=(0, 0, 40.0), exposure=1.0, key=3.8, ambient=1.5)
    Image.fromarray(full).save('adv/ref/net_arm_full.png')
    print('done %.1fs' % (time.time() - t0))
finally:
    ax.close()
