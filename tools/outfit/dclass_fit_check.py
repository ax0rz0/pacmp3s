"""How well do the D-class accessories sit on the body the way the user's feminiser deforms it in game?  Old placement (bind-pose localisation) vs the deformation-aware one.
python dclass_fit_check.py   -> per accessory: median / 90th percentile / max distance of its vertices to the nearest deformed-body vertex (smaller = snugger, but never sunk in: see 'inside')"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import dclass_acc as da
import dclass_scene as ds
import ethics_acc as ea
import tech_deform as td
import tech_preview as tpv
from ethics_common import G3, Rig

SRC = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3\d-class low sec.txt'


def nearest(points, body, chunk=400):
    out = np.empty(len(points), np.float32)
    b = body.astype(np.float32)
    for i in range(0, len(points), chunk):
        p = points[i:i + chunk].astype(np.float32)
        d2 = ((p[:, None, :] - b[None, :, :]) ** 2).sum(-1)
        out[i:i + chunk] = np.sqrt(d2.min(1))
    return out


d = ds.DClass()
scales = td.bone_scales_from_outfit(SRC, d.rig)
print('bone scales in the D-class outfit:', {d.rig.names[i].split('_', 1)[-1]: tuple(np.round(v, 2)) for i, v in scales.items()})
drig = td.DeformedRig(ds.MIKE, scales)
S = ea.Surface(d.body_triangles()['pos'])
acc, spr = da.build_dclass(d, S)
tr = d.mesh.triangles({'belts': 0, 'hats': 2}, skin=0, exclude_materials=ds.HEAD_MATS, with_skin=True)
pos = tr['pos'] @ G3.T
nrm = tr['nrm'] @ G3.T
pos_def, _ = tpv.lbs(pos, nrm, tr['w'].astype(float), tr['b'].astype(int), drig)
body = np.unique(np.round(pos_def.reshape(-1, 3), 2), axis=0)
print('deformed body vertices %d' % len(body))
print('%-16s %-10s | old placement: median p90 max | new (deformation-aware): median p90 max' % ('accessory', 'bone'))
for a in acc:
    V = a.mesh.V
    # old: what the shipped OBJ does (plain bind-pose localisation) drawn by pac on the deformed skeleton
    W = d.rig.world[d.rig.idx[a.bone]]
    local_old = (V - W[:3, 3]) @ W[:3, :3]
    p, R = drig.pac_pose(a.bone)
    old_world = local_old @ R.T + p
    new_world = drig.localize(a.bone, V) @ R.T + p
    do, dn = nearest(old_world, body), nearest(new_world, body)
    print('%-16s %-10s | %5.2f %5.2f %5.2f | %5.2f %5.2f %5.2f' % (a.name, a.bone.split('_', 1)[-1], np.median(do), np.percentile(do, 90), do.max(), np.median(dn), np.percentile(dn, 90), dn.max()))
