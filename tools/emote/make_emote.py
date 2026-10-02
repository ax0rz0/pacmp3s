"""Convert a Mixamo FBX animation into a PAC3 custom_animation JSON for ValveBiped playermodels.

python make_emote.py <anim.fbx> --name samba [--fps 30] [--start S] [--end S] [--ease-in 0.25]
                     [--interp linear|cosine] [--root-motion] [--model models/...mdl] [--out DIR] [--preview]
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mdl_anim import Mdl, Gma, SCP_GMA, load_model, angle_between
from fbx_anim import Scene, KTIME
from retarget import (Retargeter, Valve, MixamoSource, angles_matrix, source_angles, norm, GAME_FROM_MIX, continuous)

DEFAULT_MODEL = 'models/frostbyte/ia/internalsecurity_erdim.mdl'


def sample(rt, times, root_motion):
    frames = []
    prev = None
    for t in times:
        ang, trans, ach, want = rt.frame_angles(t, prev)
        prev = ang
        frames.append((ang, trans))
    return frames


def to_json(rt, frames, fps, ease_in, interp, restart, name, dec=1):
    v = rt.v
    data = []
    for i, (ang, trans) in enumerate(frames):
        info = {}
        for b, a in ang.items():
            e = {'RR': round(float(a[0]), dec), 'RU': round(float(a[1]), dec), 'RF': round(float(a[2]), dec)}
            if rt.root_motion and trans is not None and v.m.names[b].endswith('Pelvis'):
                e['MF'] = round(float(trans[0]), dec); e['MR'] = round(float(-trans[1]), dec); e['MU'] = round(float(trans[2]), dec)
            info[v.m.names[b]] = e
        data.append({'FrameRate': (1.0 / ease_in if (i == 0 and ease_in > 0) else float(fps)), 'BoneInfo': info})
    out = {'Type': 'sequence', 'Interpolation': interp, 'FrameData': data, 'Name': name,
           'Notes': 'claude skill made by ax0rz0'}
    if restart:
        out['RestartFrame'] = restart
    return out


def simulate_pac(rt, js, fps, ease_in, probe_steps=4):
    """Replay the JSON exactly like pac's linear/cosine interpolation and compare with the exact retarget."""
    v = rt.v
    fd = js['FrameData']; n = len(fd)
    bones = [v.m.index[k] for k in fd[0]['BoneInfo']]
    names = {b: v.m.names[b] for b in bones}
    def euler(i, b):
        e = fd[i]['BoneInfo'].get(names[b])
        return np.array([e['RR'], e['RU'], e['RF']]) if e else np.zeros(3)
    worst = {}; allerr = []
    for i in range(1, n):                     # transition frame i-1 -> i (0-based): data index
        prev = i - 1
        t0 = (i - 1) / fps; t1 = i / fps
        for k in range(1, probe_steps):
            d = k / probe_steps
            tt = t0 + d * (t1 - t0)
            if js['Interpolation'] == 'cosine':
                dd = (1 - math.cos(d * math.pi)) / 2
            else:
                dd = d
            M = {}
            for b in bones:
                e = (1 - dd) * euler(prev, b) + dd * euler(i, b)
                M[b] = angles_matrix(e)
            # achieved world from simulated M
            WR = [None] * v.m.n
            for b in range(v.m.n):
                p = v.parent[b]
                PR = WR[p] if p >= 0 else np.eye(3)
                WR[b] = PR @ v.Lr[b] @ M.get(b, np.eye(3))
            _, _, (XR, XP), want = rt.solve(tt)
            for b in bones:
                err = angle_between(WR[b], XR[b])
                allerr.append(err)
                worst[names[b]] = max(worst.get(names[b], 0.0), err)
    return worst, np.array(allerr)


def euler_stats(frames):
    mx = {}
    for ang, _ in frames:
        for b, a in ang.items():
            mx[b] = max(mx.get(b, 0), abs(a[0]))
    return mx


