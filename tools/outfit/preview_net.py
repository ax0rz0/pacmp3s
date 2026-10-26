import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import adv_common as ac
import adv_geom as ag
import adv_net_arms as arms
import adv_scene as asn
import ax_render as axr
import make_adv_net as man


def neon(i=0):
    return tuple(int(c * 255) for c in ac.PALETTE_NEON[i])


def net_items(sc, meshes, amesh, theme=0, hair_col=0, gloves=True, extra=()):
    glowc = neon(theme)
    hc = tuple(int(c * 255) for c in ac.PALETTE_HAIR[hair_col])
    parts = {
        'black': dict(mesh=meshes['black'], color=(18, 18, 23), rough=0.5, smooth=42),
        'gray': dict(mesh=meshes['gray'], color=(50, 52, 64), rough=0.4, metal=0.5, smooth=42),
        'gun': dict(mesh=meshes['gun'], color=(107, 112, 128), rough=0.3, metal=0.7, smooth=42),
        'glow': dict(mesh=meshes['glow'], color=glowc, nolight=True, smooth=55),
    }
    if 'hair' in meshes:
        parts['hair'] = dict(mesh=meshes['hair'], color=hc, rough=0.42, smooth=60)
        parts['pony'] = dict(mesh=meshes['pony'], color=hc, rough=0.42, smooth=60)
        parts['pony_tips'] = dict(mesh=meshes['pony_tips'], color=glowc, nolight=True, smooth=65)
    for k, v in amesh.items():
        col = glowc if k.startswith('glow') else (44, 46, 56)
        parts[k] = dict(mesh=v, color=col, nolight=k.startswith('glow'), rough=0.35, metal=0.5, smooth=45)
        parts[k + '_r'] = dict(mesh=ag.mirror_y(v), color=col, nolight=k.startswith('glow'), rough=0.35, metal=0.5, smooth=45)
    return axr.export_parts(parts, 'netp')


if __name__ == '__main__':
    t0 = time.time()
    sc = asn.Scene()
    meshes, ctx, tie = man.world_meshes(sc)
    am, _ = arms.build_arm(sc)
    body = axr.export_body(sc)
    for it in body:
        if it['name'] in ('body_citizen_sheet', 'body_handfemale'):
            it['tex'] = None
            it['color'] = (14, 14, 18)
            it['rough'] = 0.3
    items = body + net_items(sc, meshes, am)
    ax = axr.Ax()
    try:
        head = axr.render_item_views(ax, items, views=['front', '34', 'back'], size=(420, 540), radius=9.5, fov=22, exposure=1.0, key=3.8, ambient=1.5, rim=(0.8, 0.5, 0.9), rim_i=1.4)
        full = axr.render_item_views(ax, items, views=['front', '34', 'back'], size=(420, 840), radius=38.0, fov=22, focus=(0, 0, 36.0), exposure=1.0, key=3.8, ambient=1.5)
        Image.fromarray(head).save('adv/ref/net_final_head.png')
        Image.fromarray(full).save('adv/ref/net_final_full.png')
        print('done %.1fs' % (time.time() - t0))
    finally:
        ax.close()
