import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_net as net
import adv_scene as asn
import ax_render as axr

t0 = time.time()
sc = asn.Scene()
parts, ctx = net.build_head(sc)
extra = {}
if os.path.exists('adv_net_hair.py'):
    import adv_net_hair as hair
    hp, hctx = hair.build_hair(sc, ctx)
    parts.update({'hair_' + k: v for k, v in hp.items()})
for n, p in parts.items():
    print('%-12s %6d verts %6d tris' % (n, len(p['mesh'].V), len(p['mesh'].F)))
body = axr.export_body(sc)
items = body + axr.export_parts(parts, 'net')
ax = axr.Ax()
try:
    views = sys.argv[1].split(',') if len(sys.argv) > 1 else ['front', '34']
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    img = axr.render_item_views(ax, items, views=views, size=(size, int(size * 1.25)), radius=8.6, fov=22, exposure=0.9, rim=(0.8, 0.55, 0.9), rim_i=1.4)
    Image.fromarray(img).save('adv/ref/net.png')
    print('saved', img.shape, '%.1fs' % (time.time() - t0))
finally:
    ax.close()
