"""CPU preview of the guitar poses: layer A's body / right hand at a few beats of the pattern, the left hand in a few chord shapes"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guitar_layers as gl
import guitar_prev as gp
import guitar_scene as gs
import midi_guitar as mg
from guitar_anim import Rigged, nominal

ZOOM = {'side': ((-22, 32), (12, 66)), 'front': ((-34, 34), (12, 66)), 'q': ((-36, 30), (12, 66))}


def main(out_name='guitar_poses.png', beats=(0.0, 1.0, 1.5, 2.5), roots=('D', 'G', 'B', 'A')):
    G = Rigged('ethics')
    jsA, infoA = gl.layer_a(G)
    pose = infoA['pose']
    P0 = nominal()
    items = []
    for b, root in zip(beats, roots):
        P = pose(b * mg.SPB)
        P.update(gl.left_pose(G, P0, root)[0])
        solved = G.arms.solved(P)
        M, trl, AR, AP = solved
        tg = [G.to_world(P, loc, solved) for loc in gl.LEFT_SHAPES[root].values()]
        tg += [G.to_world(P, np.array([x, -3.5, 16.8]), solved) for x in (-1.9, 0.4, 1.7)]
        items.append(('beat %.1f chord %s' % (b, root), G.rig, AR, AP, G, P, tg))
    path = os.path.join(HERE, 'out', out_name)
    gp.grid(path, items, views=('side', 'front', 'q'), zoom=ZOOM, size=(3.6, 3.3), title='guitar poses (ethics rig): body + right hand from layer A, left hand from layer B')
    print('wrote', path)


if __name__ == '__main__':
    main()
