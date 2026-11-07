"""the Xbox scene: a small table, a TV and a console in front of the player, in the model frame of the player (+X forward, +Y left, +Z up, origin between the feet).

Everything is built from the Hunter blocks / plates that ship with Garry's Mod (no custom models); the TV screen is a plate scaled to 16:9 whose top face has uv 0..1, standing on edge
so that the picture reads upright for someone standing at the table.  Units are Source units; the Ethics Assistant is about 62 units tall with 22 unit arms, so the scene is small.
"""
import math

import numpy as np

CUBE = 'models/hunter/blocks/cube025x025x025.mdl'           # a cube, 11.82 units on a side
PLATE = 'models/hunter/plates/plate1x1.mdl'                  # 47.45 x 47.45 x 3, top face uv 0..1  (u towards +y, v towards +x)
SPHERE = 'models/hunter/misc/sphere025x025.mdl'
CUBE_SIZE = 11.82
PLATE_SIZE = 47.46
PLATE_T = 3.0

TABLE_TOP = 24.0
TABLE_X0, TABLE_X1 = 10.0, 46.0            # depth, front edge nearest the player
TABLE_Y = 22.0                             # half width
TV_X = 36.0                                # centre of the TV bezel (front face at TV_X - 1.1)
TV_W, TV_H, TV_D = 28.0, 17.5, 2.2
TV_Z = TABLE_TOP + 2.4 + TV_H / 2          # bottom of the bezel sits on a 2.4 high foot
SCREEN_W, SCREEN_H = 25.6, 14.4            # 16:9
CONSOLE_C = np.array([20.0, -10.0, TABLE_TOP + 1.4])
CONSOLE_SIZE = np.array([9.0, 11.0, 2.8])
BUTTON = np.array([CONSOLE_C[0] - CONSOLE_SIZE[0] / 2 - 0.2, CONSOLE_C[1] - 3.8, CONSOLE_C[2] + 0.3])   # power button on the front face


def box(center, size, color, name, model=CUBE):
    """a part description: block scaled to `size` (x, y, z world axes)"""
    return dict(kind='box', name=name, model=model, pos=tuple(float(v) for v in center), scale=tuple(float(s) / CUBE_SIZE for s in size), ang=(0.0, 0.0, 0.0), color=color, size=tuple(float(v) for v in size))


def table_parts():
    parts = []
    parts.append(dict(box((sum((TABLE_X0, TABLE_X1)) / 2, 0.0, TABLE_TOP - 0.6), (TABLE_X1 - TABLE_X0, 2 * TABLE_Y, 1.2), (0.36, 0.22, 0.12), 'table top')))
    for sx in (TABLE_X0 + 2.0, TABLE_X1 - 2.0):
        for sy in (-TABLE_Y + 2.0, TABLE_Y - 2.0):
            parts.append(dict(box((sx, sy, (TABLE_TOP - 1.2) / 2), (2.6, 2.6, TABLE_TOP - 1.2), (0.30, 0.18, 0.10), 'table leg')))
    return parts


def tv_parts():
    parts = []
    parts.append(dict(box((TV_X, 0.0, TV_Z), (TV_D, TV_W, TV_H), (0.025, 0.025, 0.03), 'tv bezel')))
    parts.append(dict(box((TV_X + 0.3, 0.0, TABLE_TOP + 1.2), (2.4, 6.0, 2.4), (0.04, 0.04, 0.045), 'tv neck')))
    parts.append(dict(box((TV_X + 0.3, 0.0, TABLE_TOP + 0.3), (7.0, 13.0, 0.6), (0.05, 0.05, 0.055), 'tv foot')))
    return parts


def console_parts():
    parts = []
    c = CONSOLE_C
    parts.append(dict(box(c, tuple(CONSOLE_SIZE), (0.07, 0.07, 0.075), 'console body')))
    parts.append(dict(box((c[0] + 0.4, c[1], c[2] + CONSOLE_SIZE[2] / 2 + 0.05), (CONSOLE_SIZE[0] * 0.78, CONSOLE_SIZE[1] * 0.8, 0.12), (0.035, 0.035, 0.04), 'console top vent')))
    parts.append(dict(kind='box', name='power button', model=SPHERE, pos=tuple(float(v) for v in BUTTON), scale=(2.2 / 11.86, 2.2 / 11.86, 0.8 / 11.86), ang=(0.0, 0.0, 0.0), color=(0.12, 0.13, 0.12), size=(2.2, 2.2, 0.8)))
    return parts


def screen_part():
    """the TV screen: a plate standing on edge, top face towards -X (the player).  local x (v, down the picture) -> world -Z, local y (u, along the picture) -> world -Y, local z (normal) -> world -X"""
    R = np.array([[0.0, 0.0, -1.0], [0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]])
    return dict(kind='screen', name='tv screen', model=PLATE, pos=(TV_X - TV_D / 2 - 0.12, 0.0, TV_Z), R=R,
                scale=(SCREEN_H / PLATE_SIZE, SCREEN_W / PLATE_SIZE, 0.06), size=(SCREEN_H, SCREEN_W, PLATE_T * 0.06))


def all_parts():
    return table_parts() + tv_parts() + console_parts() + [screen_part()]


def box_corners(center, size):
    c = np.asarray(center, float)
    h = np.asarray(size, float) / 2
    return np.array([[c[0] + sx * h[0], c[1] + sy * h[1], c[2] + sz * h[2]] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])


EDGES = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
