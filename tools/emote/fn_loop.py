"""Automatic loop-window finder for emotes (world-rotation closure plus per-frame angular-velocity continuity)."""
import numpy as np

BODY = ['Pelvis', 'Spine', 'Spine1', 'Spine2', 'Neck1', 'Head1', 'R_Clavicle', 'L_Clavicle', 'R_UpperArm', 'L_UpperArm', 'R_Forearm', 'L_Forearm',
        'R_Hand', 'L_Hand', 'R_Thigh', 'L_Thigh', 'R_Calf', 'L_Calf', 'R_Foot', 'L_Foot']


def rot_diff(Ra, Rb):
    c = (np.einsum('...ij,...ij->...', Ra, Rb) - 1) / 2
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def find_loop(src, max_sec=10.2, min_loop=0.5, tol=0.75):
    """Return dict(s, e, closure, vel, score, fps): loop restart frame s and the last frame e (source frames) of the clip to play.
    Among all windows within `tol` of the best score the longest one wins (more of the emote is kept)."""
    fps = src.fps
    n = src.nframes
    emax = min(n - 1, int(round(max_sec * fps)))
    keys = [k for k in BODY if k in src.keys]
    R = np.array([[src.pose(f / fps)[k][0] for k in keys] for f in range(emax + 2 if emax + 2 <= n else n)])    # (F, B, 3, 3)
    F = len(R)
    step = np.array([rot_diff(R[f], R[min(f + 1, F - 1)]) for f in range(F)])                                   # (F, B) angular step per frame
    minf = int(round(min_loop * fps))
    cands = []
    for s in range(0, emax - minf + 1):
        es = np.arange(s + minf, emax + 1)
        clo = rot_diff(R[s][None], R[es]).max(axis=1)
        vel = np.abs(step[s][None] - step[es]).mean(axis=1)
        sc = clo + 2.0 * vel
        for e, c, v, k in zip(es, clo, vel, sc):
            cands.append((k, c, v, s, int(e)))
    best = min(c[0] for c in cands)
    near = [c for c in cands if c[0] <= best + tol]
    k, c, v, s, e = max(near, key=lambda x: (x[4] - x[3], -x[3]))
    return dict(s=s, e=e, closure=float(c), vel=float(v), score=float(k), fps=fps, best=float(best), nframes=n)