def preview(rt, js, times, path, fps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    v = rt.v; sc = rt.src.sc
    chains_v = [['Pelvis', 'Spine', 'Spine1', 'Spine2', 'Spine4', 'Neck1', 'Head1'],
                ['Spine4', 'R_Clavicle', 'R_UpperArm', 'R_Forearm', 'R_Hand', 'R_Finger2'],
                ['Spine4', 'L_Clavicle', 'L_UpperArm', 'L_Forearm', 'L_Hand', 'L_Finger2'],
                ['Pelvis', 'R_Thigh', 'R_Calf', 'R_Foot', 'R_Toe0'], ['Pelvis', 'L_Thigh', 'L_Calf', 'L_Foot', 'L_Toe0']]
    chains_m = [['Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head', 'HeadTop_End'],
                ['Spine2', 'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand', 'RightHandMiddle1'],
                ['Spine2', 'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand', 'LeftHandMiddle1'],
                ['Hips', 'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase'], ['Hips', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase']]
    nrow = len(times)
    fig, axes = plt.subplots(nrow, 2, figsize=(7.2, 3.4 * nrow))
    axes = np.atleast_2d(axes)
    for r, t in enumerate(times):
        _, _, (WR, WP), want = rt.solve(t)
        W = sc.world_matrices(int(round(t * KTIME)))
        cur = {}
        for ch in chains_m:
            for nm in ch:
                M4 = W[sc.by_name['mixamorig:' + nm]['id']]
                cur[nm] = GAME_FROM_MIX @ M4[:3, 3]
        hip_v = WP[v.bone('Pelvis')]; hip_m = cur['Hips']
        s = rt.root_scale
        for c, (hx, hy, title) in enumerate([(1, 2, 'front (screen right = character left)'), (0, 2, 'side (screen right = forward)')]):
            ax = axes[r, c]
            for ch in chains_m:
                pts = np.array([(cur[n] - hip_m) * s + hip_v for n in ch])
                ax.plot(pts[:, hx], pts[:, hy], '-o', color='tab:blue', lw=2, ms=3, alpha=0.8)
            for ch in chains_v:
                pts = np.array([WP[v.bone(n)] for n in ch])
                ax.plot(pts[:, hx], pts[:, hy], '--s', color='tab:red', lw=1.4, ms=3)
            ax.set_aspect('equal'); ax.set_xlim(-45, 45); ax.set_ylim(-2, 80); ax.grid(alpha=0.25)
            ax.set_title('t=%.2fs %s' % (t, title), fontsize=8)
    fig.suptitle('blue = Mixamo (scaled)   red dashed = ValveBiped retarget (as pac would pose it)', fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fbx')
    ap.add_argument('--name', default=None)
    ap.add_argument('--fps', type=float, default=30)
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--end', type=float, default=None)
    ap.add_argument('--ease-in', type=float, default=0.25)
    ap.add_argument('--interp', default='linear', choices=['linear', 'cosine'])
    ap.add_argument('--root-motion', action='store_true')
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--out', default='.')
    ap.add_argument('--preview', action='store_true')
    ap.add_argument('--no-loop', action='store_true')
    ap.add_argument('--decimals', type=int, default=1)
    ap.add_argument('--root-frame', default='parent', choices=['parent', 'bone'])
    a = ap.parse_args()
    name = a.name or os.path.splitext(os.path.basename(a.fbx))[0].lower().replace(' ', '_')
    sc = Scene(a.fbx)
    dur = sc.duration()
    end = min(a.end if a.end else dur, dur)
    mdl = load_model(a.model)
    v = Valve(mdl)
    rt = Retargeter(MixamoSource(sc), v, root_motion=a.root_motion, root_frame=a.root_frame)
    n = int(round((end - a.start) * a.fps)) + 1
    times = [a.start + i / a.fps for i in range(n)]
    print('clip %.2fs-%.2fs -> %d frames @ %g fps | base seq0 = %s | model %s' % (a.start, end, n, a.fps, v.seq0, a.model))
    frames = sample(rt, times, a.root_motion)
    # loop closure: how far is the last pose from the first (world rotation of mapped bones)?
    A = rt.solve(times[0])[3]; B = rt.solve(times[-1])[3]
    closure = max(angle_between(A[b], B[b]) for b in A)
    print('loop closure: worst bone differs %.2f deg between first and last frame' % closure)
    restart = None if a.no_loop else 2
    js = to_json(rt, frames, a.fps, a.ease_in, a.interp, restart, name, a.decimals)
    worst, allerr = simulate_pac(rt, js, a.fps, a.ease_in)
    print('pac playback simulation (%s, %d probes): mean err %.3f deg, p99 %.3f, max %.3f' % (a.interp, len(allerr), allerr.mean(), np.percentile(allerr, 99), allerr.max()))
    bad = sorted(worst.items(), key=lambda kv: -kv[1])[:5]
    print('  worst bones:', ', '.join('%s %.2f' % (k.replace('ValveBiped.Bip01_', ''), e) for k, e in bad))
    ps = euler_stats(frames)
    near = [(v.m.names[b].replace('ValveBiped.Bip01_', ''), round(p, 1)) for b, p in ps.items() if p > 75]
    print('bones whose |pitch| exceeds 75 deg somewhere (gimbal-prone):', near)
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, name + '.json')
    with open(path, 'w', newline='\n') as f:
        json.dump(js, f, separators=(',', ':'))
    print('wrote %s (%d bytes, %d frames, %d bones)' % (path, os.path.getsize(path), len(js['FrameData']), len(js['FrameData'][0]['BoneInfo'])))
    if a.preview:
        pt = [times[0], times[len(times) // 4], times[len(times) // 2], times[3 * len(times) // 4]]
        preview(rt, js, pt, os.path.join(a.out, name + '_preview.png'), a.fps)
        print('preview ->', os.path.join(a.out, name + '_preview.png'))


if __name__ == '__main__':
    main()
