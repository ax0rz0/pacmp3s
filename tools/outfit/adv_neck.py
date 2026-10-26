"""A skin coloured neck for the donor head swap.

The Ethics Assistant's own head slot also holds her neck, so hiding the head hides the neck as well, and a bone-merged copy of her mesh leaves a nape fin and a chin lump (see
neck_lab.py).  This replaces it: a smooth column from inside the suit collar up into the donor head.  The front surface follows the player's own throat line; behind, the column flares back
and sideways towards its top so that it continues the donor's lower skull (the donor head is cut with a tilted clip plane under the skull, see make_adv_head_swap.py) instead of ending in
the donor's wide flat neck flange.  Built in the in-game bind frame like the other accessories.  build_neck() -> world-space Mesh."""
import numpy as np

import adv_geom as ag

# world x of the throat (front surface) by height z, measured on the Ethics Assistant's own skin slot; above z~60 it continues behind the chin into the donor head
FRONT = np.array([[55.0, 1.10], [58.0, 1.50], [58.7, 1.90], [59.3, 2.10], [60.0, 2.25], [61.0, 2.45], [63.6, 2.60]])
# world x of the back surface: straight behind the throat inside the suit collar, then flaring back like the lower skull
BACK = np.array([[55.0, -1.8], [59.5, -1.3], [61.0, -1.5], [62.2, -2.0], [63.0, -2.45], [63.6, -2.7]])
HALF_WIDTH = np.array([[55.0, 2.00], [59.0, 1.95], [61.0, 2.05], [62.2, 2.35], [63.0, 2.6], [63.6, 2.75]])


def build_neck(n_rings=26, sides=32):
    z = np.linspace(55.0, 63.6, n_rings)
    xf = np.interp(z, FRONT[:, 0], FRONT[:, 1])
    xb = np.interp(z, BACK[:, 0], BACK[:, 1])
    hw = np.interp(z, HALF_WIDTH[:, 0], HALF_WIDTH[:, 1])
    xc = (xf + xb) / 2.0
    depth = xf - xb
    path = np.column_stack([xc, np.zeros_like(z), z])
    # with up_hint = +y the section normal runs along y (scale[:,0] = half width) and the binormal along x (scale[:,1] = half depth)
    return ag.loft(path, ag.circle(sides, 1.0, 1.0), scale=np.column_stack([hw, depth / 2.0]), up_hint=np.array([0.0, 1.0, 0.0]), cap_start=True, cap_end=True)


if __name__ == '__main__':
    m = build_neck()
    V = m.V
    print('verts', len(V), 'tris', len(m.F), 'x', V[:, 0].min(), V[:, 0].max(), 'y', V[:, 1].min(), V[:, 1].max(), 'z', V[:, 2].min(), V[:, 2].max())
