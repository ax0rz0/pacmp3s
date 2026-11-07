"""build everything the guitar pac needs for the ethics rig: the two animation layers (JSON), the proxy expression that scrubs layer A along the recording's beats, a check of that expression"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guitar_layers as gl
import song_chords as sc
import song_warp as sw
from guitar_anim import Rigged

SONG_SECONDS = 230.5045
KNOT_EVERY = 8                    # beats between the knots of the tempo curve (phase error <= 0.06 beat)
OUT = os.path.join(HERE, 'out')


def build(family='ethics'):
    G = Rigged(family)
    jsA, infoA = gl.layer_a(G)
    segs, beats = sc.segments()
    jsB, infoB = gl.layer_b(G, segs, total=SONG_SECONDS)
    kt, ki = sw.piecewise(beats, KNOT_EVERY)
    terms = sw.hinge_terms(kt, ki)
    expr = sw.expression(terms)
    return G, jsA, infoA, jsB, infoB, expr, terms, beats


def phase_of(terms, t_since_show):
    return sum(a * max(t_since_show - t, 0.0) for a, t in terms)


def check_expression(expr, terms, beats):
    """evaluate the written expression the way the old build does (a Lua chunk, `timeex()` and `max` in scope) and compare with the beats"""
    env = {'max': max, 'min': min, 'timeex': None}
    err = []
    for k, b in enumerate(beats):
        env['timeex'] = lambda b=b: b + sw.LEAD
        v = eval(expr, {'__builtins__': {}}, env)
        err.append(v - k / 2.0)
    err = np.array(err)
    # the expression must also be 0 before the first beat and constant after the last one
    env['timeex'] = lambda: 0.0
    v0 = eval(expr, {'__builtins__': {}}, env)
    env['timeex'] = lambda: 400.0
    v1 = eval(expr, {'__builtins__': {}}, env)
    env['timeex'] = lambda: 600.0
    v2 = eval(expr, {'__builtins__': {}}, env)
    return err, v0, v1, v2


def main():
    G, jsA, infoA, jsB, infoB, expr, terms, beats = build()
    os.makedirs(OUT, exist_ok=True)
    for nm, js in (('A', jsA), ('B', jsB)):
        s = json.dumps(js, separators=(',', ':'))
        open(os.path.join(OUT, 'guitar_%s.json' % nm), 'w', newline='\n').write(s)
        print('layer %s: %d frames, %d bones, %d bytes, RestartFrame %s' % (nm, len(js['FrameData']), len(js['FrameData'][0]['BoneInfo']), len(s), js.get('RestartFrame')))
    print('right hand fit: rms %.2f (elbow swing, wrist flexion, palm roll = %s)' % (infoA['rms'], np.round(infoA['fit'], 1)))
    print('left hand fit rms per shape:', infoB['rms'])
    print('chord segments: %d, key frames: %d, shortest hold %.2f s' % (len(infoB['segs']), len(infoB['keys']), min(b[0] - a[0] for a, b in zip(infoB['keys'][:-1], infoB['keys'][1:]))))
    print('proxy expression: %d terms, %d chars' % (len(terms), len(expr)))
    open(os.path.join(OUT, 'guitar_offset_expr.txt'), 'w').write(expr)
    err, v0, v1, v2 = check_expression(expr, terms, beats)
    print('expression vs beat grid: max |phase error| %.3f cycles (%.3f beats), rms %.3f beats; at show %.3f, at 400 s %.3f, at 600 s %.3f (should be 0 and %.1f)' % (np.abs(err).max(), np.abs(err).max() * 2, np.sqrt(np.mean(err ** 2)) * 2, v0, v1, v2, (len(beats) - 1) / 2.0))
    # key frame timeline: frame arrival times (0.25 s ease in + durations) against the chord segments
    t = 0.25
    arr = [t]
    for fr in jsB['FrameData'][1:]:
        t += 1.0 / fr['FrameRate']
        arr.append(t)
    print('last frame arrives at %.2f s after the toggle (audio file length %.2f s)' % (arr[-1], SONG_SECONDS + sw.LEAD))


if __name__ == '__main__':
    main()
