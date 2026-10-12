"""Paint the three BNA Ethics Assistant styles (formal / anima / neon) for models/jericho/citizens/female_04.
    python make_ethics_textures.py            -> ethics/posmaps.npz (UV-space position maps) and ethics/tex_by_style.pkl (+ PNG previews in ethics/tex/)
    python make_ethics_textures.py --check    -> rebuild everything in memory and compare with the files above (nothing is written)
Region ids in the maps: 1 jacket (torso bodygroup), 2 trousers (skirt bodygroup 0), 3 skirt (skirt bodygroup 1), 4 head (female_04 bodygroup)."""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

import ethics_paint as ep
import uvmap
from ethics_common import G3, Body

HERE = os.path.dirname(os.path.abspath(__file__))
POSMAPS = os.path.join(HERE, 'ethics', 'posmaps.npz')
TEXPKL = os.path.join(HERE, 'ethics', 'tex_by_style.pkl')
STYLES = ('formal', 'anima', 'neon')


def _tris(m, bodypart, model_index, material, rid):
    tr = m.mesh_triangles(bodypart, model_index)
    sel = np.array(m.textures)[tr['slot']] == material
    n = int(sel.sum())
    return tr['pos'][sel] @ G3.T, tr['nrm'][sel] @ G3.T, tr['uv'][sel], np.full((n, 3), float(rid))


def build_posmaps(body):
    m = body.mesh
    groups = {'suit': [_tris(m, 'torso', 0, 'suit', 1), _tris(m, 'skirt', 0, 'suit', 2)],
              'skirt': [_tris(m, 'skirt', 1, 'skirt', 3)],
              'head': [_tris(m, 'female_04', 0, 'chau_facemap', 4)]}
    out = {}
    for prefix, parts in groups.items():
        pos, nrm, uv, rid = (np.concatenate(a) for a in zip(*parts))
        pm = uvmap.uv_raster(uv, {'pos': pos, 'nrm': nrm, 'rid': rid})
        for k in ('pos', 'nrm', 'rid', 'cover', 'padded'):
            out['%s_%s' % (prefix, k)] = pm[k]
    return out


def paint_all(body, maps):
    class Npz(dict):
        files = property(lambda self: list(self))
    npz = Npz(maps)
    M_suit, M_skirt, M_head = ep.Maps(npz, 'suit'), ep.Maps(npz, 'skirt'), ep.Maps(npz, 'head')
    tex = {}
    for style in STYLES:
        suit = ep.paint_suit(style, M_suit, body.stock['suit'])
        skirt = ep.paint_skirt(style, M_skirt, body.stock['skirt'])
        face = ep.paint_face(style, M_head, body.stock['chau_facemap'])
        tex[style] = {k: (np.clip(v, 0, 1) * 255 + 0.5).astype(np.uint8) for k, v in (('suit', suit), ('skirt', skirt), ('chau_facemap', face))}
    return tex


def main():
    check = '--check' in sys.argv
    body = Body()
    maps = build_posmaps(body)
    if check:
        old = np.load(POSMAPS)
        for k in maps:
            a, b = np.asarray(maps[k], np.float64), np.asarray(old[k], np.float64)
            print('posmap %-12s max abs difference %.3g' % (k, float(np.abs(a - b).max())))
    else:
        os.makedirs(os.path.dirname(POSMAPS), exist_ok=True)
        np.savez_compressed(POSMAPS, **maps)
        print('wrote', POSMAPS)
    tex = paint_all(body, maps)
    if check:
        old = pickle.load(open(TEXPKL, 'rb'))
        for style in STYLES:
            for k in tex[style]:
                d = np.abs(tex[style][k].astype(int) - old[style][k].astype(int))
                print('texture %-7s %-13s max difference %d, differing texels %.4f%%' % (style, k, d.max(), 100.0 * (d.max(-1) > 0).mean()))
    else:
        pickle.dump(tex, open(TEXPKL, 'wb'))
        os.makedirs(os.path.join(HERE, 'ethics', 'tex'), exist_ok=True)
        for style in STYLES:
            for k, v in tex[style].items():
                Image.fromarray(v).save(os.path.join(HERE, 'ethics', 'tex', '%s_%s.png' % (style, k)))
        print('wrote', TEXPKL)


if __name__ == '__main__':
    main()
