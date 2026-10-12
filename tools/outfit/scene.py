"""Build and render a styled scene: painted body + accessories (+ glow sprites as emissive blobs)."""
import pickle
import numpy as np
from PIL import Image
import preview as pv
import meshgen as mg
from ethics_common import Body, PALETTE
import ethics_acc as ea

_body = None
_tex = None


def body():
    global _body, _tex
    if _body is None:
        _body = Body()
        _tex = pickle.load(open('ethics/tex_by_style.pkl', 'rb'))
    return _body, _tex


def surfaces(b, skirt):
    tr = b.triangles(skirt=skirt)
    names = np.array(b.mesh.textures)
    S = ea.Surface(tr['pos'])
    sel = names[tr['slot']] == 'suit'
    S_suit = ea.Surface(tr['pos'][sel])
    return S, S_suit


def acc_soup(a, texlist):
    m = a.mesh
    col = np.array(a.color if a.color else (200, 200, 200), float)
    if a.material == 'texture' and a.texture is not None:
        texlist.append(a.texture)
        s = pv.mesh_to_soup(m.V, m.F, N=m.normals(), UV=m.UV, tex=len(texlist) - 1, color=col)
    else:
        s = pv.mesh_to_soup(m.V, m.F, N=m.normals(), UV=None, tex=-1, color=col, glow=0.9 if a.nolight else 0.0)
    return s


def sprite_soup(sp):
    m = mg.ellipsoid((sp.size * 0.16,) * 3, nu=10, nv=6).transform(t=sp.pos)
    return pv.mesh_to_soup(m.V, m.F, N=None, UV=None, tex=-1, color=np.array(sp.color, float), glow=1.0)


def build(style, builder, skirt=True):
    b, tex = body()
    S, S_suit = surfaces(b, skirt)
    acc, spr = builder(b, S, S_suit)
    soup, texlist = b.soup(skirt=skirt, textures=tex[style], flat={'eyeball_l': (40, 28, 26), 'eyeball_r': (40, 28, 26)})
    parts = [soup]
    for a in acc:
        if a.alpha is not None:
            continue                      # translucent parts are not drawn in the preview
        parts.append(acc_soup(a, texlist))
    for sp in spr:
        parts.append(sprite_soup(sp))
    return pv.concat(parts), texlist, acc, spr


def render_views(scene, texlist, views=('front', '34', 'back'), height=720, bounds_from=None):
    ims = []
    for v in views:
        bnd = pv.fit_bounds((bounds_from if bounds_from is not None else scene['pos']), v)
        ims.append(pv.render(scene, texlist, v, height=height, bounds=bnd))
    return np.concatenate(ims, axis=1)
