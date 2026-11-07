"""the guitar (models/custom/guitar/m_d_45.mdl, a Martin D-45, 1 bone) held on the chest, in the model frame of the player (+X forward, +Y left, +Z up).

Guitar local frame (from the model's vertices): +Z along the guitar, body z 0..25 (width x +-9.8, sound hole centred at z 16, radius ~7), neck z 25..46, headstock to z 50; the soundboard is the -Y face
(y -1.9), the back the +Y face (y +3.5).  The model is scaled down (Size) because the Ethics Assistant is only about 62 units tall with 22 unit arms.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\emote')
from retarget import norm

MODEL = 'models/custom/guitar/m_d_45.mdl'
SIZE = 0.62                                   # model scale
NUT_Z, SCALE_LEN = 46.3, 40.6                 # model units: the nut and the scale length (the 12th fret is half way, at z ~26 = the body joint)
BODY_C = np.array([0.0, 0.8, 12.0])           # centre of the body in guitar-local units
N_DIR = norm(np.array([0.60, 0.72, 0.34]))     # neck direction (headstock end) in the model frame: forward, to the player's left, a little up
F0 = np.array([0.82, -0.25, 0.50])            # roughly where the soundboard faces
C_BODY = np.array([6.0, -3.0, 35.5])          # where the body centre sits in the model frame (base pose) before the chest moves


def frame():
    z = N_DIR
    f = F0 - z * float(np.dot(F0, z))
    f = norm(f)                                # soundboard normal (front)
    y = -f                                     # local +Y points at the back
    x = np.cross(y, z)
    R = np.stack([x, y, z], axis=1)           # columns = local axes in the model frame
    return R


R_G = frame()
ORIGIN = C_BODY - R_G @ (BODY_C * SIZE)


def g2w(local):
    """guitar-local point (model units of the mesh) -> model frame"""
    return ORIGIN + R_G @ (np.asarray(local, float) * SIZE)


def fret_z(f):
    return NUT_Z - SCALE_LEN * (1.0 - 2.0 ** (-f / 12.0))


def points(n=2500, seed=1):
    pos = np.load(os.path.join(HERE, 'guitar_pos.npy'))
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(pos), size=min(n, len(pos)), replace=False)
    return np.array([g2w(p) for p in pos[idx]])
