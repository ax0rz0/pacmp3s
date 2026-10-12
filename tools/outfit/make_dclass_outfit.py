"""Build 'd-class low sec bna.txt': the user's d-class low sec outfit with the emote pack removed and a BNA accessory group added (the gray uniform is untouched).
Assets are staged under STAGE (obj/bna, tex/bna) for the repo; the outfit links them by raw GitHub URL."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import bna_parts as bp
import dclass_acc as da
import dclass_scene as ds
import ethics_acc as ea
import pac_parse as pp
import pac_write as pw

PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'
SRC = os.path.join(PAC_DIR, 'd-class low sec.txt')
SLUG = 'dclass_low_sec_bna'
STAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_bna')


def build(out_path=None, stage=STAGE):
    d = ds.DClass()
    S = ea.Surface(d.body_triangles()['pos'])
    acc, spr = da.build_dclass(d, S)
    urls = bp.stage_assets(stage, 'bna', acc, d.rig, 'dclass')
    parts = pp.load(SRC)
    # 1) drop the emote pack (the top-level group holding the command events, animations, sounds, props)
    removed = 0
    keep = {}
    for k in sorted(k for k in parts if isinstance(k, int)):
        s = parts[k]['self']
        n_events = sum(1 for p in pw.walk([parts[k]]) if p['self'].get('ClassName') == 'event')
        if s['ClassName'] == 'group' and n_events > 10:
            removed += sum(1 for _ in pw.walk([parts[k]]))
            continue
        keep[len(keep) + 1] = parts[k]
    # 2) the BNA accessory group (Size 0.95 like the user's entity2 so the accessories scale with the body)
    # the material_3d parts of the textured accessories come first: model2 `Material` finds them by name only if they already exist
    mat_parts, tex_names = bp.texture_material_parts(acc, urls, 'bna dclass')
    kids = mat_parts + bp.parts_for(acc, urls, size=0.95, tex_names=tex_names) + bp.sprite_parts(spr, d.rig)
    keep[len(keep) + 1] = bp.group('BNA accessories (D-class)', kids)
    # 3) watermark + fresh UIDs
    for k in keep:
        keep[k]['self']['Notes'] = bp.WATERMARK
    pw.remap_uids(keep, SLUG)
    text = pw.dump(keep, watermark=bp.WATERMARK)
    if out_path:
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, keep, removed, acc, spr, urls


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(STAGE, 'outfits', 'd-class low sec bna.txt')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text, keep, removed, acc, spr, urls = build(out)
    n = sum(1 for _ in pw.walk(keep))
    print('wrote %s (%d bytes, %d parts; %d emote-pack parts removed; %d accessories + %d sprites added)' % (out, len(text), n, removed, len(acc), len(spr)))
