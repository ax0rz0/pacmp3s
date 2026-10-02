"""Keyframe thinning for pac custom_animation data.

pac interpolates the Euler numbers of two neighbouring frames linearly (LerpAngle / LerpVector) and every frame carries its own
FrameRate, so a frame can be dropped whenever linear interpolation between the kept neighbours still reproduces it. Doing that
adaptively (dense around fast or gimbal-prone motion, sparse elsewhere) shrinks the files a lot and keeps the same error model.
"""
import numpy as np


def eulers_to_R(E):
    """(...,3) degrees (pitch, yaw, roll) -> (...,3,3), Source AngleMatrix = Rz(yaw) Ry(pitch) Rx(roll)."""
    E = np.asarray(E, dtype=float)
    p, y, r = np.radians(E[..., 0]), np.radians(E[..., 1]), np.radians(E[..., 2])
    cp, sp, cy, sy, cr, sr = np.cos(p), np.sin(p), np.cos(y), np.sin(y), np.cos(r), np.sin(r)
    R = np.empty(E.shape[:-1] + (3, 3))
    R[..., 0, 0] = cy * cp; R[..., 0, 1] = cy * sp * sr - sy * cr; R[..., 0, 2] = cy * sp * cr + sy * sr
    R[..., 1, 0] = sy * cp; R[..., 1, 1] = sy * sp * sr + cy * cr; R[..., 1, 2] = sy * sp * cr - cy * sr
    R[..., 2, 0] = -sp;     R[..., 2, 1] = cp * sr;                R[..., 2, 2] = cp * cr
    return R


def rot_err_deg(Ra, Rb):
    c = (np.einsum('...ij,...ij->...', Ra, Rb) - 1.0) / 2.0
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def thin(E, trans, tol_rot=0.8, tol_pos=0.4, max_seg=12):
    """E: (N, B, 3) continuous Euler triples (degrees), trans: (N, 3) pelvis offsets or None.
    Returns the kept frame indices (always including 0 and N-1)."""
    N = E.shape[0]
    tol = np.broadcast_to(np.asarray(tol_rot, dtype=float), (E.shape[1],))[None, :]
    R = eulers_to_R(E)
    keys = [0]
    a = 0
    while a < N - 1:
        best = a + 1
        for b in range(a + 2, min(N - 1, a + max_seg) + 1):
            ks = np.arange(a + 1, b)
            f = ((ks - a) / (b - a))[:, None, None]
            Elerp = (1 - f) * E[a][None] + f * E[b][None]
            err = (rot_err_deg(eulers_to_R(Elerp), R[a + 1:b]) / tol).max()   # per-bone tolerance, normalised
            if err > 1.0:
                break
            if trans is not None:
                tl = (1 - f[:, :, 0]) * trans[a][None] + f[:, :, 0] * trans[b][None]
                if np.linalg.norm(tl - trans[a + 1:b], axis=1).max() > tol_pos:
                    break
            best = b
        keys.append(best)
        a = best
    return keys
