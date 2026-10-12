"""Build 'tech expert bna.txt': the user's tech expert outfit with the BNA retexture (image URLs in the Materials of its entity2 parts, their null slots kept) and a BNA accessory group.
Everything else of the original stays as it is. Assets are staged under STAGE (obj/bna, tex/bna) for the repo; the outfit links them by raw GitHub URL."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import bna_parts as bp
import make_tech_textures as mtt
import pac_parse as pp
import pac_write as pw
import tech_acc as ta
import tech_deform as td
import tech_paint as tp
import tech_scene as ts

PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'
SRC = os.path.join(PAC_DIR, 'tech expert.txt')
SLUG = 'tech_expert_bna'
STAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_bna')
SIZE = 0.85                      # the Size of the user's entity2 parts: bone-attached accessories scale with the body
NOCLAMP_SLOTS = (5, 6)           # the helmet and backpack UVs run outside 0..1 (wrapping texture needed)
N_SLOTS = 20


def texture_urls():
    out = {}
    for slot in tp.SLOTS:
        u = bp.REPO_RAW + 'tex/bna/' + tp.slot_filename(slot)
        out[slot] = u + (' noclamp' if slot in NOCLAMP_SLOTS else '')
    return out


def with_textures(materials, urls, n_slots=N_SLOTS):
    """add the BNA urls to a ';'-separated Materials string; slots the user already filled (the null head slots) are kept, a clash is an error"""
    mats = materials.split(';')
    mats += [''] * (n_slots - len(mats))
    for slot, u in urls.items():
        if mats[slot - 1] != '':
            raise ValueError('slot %d is already set in the original entity2: %r' % (slot, mats[slot - 1]))
        mats[slot - 1] = u
    return ';'.join(mats)


def build(out_path=None, stage=STAGE):
    te = ts.TechExpert()
    drig = td.DeformedRig(ts.TECH, td.bone_scales_from_outfit(SRC, te.rig))
    acc, spr = ta.build_tech(te)
    urls = bp.stage_assets(stage, 'bna', acc, drig, 'tech')
    parts = pp.load(SRC)
    n_orig_top = len(parts)
    urls_tex = texture_urls()
    n_entity = 0
    for p in pw.walk(parts):
        s = p['self']
        if s['ClassName'] == 'entity2':
            s['Materials'] = with_textures(s.get('Materials', ''), urls_tex)
            n_entity += 1
    if n_entity < 1:
        raise RuntimeError('the original outfit has no entity2 part')
    kids = bp.parts_for(acc, urls, size=SIZE) + bp.sprite_parts(spr, drig)
    for k in kids:
        k['self']['Name'] = k['self']['Name'].replace('_', ' ')
    parts[n_orig_top + 1] = bp.group('BNA accessories (tech expert)', kids)
    for key in parts:
        parts[key]['self']['Notes'] = bp.WATERMARK
    pw.remap_uids(parts, SLUG)
    text = pw.dump(parts, watermark=bp.WATERMARK)
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    return text, parts, acc, spr, urls, n_entity


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(STAGE, 'outfits', 'tech expert bna.txt')
    mtt_out = os.path.join(STAGE, 'tex', 'bna')
    if not os.path.exists(os.path.join(mtt_out, 'tech_vest.jpg')):
        orig, _ = mtt.originals()
        tp.make_all(mtt_out, orig)
    text, parts, acc, spr, urls, n_entity = build(out)
    print('wrote %s (%d bytes, %d parts; %d entity2 parts retextured; %d accessories + %d sprites added)' % (out, len(text), sum(1 for _ in pw.walk(parts)), n_entity, len(acc), len(spr)))
