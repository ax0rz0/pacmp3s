"""the two guitar animation layers (see guitar_anim.py): A = body + right hand, a loop of one picking pattern; B = the left hand over the whole song as sparse keyframes"""
import collections
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik
import thr_core as tc
import guitar_scene as gs
import midi_guitar as mg
from guitar_anim import (STYLE, PATTERN_BEATS, PLUCK_BEATS, Rigged, nominal, fit_hand, rot_about)

STR_X = [-2.1, -1.26, -0.42, 0.42, 1.26, 2.1]              # strings 6..1 across the fretboard in guitar-local x (bass side up)


def pt(strg, fret, y=-2.7):
    return np.array([STR_X[6 - strg], y, gs.fret_z(fret) - 0.9])


LEFT_SHAPES = {       # chord root -> fingertips (finger id: point on the fretboard); the ethics rig has thumb 0, index 1 and middle 2 only
    'D': {1: pt(3, 2), 2: pt(1, 2)},
    'A': {1: pt(4, 2), 2: pt(2, 2)},
    'G': {1: pt(5, 2), 2: pt(1, 3)},
    'C': {1: pt(2, 1), 2: pt(4, 2)},
    'E': {1: pt(3, 1), 2: pt(5, 2)},
    'B': {1: pt(3, 3), 2: pt(1, 4)},
}
LEFT_POLE = np.array([-0.3, 0.5, -0.8])
RIGHT_POLE = np.array([-0.4, -0.4, -0.8])
LEFT_WRIST_OFF = np.array([2.5, 7.0, -8.0])         # the fretting wrist sits behind the neck and well below the fingers (scan: fit error 0.8..1.1 units, was 2.8)
RIGHT_WRIST = np.array([-0.5, -8.0, 9.0])          # the picking wrist hovers over the lower edge of the sound hole (a wrist further up the board leaves the fingers pointing along the neck)
LEFT_PREFIXES = ('L_UpperArm', 'L_Forearm', 'L_Hand', 'L_Finger', 'Anim_Attachment_LH')
_cache = {}


def short(nm):
    return nm.replace('ValveBiped.Bip01_', '').replace('ValveBiped.', '')


def left_pose(G, P, root, iters=110):
    key = (G.key, root)
    if key not in _cache:
        tg = LEFT_SHAPES[root]
        c = np.mean(list(tg.values()), axis=0)
        wrist = G.to_world(P, c + LEFT_WRIST_OFF)
        targets = {fid: G.to_world(P, loc) for fid, loc in tg.items()}
        Q, rms, x, miss = fit_hand(G, P, 'L', wrist, LEFT_POLE, targets, claw=0.85, fm={0: 0.25}, iters=iters)
        _cache[key] = ({k: v for k, v in Q.items() if k.startswith('l_')}, rms)
    return _cache[key]


def right_rest(G, P, iters=140):
    tg = {0: np.array([-1.9, -3.5, 17.0]), 1: np.array([0.4, -3.5, 16.6]), 2: np.array([1.7, -3.5, 16.6])}
    wrist = G.to_world(P, RIGHT_WRIST)
    targets = {fid: G.to_world(P, loc) for fid, loc in tg.items()}
    Q, rms, x, miss = fit_hand(G, P, 'R', wrist, RIGHT_POLE, targets, claw=0.6, fm={0: 0.8, 1: 0.9, 2: 0.9}, iters=iters)
    return Q, rms, x


def bump(x):
    return math.sin(math.pi * min(max(x, 0.0), 1.0))


def pluck_curl(beat_in_pattern, dur_beats=0.4):
    """curl added to each finger at this moment of the pattern (beats since the pattern started)"""
    out = {0: 0.0, 1: 0.0, 2: 0.0}
    for b, fingers in PLUCK_BEATS:
        for f in fingers:
            fid = 2 if f >= 2 else f
            x = (beat_in_pattern - b) / dur_beats
            if 0.0 <= x <= 1.0:
                out[fid] = max(out[fid], bump(x))
    return out


def layer_a(G, TS=1.0, name='guitar_play'):
    rig, arms = G.rig, G.arms
    T = PATTERN_BEATS * mg.SPB * TS
    n = int(round(T * 30))
    fps = n / T
    P0 = nominal()
    Qr, rms_r, x_r = right_rest(G, P0)
    phi, wflex, proll = float(x_r[0]), float(np.clip(x_r[1], -50, 70)), float(x_r[2])      # elbow swing about the shoulder-wrist axis, wrist flexion, palm roll of the best fit
    base = {k: v for k, v in Qr.items() if k.startswith('r_')}
    left_rest = {k: v for k, v in P0.items() if k.startswith('l_')}

    def pose(t):
        b = (t / (mg.SPB * TS)) % PATTERN_BEATS                       # beats into the pattern
        ph = 2 * math.pi * b / PATTERN_BEATS
        P = nominal()
        P['croll'] += 1.8 * math.sin(ph)
        P['pyaw'] += 1.2 * math.sin(ph + 0.5)
        P['hroll'] += 2.5 * math.sin(ph + 1.0)
        P['py'] += 0.5 * math.sin(ph)
        P['hpitch'] += 2.6 * (0.5 + 0.5 * math.cos(2 * math.pi * b / 2.0))        # a nod every two beats
        P['r_fz'] = 1.0 * max(0.0, math.cos(2 * math.pi * b / 2.0)) ** 6          # the right foot taps on the odd beats
        loc = RIGHT_WRIST + np.array([0.7 * math.sin(2 * math.pi * b), 0.35 * math.cos(2 * math.pi * b), 0.0])
        solved = arms.solved(P)
        wrist = G.to_world(P, loc, solved)
        axis = ik.norm(wrist - arms.shoulder(P, 'R'))
        pole = rot_about(RIGHT_POLE, axis, phi)
        out, miss, info = arms.ik(P, 'R', wrist, pole, wflex=wflex, proll=proll, claw=0.6, solved=solved)
        P.update(out)
        curl = pluck_curl(b)
        for fid in (0, 1, 2):
            P['r_fm%d' % fid] = base.get('r_fm%d' % fid, 0.9) + 0.55 * curl[fid] * (0.55 if fid == 0 else 1.0)
        P.update(left_rest)
        return P

    frames = tc.build_frames(rig, pose, [i / fps for i in range(n + 1)], STYLE)
    js = tc.to_json(rig, frames, round(fps, 4), name=name)
    for fr in js['FrameData']:
        fr['BoneInfo'] = {k: v for k, v in fr['BoneInfo'].items() if not short(k).startswith(LEFT_PREFIXES)}
    return js, dict(T=T, n=n, fps=fps, rms=rms_r, pose=pose, fit=(phi, wflex, proll))


