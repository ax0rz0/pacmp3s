"""Overlay render: the source Fortnite animation (blue) vs the retargeted job-model skeleton (red) at four moments."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import make_fn_pack as fp
from retarget import Retargeter, Valve, ValveAnimSource
from mdl_anim import load_model

CH = [['Pelvis', 'Spine', 'Spine1', 'Spine2', 'Spine4', 'Neck1', 'Head1'], ['Spine4', 'R_Clavicle', 'R_UpperArm', 'R_Forearm', 'R_Hand', 'R_Finger2'],
      ['Spine4', 'L_Clavicle', 'L_UpperArm', 'L_Forearm', 'L_Hand', 'L_Finger2'], ['Pelvis', 'R_Thigh', 'R_Calf', 'R_Foot', 'R_Toe0'],
      ['Pelvis', 'L_Thigh', 'L_Calf', 'L_Foot', 'L_Toe0']]


def run(keys, path, family='classd', per=4):
    valve = Valve(load_model(fp.FAMILIES[family]))
    fig, axes = plt.subplots(len(keys) * 2, per, figsize=(2.6 * per, 3.3 * len(keys) * 2))
    for r, key in enumerate(keys):
        spec = key if isinstance(key, tuple) else [s for s in fp.SPECS if s[0] == key][0]
        m, ani, seqs = fp.taunt(spec[2])
        src = ValveAnimSource(m, ani, seqs[spec[3].lower()])
        rt = Retargeter(src, valve, root_motion=True)
        T = min(src.duration, 10.2)
        for c in range(per):
            t = T * (c + 0.5) / per
            _, _, (WR, WP), _ = rt.solve(t)
            cur = src.pose(t)
            hip_s = cur['Pelvis'][1]; hip_v = WP[valve.bone('Pelvis')]
            for row, (hx, title) in enumerate([(1, 'front'), (0, 'side')]):
                ax = axes[r * 2 + row, c]
                for ch in CH:
                    ps = np.array([(cur[n][1] - hip_s) * rt.root_scale + hip_v for n in ch])
                    ax.plot(ps[:, hx], ps[:, 2], '-o', color='tab:blue', lw=2.2, ms=3, alpha=0.75)
                    pv = np.array([WP[valve.bone(n)] for n in ch])
                    ax.plot(pv[:, hx], pv[:, 2], '--s', color='tab:red', lw=1.3, ms=3)
                ax.set_aspect('equal'); ax.set_xlim(-45, 45); ax.set_ylim(-2, 80); ax.set_xticks([]); ax.set_yticks([])
                ax.set_title('%s t=%.1fs %s' % (spec[1], t, title), fontsize=7)
    fig.suptitle('blue = Fortnite animation as authored   red dashed = retargeted %s skeleton (what pac will pose)' % family, fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)


if __name__ == '__main__':
    import make_actmod_emotes as am
    run([(k, t, model, seq) for k, t, model, seq, _, _ in am.SPECS], sys.argv[1] if len(sys.argv) > 1 else 'fn_preview.png')
