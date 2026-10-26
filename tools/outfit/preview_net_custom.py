import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_net_arms as arms
import adv_scene as asn
import ax_render as axr
import make_adv_net as man
import make_adv_net_custom as mc
import preview_net as pv
import run_donor_preview as rdp
from ethics_acc import Surface

if __name__ == '__main__':
    t0 = time.time()
    d, tr, P, N = rdp.load()
    sel = np.isin(tr['slot'], [d.tex.index(n) for n in ('Head', 'Lipstick', 'Mouth', 'Cyberware', 'EyeMakeup', 'Pimples')])
    S_d = Surface(P[sel])
    sc = asn.Scene()
    kw = dict(head_surface=S_d, axis_xy=(-0.6, 0.0), warp=([60.25, 62.3, 63.6, 65.1, 67.5], [61.0, 62.6, 64.0, 65.36, 67.6]), cup_x=-1.0, cup_y=4.7, cup_z=64.9, arc_top=72.2, eye_u=-1.33, eye_v=65.12, act_smooth=5, act_dilate=4, max_dev=2.2, inflate=0.4, filter_v=62.7)
    meshes, ctx, tie = man.world_meshes(sc, kw, with_hair=False)
    am, _ = arms.build_arm(sc)
    body = axr.export_body(sc, skip=('chau_facemap', 'eyeball_l', 'eyeball_r', 'fmouth'))
    for it in body:
        if it['name'] in ('body_citizen_sheet', 'body_handfemale'):
            it['tex'] = None; it['color'] = (14, 14, 18); it['rough'] = 0.3
    items = body + rdp.export_head(d, tr, P, N) + pv.net_items(sc, meshes, am)
    ax = axr.Ax()
    try:
        head = axr.render_item_views(ax, items, views=['front', '34', 'left'], size=(420, 540), radius=9.5, fov=22, exposure=1.0, key=3.8, ambient=2.2, rim=(0.7, 0.6, 0.9), rim_i=0.8)
        Image.fromarray(head).save('adv/ref/netc_head.png')
        print('done %.1fs' % (time.time() - t0))
    finally:
        ax.close()