def chord_roots():
    import mido
    mid = mido.MidiFile(mg.PATH)
    tr = mid.tracks[3]
    ticks = 0
    byb = collections.defaultdict(list)
    L = 4 * mg.SPB
    for m in tr:
        ticks += m.time
        if m.type == 'note_on' and m.velocity > 0:
            byb[int((ticks / mid.ticks_per_beat * mg.SPB) // L)].append(m.note)
    nb = int(mid.length // L) + 1
    seq = []
    for b in range(nb):
        ns = byb.get(b, [])
        seq.append(mg.NAMES[collections.Counter(n % 12 for n in ns).most_common(1)[0][0]] if ns else None)
    last = 'D'
    for i, r in enumerate(seq):                       # rests keep the previous chord; roots outside the table keep it too
        if r is None or r not in LEFT_SHAPES:
            seq[i] = last
        else:
            last = r
    segs = []
    cur, start = seq[0], 0
    for i, r in enumerate(seq[1:], 1):
        if r != cur:
            segs.append((start * L, i * L, cur))
            cur, start = r, i
    segs.append((start * L, mid.length, cur))
    return segs


def layer_b(G, segs=None, name='guitar_chords', total=None, move=0.24):
    """left hand over the whole song.  segs = [(t0, t1, shape)] in seconds of the song (default: the MIDI's chord roots); the hand arrives on each new chord at t0 (it starts moving `move` s earlier)
    and holds it.  The first frame blends in from the base pose over 0.25 s, which the outfit pays for with 0.25 s of lead silence in the audio; the last two frames hold the final chord."""
    rig = G.rig
    P0 = nominal()
    if segs is None:
        segs = chord_roots()
    poses = {}
    for r in sorted(set(s[2] for s in segs)):
        poses[r], rms = left_pose(G, P0, r)
    keys = []
    for i, (t0, t1, r) in enumerate(segs):
        if i == 0:
            keys.append((0.0, r))
        else:
            keys.append((max(t0 - move, keys[-1][0] + 0.05), segs[i - 1][2]))
            keys.append((t0, r))
    end = total if total is not None else segs[-1][1]
    keys.append((max(end, keys[-1][0] + 0.5), segs[-1][2]))
    times = [k[0] for k in keys]
    lookup = {}
    for t, r in keys:
        lookup[round(t, 6)] = r

    def pose(t):
        P = nominal()
        P.update(poses[lookup[round(t, 6)]])
        return P

    frames = tc.build_frames(rig, pose, times, STYLE)
    js = tc.to_json(rig, frames, 30, name=name, restart=len(times))
    for i, fr in enumerate(js['FrameData']):
        if i > 0:
            fr['FrameRate'] = round(1.0 / max(times[i] - times[i - 1], 1e-3), 4)
        fr['BoneInfo'] = {k: v for k, v in fr['BoneInfo'].items() if short(k).startswith(('L_UpperArm', 'L_Forearm', 'L_Hand', 'L_Finger'))}
    return js, dict(keys=keys, segs=segs, rms={r: round(left_pose(G, P0, r)[1], 2) for r in poses})


if __name__ == '__main__':
    import time
    t0 = time.time()
    G = Rigged('ethics')
    jsA, infoA = layer_a(G)
    print('layer A: %d frames @ %.3f fps (loop %.4f s), right hand fit rms %.2f, bones %d, %.0fs' % (len(jsA['FrameData']), infoA['fps'], infoA['T'], infoA['rms'], len(jsA['FrameData'][0]['BoneInfo']), time.time() - t0))
    jsB, infoB = layer_b(G)
    print('layer B: %d frames, bones %d, segments %d, fit rms %s, %.0fs' % (len(jsB['FrameData']), len(jsB['FrameData'][0]['BoneInfo']), len(infoB['segs']), infoB['rms'], time.time() - t0))
    for nm, js in (('A', jsA), ('B', jsB)):
        s = json.dumps(js, separators=(',', ':'))
        print('layer %s JSON %d bytes' % (nm, len(s)))
        open(os.path.join(HERE, 'out', 'guitar_%s.json' % nm), 'w').write(s)
