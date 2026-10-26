import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import donor_tools as dt
import adv_scene as asn
import ax_render as axr
from ethics_common import MODEL, G3

HEAD_SLOTS = ['Head', 'EyeL', 'EyeR', 'Cyberware', 'EyeBrows', 'EyeLashes', 'EyeMakeup', 'Lipstick', 'Mouth', 'Pimples', 'Port', 'PortEmissive', 'PortScrews', 'PortSillicone',
              'PortSilliconeShadow', 'Scalp', 'Hair']
MASKED = {'EyeBrows', 'EyeLashes', 'EyeMakeup', 'Hair', 'Scalp', 'PortSillicone', 'PortSilliconeShadow', 'Pimples'}


def load(mdl='donor/ssm/models/cyberpunk2077rex/songsomirex/song_so_mi_pm.mdl'):
    d = dt.Donor(mdl)
    pn, pp, pB = dt.read_bones(open(MODEL, 'rb').read())
    m = dt.Merger(d, pn, pB, G3)
    tr = d.triangles()
    P, N = m.skin(tr['pos'], tr['nrm'], tr['w'], tr['b'])
    return d, tr, P, N


def export_head(d, tr, P, N, slots=HEAD_SLOTS, hide=(), tex_size=1024, prefix='ssm'):
    items = []
    for name in slots:
        if name in hide or name not in d.tex:
            continue
        s = d.tex.index(name)
        sel = np.nonzero(tr['slot'] == s)[0]
        if len(sel) == 0:
            continue
        arr = d.texture_array(name)
        im = None
        if arr is not None:
            im = Image.fromarray(np.asarray(arr).astype(np.uint8))
            if im.mode != 'RGBA':
                im = im.convert('RGBA')
            if max(im.size) > tex_size:
                im.thumbnail((tex_size, tex_size))
        shader, params = d.vmt_params(name)
        masked = name in MASKED or 'alphatest' in params or 'translucent' in params
        color = (200, 200, 200)
        it = axr.export_soup('%s_%s' % (prefix, name), axr.to_ax(P[sel]), np.stack([-N[sel][..., 1], N[sel][..., 2], -N[sel][..., 0]], -1), tr['uv'][sel], tex_png=im, color=color,
                             rough=0.45, mask=masked, double=True)
        items.append(it)
    return items


if __name__ == '__main__':
    t0 = time.time()
    d, tr, P, N = load()
    print('skinned in %.1fs' % (time.time() - t0))
    for s in ('Head', 'EyeL', 'Hair', 'Port', 'Cyberware', 'Lipstick'):
        print(s, d.basetexture(s), d.vmt_params(s)[0], {k: v for k, v in d.vmt_params(s)[1].items() if k in ('basetexture', 'alphatest', 'translucent', 'nocull', 'phong', 'bumpmap', 'envmap', 'selfillum')})
    sc = asn.Scene()
    body = axr.export_body(sc, skip=('chau_facemap', 'eyeball_l', 'eyeball_r', 'fmouth'))
    items = body + export_head(d, tr, P, N)
    print('exported %d items %.1fs' % (len(items), time.time() - t0))
    ax = axr.Ax()
    try:
        img = axr.render_item_views(ax, items, views=['front', '34', 'left', 'back'], size=(420, 540), radius=9.5, fov=22, exposure=1.0, key=3.8, ambient=1.6, rim=(0.8, 0.5, 0.9), rim_i=1.4)
        Image.fromarray(img).save('adv/ref/ssm_head.png')
        print('rendered %.1fs' % (time.time() - t0))
    finally:
        ax.close()
