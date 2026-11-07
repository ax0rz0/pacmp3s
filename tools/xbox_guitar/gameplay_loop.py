"""find a good loop in the gameplay clip: start / length (seconds) where the frame at the end looks most like the frame at the start (small grey thumbnails, a few frames compared on both sides),
away from the rating card at the start and the pre-order card at the end.  Prints the best few; writes out/game_loop.json with the best one."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.environ.get('XBOX_WORK', os.path.dirname(HERE))
SRC = os.path.join(SP, 'xbox_real', 'dl', 'nfsrivals', 'nfsrivals.mp4')
FPS = 8
W, H = 96, 54


def thumbs(src=SRC, fps=FPS):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vf', 'fps=%d,scale=%d:%d:flags=area,format=gray' % (fps, W, H), '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8)
    n = len(a) // (W * H)
    return a[:n * W * H].reshape(n, H, W).astype(np.float32)


def main(lo_s=8.0, hi_s=86.0, min_len=5.5, max_len=7.0):
    t = thumbs()
    n = len(t)
    best = []
    for L in np.arange(min_len, max_len + 1e-6, 1.0 / FPS):
        Lf = int(round(L * FPS))
        for i in range(int(lo_s * FPS), int(hi_s * FPS) - Lf):
            j = i + Lf
            d = 0.0
            for k in (-2, -1, 0, 1, 2):                     # frames around the cut: the end looks like the start, and the frame after the end like the frame after the start
                d += float(np.abs(t[i + k] - t[j + k]).mean())
            motion = float(np.abs(t[i + 1] - t[i]).mean())  # prefer moving footage over a held frame
            best.append((d / 5.0, i / FPS, Lf / FPS, motion))
    best.sort()
    print('%d frames at %d fps; best loops (frame difference, start s, length s, motion):' % (n, FPS))
    seen = []
    for d, s, L, m in best:
        if any(abs(s - q) < 4.0 for q in seen):
            continue
        seen.append(s)
        print('  diff %.2f  start %.3f  length %.3f  motion %.2f' % (d, s, L, m))
        if len(seen) >= 8:
            break
    d, s, L, m = [b for b in best if not any(abs(b[1] - q) < 0 for q in [])][0]
    json.dump({'start': s, 'length': L, 'diff': d}, open(os.path.join(HERE, 'out', 'game_loop.json'), 'w'))


if __name__ == '__main__':
    main()
