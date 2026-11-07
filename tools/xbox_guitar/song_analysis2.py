"""second stage: beat grid at ~0.906 s, chroma per beat, chord roots per beat, where the chords change"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import song_analysis as sa

MAJ = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0], float)
MIN = np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], float)


def chord_per_beat(t, C, B, beats):
    out = []
    for i in range(len(beats) - 1):
        m = (t >= beats[i]) & (t < beats[i + 1])
        if not m.any():
            m = (t >= beats[i] - 0.1) & (t < beats[i + 1] + 0.1)
        c = C[m].mean(axis=0) if m.any() else np.zeros(12)
        b = B[m].mean(axis=0) if m.any() else np.zeros(12)
        c = c / (np.linalg.norm(c) + 1e-9)
        b = b / (np.linalg.norm(b) + 1e-9)
        best = None
        for r in range(12):
            for q, T in (('', MAJ), ('m', MIN)):
                tpl = np.roll(T, r)
                s = float(np.dot(c, tpl) / np.linalg.norm(tpl)) + 0.45 * float(b[r])
                if best is None or s > best[0]:
                    best = (s, r, q)
        out.append((best[1], best[2], best[0]))
    return out


def main():
    x = sa.decode()
    env, tt = sa.onset_envelope(x)
    beats = sa.beat_track(env, 0.906)
    iv = np.diff(beats)
    print('beats: %d, first %.2f s, last %.2f s, interval median %.3f mean %.3f std %.3f  (BPM %.1f)' % (len(beats), beats[0], beats[-1], np.median(iv), iv.mean(), iv.std(), 60 / np.median(iv)))
    print('interval per 20 beats:', ' '.join('%.3f' % iv[i:i + 20].mean() for i in range(0, len(iv), 20)))
    t, C, B, tun = sa.chroma_frames(x)
    print('tuning offset %.2f semitones (+ = sharp of A440)' % tun)
    ch = chord_per_beat(t, C, B, beats)
    names = [sa.NAMES[r] + q for r, q, s in ch]
    print('chord per beat (beat index: name), bars of 4 starting at beat 0:')
    for i in range(0, len(names), 16):
        print('  %3d: %s' % (i, ' | '.join(' '.join('%-3s' % n for n in names[j:j + 4]) for j in range(i, min(i + 16, len(names)), 4))))
    chg = [i for i in range(1, len(names)) if names[i] != names[i - 1]]
    print('changes at beat index mod 4:', np.bincount(np.array(chg) % 4, minlength=4), ' mod 2:', np.bincount(np.array(chg) % 2, minlength=2))
    np.save(os.path.join(HERE, 'out', 'song_beats.npy'), beats)
    json.dump({'names': names, 'beats': beats.tolist()}, open(os.path.join(HERE, 'out', 'song_chords_raw.json'), 'w'))


if __name__ == '__main__':
    main()
