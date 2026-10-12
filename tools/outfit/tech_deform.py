"""Emulates the user's 'bone3' feminiser (ManipulateBoneScale on pelvis / thighs / upper arms) for bone-attached accessories.

In game each bone matrix is W'_i = W'_parent * L_i * S_i (S_i = the bone's scale in its own axes), so a scale on a bone also moves/scales all its descendants. pac draws a model2 part at the
bone's POSITION and ANGLES only (Source MatrixAngles of the sheared matrix: yaw/pitch from the forward column, roll from left.z/up.z), the part itself is rigid. An accessory authored on the
bind-pose surface is therefore mapped with M_B = W'_B W_B^-1 (where the surface it sits on really is) and then expressed in the frame pac will use (p'_B, R'_B).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ethics_acc as ea
import pac_parse as pp
import pac_write as pw
from ethics_common import Rig, matrix_from_angles


def source_angles(W):
    """Source MatrixAngles of a (possibly scaled / sheared) bone matrix -> (pitch, yaw, roll) degrees"""
    f, l, u = W[:3, 0], W[:3, 1], W[:3, 2]
    xy = np.hypot(f[0], f[1])
    if xy > 1e-3:
        yaw = np.degrees(np.arctan2(f[1], f[0]))
        pitch = np.degrees(np.arctan2(-f[2], xy))
        roll = np.degrees(np.arctan2(l[2], u[2]))
    else:
        yaw = np.degrees(np.arctan2(-l[0], l[1]))
        pitch = np.degrees(np.arctan2(-f[2], xy))
        roll = 0.0
    return np.array([pitch, yaw, roll])


def bone_scales_from_outfit(path, rig):
    """{bone index: (sx, sy, sz)} from the bone3 / bone parts of a pac outfit file (Scale * Size, multiplied when a bone appears twice)"""
    names = {ea.friendly(n): i for i, n in enumerate(rig.names)}
    out = {}
    for p in pw.walk(pp.load(path)):
        s = p['self']
        if s.get('ClassName') not in ('bone3', 'bone2', 'bone') or s.get('Hide'):
            continue
        i = names.get(s.get('Bone'))
        if i is None:
            raise KeyError('bone %r of the outfit is not in the rig' % s.get('Bone'))
        sc = np.array(s.get('Scale', ('Vector', (1, 1, 1)))[1], float) * float(s.get('Size', 1.0))
        out[i] = out.get(i, np.ones(3)) * sc
    return out


class DeformedRig(Rig):
    """A Rig whose accessories are localised for the scaled skeleton (see module docstring). With no scales it reproduces Rig exactly."""

    def __init__(self, mdl_path, scales):
        super().__init__(mdl_path)
        n = len(self.names)
        self.scales = scales
        self.world0 = [np.asarray(w, float) for w in self.world]
        W1 = [None] * n
        for i in range(n):                                   # bones are stored parent-first
            p = self.parents[i]
            L = self.world0[i] if p < 0 else np.linalg.inv(self.world0[p]) @ self.world0[i]
            S = np.eye(4)
            if i in scales:
                S[:3, :3] = np.diag(scales[i])
            W1[i] = (L @ S) if p < 0 else (W1[p] @ L @ S)
        self.world1 = W1

    def deform_matrix(self, bone_name):
        i = self.idx[bone_name]
        return self.world1[i] @ np.linalg.inv(self.world0[i])

    def pac_pose(self, bone_name):
        """(position, 3x3 rotation) of the bone as pac sees it in game"""
        W = self.world1[self.idx[bone_name]]
        return W[:3, 3].copy(), matrix_from_angles(*source_angles(W))

    def deform_points(self, bone_name, V):
        M = self.deform_matrix(bone_name)
        return np.asarray(V, float) @ M[:3, :3].T + M[:3, 3]

    def localize(self, bone_name, V):
        """world-space (bind pose, unscaled body) points sitting on the surface of bone `bone_name` -> the bone-local coordinates to bake into the OBJ"""
        p, R = self.pac_pose(bone_name)
        return (self.deform_points(bone_name, V) - p) @ R


if __name__ == '__main__':
    from tech_scene import TECH
    outfit = sys.argv[1] if len(sys.argv) > 1 else r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3\tech expert.txt'
    base = Rig(TECH)
    sc = bone_scales_from_outfit(outfit, base)
    print('bone scales from the outfit:', {base.names[i]: tuple(np.round(v, 3)) for i, v in sc.items()})
    ident = DeformedRig(TECH, {})
    rng = np.random.RandomState(1)
    err = 0.0
    for name in ('ValveBiped.Bip01_Head1', 'ValveBiped.Bip01_Spine4', 'ValveBiped.Bip01_L_Forearm', 'ValveBiped.Bip01_Pelvis'):
        V = rng.randn(20, 3) * 5 + base.world[base.idx[name]][:3, 3]
        W = base.world[base.idx[name]]
        old = (V - W[:3, 3]) @ W[:3, :3]
        err = max(err, float(np.abs(ident.localize(name, V) - old).max()))
    print('identity check (no scales) max deviation from Rig: %.2e' % err)
    d = DeformedRig(TECH, sc)
    for name in ('ValveBiped.Bip01_Head1', 'ValveBiped.Bip01_Spine4', 'ValveBiped.Bip01_L_Forearm', 'ValveBiped.Bip01_L_Hand', 'ValveBiped.Bip01_Pelvis'):
        p0 = base.world[base.idx[name]]
        p1, R1 = d.pac_pose(name)
        dang = np.degrees(np.arccos(np.clip((np.trace(base.world[base.idx[name]][:3, :3].T @ R1) - 1) / 2, -1, 1)))
        print('  %-26s bind pos (%6.2f %6.2f %6.2f) -> in game (%6.2f %6.2f %6.2f), orientation changes by %.1f deg' % ((name,) + tuple(p0[:3, 3]) + tuple(p1) + (dang,)))
