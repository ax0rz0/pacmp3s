"""Previews of the tech expert outfit: bind pose, or deformed by the user's feminiser bone scales with every accessory placed the way pac will draw it (bone position + angles)."""
import os

import numpy as np
from PIL import Image

import meshgen as mg
import preview as pv
import scene as sc
import tech_paint as tp
import tech_scene as ts
from ethics_acc import Acc
from ethics_common import G3

STAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stage_bna')


def bna_textures(te, tex_dir=None):
    tdir = tex_dir or os.path.join(STAGE, 'tex', 'bna')
    over = {}
    for slot in tp.SLOTS:
        over[te.mesh.textures[slot - 1]] = np.asarray(Image.open(os.path.join(tdir, tp.slot_filename(slot))).convert('RGB'))
    return over


def lbs(pos, nrm, W, B, drig):
    """linear blend skinning with the deformed skeleton (the vertices are in the game frame, bind pose)"""
    out = np.zeros_like(pos)
    outn = np.zeros_like(nrm)
    tot = W.sum(-1)
    for k in range(W.shape[-1]):
        w, b = W[..., k], B[..., k]
        for bi in np.unique(b[w > 0]):
            sel = (b == bi) & (w > 0)
            M = drig.world1[bi] @ np.linalg.inv(drig.world0[bi])
            out[sel] += w[sel][:, None] * (pos[sel] @ M[:3, :3].T + M[:3, 3])
            outn[sel] += w[sel][:, None] * (nrm[sel] @ M[:3, :3].T)
    out /= np.maximum(tot, 1e-6)[..., None]
    n = np.linalg.norm(outn, axis=-1, keepdims=True)
    return out, outn / np.maximum(n, 1e-9)


def body_soup(te, textures, drig=None):
    """the tech expert in the user's bodygroups + the Female_04 head; deformed when drig is given"""
    if drig is None:
        return te.soup(textures=textures)
    ch = dict(ts.USER_BODYGROUPS)
    tr = te.mesh.triangles(ch, skin=0, exclude_materials=ts.HEAD_MATS, with_skin=True)
    pos = tr['pos'] @ G3.T
    nrm = tr['nrm'] @ G3.T
    pos, nrm = lbs(pos, nrm, tr['w'].astype(float), tr['b'].astype(int), drig)
    tr = dict(tr, pos=pos, nrm=nrm)
    texlist, ids = [], {}
    names = te.mesh.textures
    tex = dict(te.tex)
    tex.update(textures or {})
    tid = np.full(len(tr['slot']), -1, np.int64)
    col = np.tile(np.array((120, 120, 120), float), (len(tr['slot']), 1))
    for slot in np.unique(tr['slot']):
        n = names[slot]
        sel = tr['slot'] == slot
        if n in tex and tex[n] is not None:
            if n not in ids:
                ids[n] = len(texlist)
                texlist.append(tex[n])
            tid[sel] = ids[n]
    a = dict(pos=tr['pos'], nrm=tr['nrm'], uv=tr['uv'], tex=tid, color=col, glow=np.zeros(len(tid)))
    b = te._soup_from(te.head_triangles(world=drig.world1), te.fmdl.textures, te.head_tex, ids, texlist,
                      special={'eyeball_l': (235, 235, 235), 'eyeball_r': (235, 235, 235), 'pupil_l': (40, 28, 26), 'pupil_r': (40, 28, 26)})
    return pv.concat([a, b]), texlist


def placed(a, drig):
    """the accessory exactly where pac draws it: bone-local mesh -> world through the bone's position + angles (deformed rig)"""
    local = drig.localize(a.bone, a.mesh.V)
    p, R = drig.pac_pose(a.bone)
    m = mg.Mesh(local @ R.T + p, a.mesh.UV.copy(), a.mesh.F.copy())
    return Acc(a.name, m, a.bone, color=a.color, material=a.material, alpha=a.alpha, nocull=a.nocull, nolight=a.nolight, texture=a.texture, translucent=a.translucent)


def placed_sprite(sp, drig):
    p, R = drig.pac_pose(sp.bone)
    q = drig.localize(sp.bone, sp.pos[None, :])[0] @ R.T + p
    return type(sp)(sp.name, sp.bone, q, sp.color, sp.size, sp.alpha)


def full_scene(te, textures, acc, spr, drig=None):
    soup, texlist = body_soup(te, textures, drig)
    parts = [soup]
    for a in acc:
        if a.alpha is not None:
            continue
        parts.append(sc.acc_soup(placed(a, drig) if drig is not None else a, texlist))
    for s in spr:
        parts.append(sc.sprite_soup(placed_sprite(s, drig) if drig is not None else s))
    return pv.concat(parts), texlist


def render_views(scene, texlist, views, height=720, focus=None):
    ims = []
    pts = scene['pos'].reshape(-1, 3)
    if focus is not None:
        pts = pts[focus(pts)]
    for v in views:
        bnd = pv.fit_bounds(pts.reshape(-1, 1, 3), v)
        ims.append(pv.render(scene, texlist, v, height=height, bounds=bnd))
    return np.concatenate(ims, axis=1)
