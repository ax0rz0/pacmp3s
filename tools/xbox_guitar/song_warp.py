"""tempo curve of the recording as a piecewise-linear map  time -> pattern cycles (one cycle = 2 beats = one picking pattern), written as a sum of hinge terms for a pac proxy expression"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import song_analysis as sa

LEAD = 0.25                  # seconds of silence in front of the audio file (pac's ease-in of the first animation frame)


def refine_beats(beats, env, hop=sa.HOP, sr=sa.SR, win=0.12):
    """snap each tracker beat to the strongest onset within +-win seconds (keeps order)"""
    fr = hop / sr
    out = []
    for b in beats:
        i0 = int(max(0, (b - win) / fr))
        i1 = int(min(len(env) - 1, (b + win) / fr))
        j = i0 + int(np.argmax(env[i0:i1 + 1]))
        out.append(j * fr)
    return np.array(out)


def piecewise(beats, step, T0=None):
    """knots every `step` beats (indices 0, step, 2 step, ...), the last knot at the final beat; returns knot times and knot beat indices"""
    idx = list(range(0, len(beats), step))
    if idx[-1] != len(beats) - 1:
        idx.append(len(beats) - 1)
    return np.array([beats[i] for i in idx]), np.array(idx, float)


def warp_error(beats, step):
    kt, ki = piecewise(beats, step)
    pred = np.interp(beats, kt, ki)
    return pred - np.arange(len(beats))                 # in beats


def hinge_terms(kt, ki, cycles_per_beat=0.5, lead=LEAD):
    """phase(t) = sum a_j * max(t - tj, 0), t = time since the toggle; phase counts pattern cycles, 0 before the first knot and constant after the last one"""
    slopes = np.diff(ki) * cycles_per_beat / np.diff(kt)           # cycles per second in each interval
    terms = []
    prev = 0.0
    for j, s in enumerate(slopes):
        terms.append((float(s - prev), float(kt[j] + lead)))
        prev = s
    terms.append((float(-prev), float(kt[-1] + lead)))
    return terms


def expression(terms, var='timeex()'):
    return ' + '.join('%.6g * max(%s - %.4f, 0)' % (a, var, t) for a, t in terms).replace('+ -', '- ')


def main():
    x = sa.decode()
    env, tt = sa.onset_envelope(x)
    beats0 = np.load(os.path.join(HERE, 'out', 'song_beats.npy'))
    print('first beats', np.round(beats0[:10], 2), ' last', np.round(beats0[-4:], 2))
    # envelope strength at the tracked beats vs half a beat later
    fr = sa.HOP / sa.SR
    def at(ts):
        return np.mean([env[min(int(t / fr), len(env) - 1)] for t in ts])
    print('mean onset strength at beats %.3f, half a beat after %.3f, quarter after %.3f' % (at(beats0), at(beats0 + 0.45), at(beats0 + 0.22)))
    beats = beats0                      # the tracker's beats are smoother than onset-snapped ones (interval std 0.02 s vs 0.07 s) and already sit on the onsets
    iv = np.diff(beats)
    bad = np.where((iv < 0.7) | (iv > 1.1))[0]
    print('intervals outside 0.7..1.1 s:', len(bad))
    for step in (4, 8, 12, 16, 24):
        e = warp_error(beats, step)
        print('knots every %2d beats: %2d terms, phase error max %.2f beats (%.2f s), rms %.2f beats' % (step, len(range(0, len(beats), step)) + 1, np.abs(e).max(), np.abs(e).max() * 0.9, np.sqrt(np.mean(e ** 2))))
    for step in (8, 12):
        kt, ki = piecewise(beats, step)
        terms = hinge_terms(kt, ki)
        ex = expression(terms)
        print('step %d: %d hinge terms, expression %d chars; phase at the end %.2f cycles' % (step, len(terms), len(ex), sum(a * max(kt[-1] + LEAD + 5 - t, 0) for a, t in terms)))


if __name__ == '__main__':
    main()
