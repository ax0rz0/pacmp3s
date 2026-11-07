"""audio-derived chord segments for the left hand (shapes D A G C E B), and how far a constant-tempo picking loop drifts from the recording's beats"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PC_SHAPE = {0: 'C', 1: 'C', 2: 'D', 3: 'E', 4: 'E', 5: 'C', 6: 'B', 7: 'G', 8: 'A', 9: 'A', 10: 'B', 11: 'B'}
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def shape_of(name):
    root = name[:2] if len(name) > 1 and name[1] == '#' else name[:1]
    return PC_SHAPE[NAMES.index(root)]


def segments(min_beats=2, path=None):
    d = json.load(open(path or os.path.join(HERE, 'out', 'song_chords_raw.json')))
    beats = np.array(d['beats'])
    shp = [shape_of(n) for n in d['names']]
    runs = []                                   # [shape, first beat index, count]
    for i, s in enumerate(shp):
        if runs and runs[-1][0] == s:
            runs[-1][2] += 1
        else:
            runs.append([s, i, 1])
    changed = True
    while changed:                              # runs shorter than min_beats are absorbed by the previous run (or the next one at the start)
        changed = False
        for k, r in enumerate(runs):
            if r[2] < min_beats and len(runs) > 1:
                if k > 0:
                    runs[k - 1][2] += r[2]
                else:
                    runs[1][1] = r[1]
                    runs[1][2] += r[2]
                runs.pop(k)
                # merge neighbours that now carry the same shape
                m = []
                for q in runs:
                    if m and m[-1][0] == q[0]:
                        m[-1][2] += q[2]
                    else:
                        m.append(q)
                runs = m
                changed = True
                break
    segs = []
    for s, i, n in runs:
        t0 = 0.0 if i == 0 else float(beats[i])
        t1 = float(beats[min(i + n, len(beats) - 1)])
        segs.append((t0, t1, s))
    return segs, beats


def main():
    segs, beats = segments()
    print('%d segments; shapes used: %s' % (len(segs), sorted(set(s[2] for s in segs))))
    print(' '.join('%s@%.1f' % (s, t0) for t0, t1, s in segs))
    k = np.arange(len(beats))
    for per in (1.800, 1.8004, 1.812):
        half = per / 2.0
        err = beats - (beats[0] + k * half)
        print('constant beat %.4f s: drift min %.2f max %.2f s (rms %.2f)' % (half, err.min(), err.max(), np.sqrt(np.mean(err ** 2))))
    # best constant period by least squares
    A = np.vstack([k, np.ones_like(k)]).T
    sl, ic = np.linalg.lstsq(A, beats, rcond=None)[0]
    err = beats - (sl * k + ic)
    print('least squares: beat %.4f s (%.2f BPM), first beat at %.3f s, residual min %.2f max %.2f rms %.3f' % (sl, 60 / sl, ic, err.min(), err.max(), np.sqrt(np.mean(err ** 2))))


if __name__ == '__main__':
    main()
