"""Overlay check: skeleton (blue) + the carrier-driven prop mesh (orange), re-built from the JSON exactly as pac would apply it."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import make_fn_pack as fp
import prop_geom as pg
from retarget import Valve, ValveAnimSource, Retargeter
from mdl_anim import load_model
import emote_props as ep

CH = [['Pelvis', 'Spine', 'Spine1', 'Spine2', 'Spine4', 'Neck1', 'Head1'], ['Spine4', 'R_Clavicle', 'R_UpperArm', 'R_Forearm', 'R_Hand', 'R_Finger2'],
      ['Spine4', 'L_Clavicle', 'L_UpperArm', 'L_Forearm', 'L_Hand', 'L_Finger2'], ['Pelvis', 'R_Thigh', 'R_Calf', 'R_Foot', 'R_Toe0'],
      ['Pelvis', 'L_Thigh', 'L_Calf', 'L_Foot', 'L_Toe0']]


def build_rt(family, model, seq, fps_src=None):
    valve = Valve(load_model(fp.FAMILIES[family]))
    m, ani, seqs = fp.taunt(model)
    src = ValveAnimSource(m, ani, seqs[seq.lower()])
    if fps_src:
        src.fps = float(fps_src)
        src.duration = (src.nframes - 1) / src.fps
    pel = [src.pose(t)['Pelvis'][1] for t in np.arange(0, src.duration, 0.1)]
    span = max(np.ptp([p[0] for p in pel]), np.ptp([p[1] for p in pel]))
    rt = Retargeter(src, valve, root_motion=True, root_axes='full' if span <= 30 else 'vertical')
    return valve, src, rt


def view(json_path, family, model, seq, mesh, carrier, times, out, title, fps=30, extra_meshes=()):
    valve, src, rt = build_rt(family, model, seq)
    js = json.load(open(json_path))
    fd = js['FrameData']
    ent = [f['BoneInfo'][carrier] for f in fd]
    ts = [i / float(fps) for i in range(len(fd))]
    world = ep.World(rt)
    V, N, F = mesh.arrays()
    n = len(times)
    fig, axes = plt.subplots(2, n, figsize=(2.3 * n, 6.2))
    for c, t in enumerate(times):
        WR, WP = world.at(t)
        R, p = ep.replay_carrier(valve, rt, ent, ts, carrier, t, world)
        pts = (V @ R.T) + p
        for row, (hx, vx, name) in enumerate([(1, 2, 'front'), (0, 2, 'side')]):
            ax = axes[row, c]
            for chain in CH:
                q = np.array([WP[valve.bone(k)] for k in chain])
                ax.plot(q[:, hx], q[:, vx], '-', color='tab:blue', lw=1.6)
            ax.scatter(pts[::3, hx], pts[::3, vx], s=0.6, color='tab:orange')
            ax.set_aspect('equal')
            ax.set_xlim(-60, 60) if hx == 1 else ax.set_xlim(-90, 40)
            ax.set_ylim(-5, 175)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title('%s t=%.2fs %s' % (title, t, name), fontsize=7)
    fig.tight_layout()
    fig.savefig(out, dpi=90)
    plt.close(fig)


if __name__ == '__main__':      # python prop_view.py [classd|isd|medic] [folder holding <family>/fn_thoughtiwasdead.json: actmod_out (default) or anim/fn]; needs ACTMOD_EXP_DIR (AM4 Expansion Pack)
    fam = sys.argv[1] if len(sys.argv) > 1 else 'classd'
    root = sys.argv[2] if len(sys.argv) > 2 else 'actmod_out'
    mesh = pg.trumpet()
    jp = os.path.join(root, fam, 'fn_thoughtiwasdead.json')
    view(jp, fam, 'actmodexp:m_ani_01', 'Amod_Fortnite_CanineCronutMix', mesh, ep.CARRIER_LH, [0.4, 1.0, 2.5, 3.5, 3.7, 3.9, 4.05, 4.2, 4.5], 'tiwd_%s_view.png' % fam, 'trumpet')
    print('written')
