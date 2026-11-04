"""v2 build + checks: builds both rigs' JSON from a choreography module, then reports pac-replay error (linear Euler lerp between 30 fps samples vs the exact pose), loop closure, gimbal, feet"""
import importlib, json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thr_core as tc
from mdl_anim import angle_between

FPS = 30
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
CHARS = {'player': ('ethics', 'player'), 'zombie': ('zombie', 'zombie')}


def build(kind, td, tl=None, write=True, tag='v2', **tojson):
    rigkey, style = CHARS[kind]
    rig = tc.rig_for(rigkey)
    tl = tl or td.Timeline()
    n = int(td.LOOP_BEATS * td.BEAT * FPS)
    times = [i / FPS for i in range(n + 1)]
    frames = tc.build_frames(rig, lambda t: tl.pose(t / td.BEAT), times, td.style_for(style))
    js = tc.to_json(rig, frames, FPS, name='thriller_%s' % kind, **tojson)
    if write:
        with open(os.path.join(OUT, '%s_%s.json' % (tag, kind)), 'w', newline='\n') as f:
            json.dump(js, f, separators=(',', ':'))
    return rig, js, tl


def replay_detail(rig, tl, js, td, style, top=12):
    sol = tc.Solver(rig, td.style_for(style))
    fd = js['FrameData']
    FPS = float(fd[1]['FrameRate'])                       # the frames are evenly spaced; the first one is the ease-in
    rows = []
    for i in range(1, len(fd) - 1):
        t = (i - 0.5) / FPS
        M, trl = tc.manip_from_json_frame(rig, fd[i], interp_with=fd[i - 1], d=0.5)
        AR, AP = tc.fk_pose(rig, M, trl)
        _, _, XR, XP = sol.solve(tl.pose(t / td.BEAT))
        for b in range(rig.n):
            rows.append((angle_between(AR[b], XR[b]), i, rig.short(b)))
    rows.sort(reverse=True)
    allv = np.array([r[0] for r in rows])
    return dict(mean=float(allv.mean()), p99=float(np.percentile(allv, 99)), max=float(allv.max())), rows[:top]


def step_report(rig, js, top=6):
    """largest per-frame change of any manipulation angle (deg) and where"""
    fd = js['FrameData']
    worst = []
    for i in range(1, len(fd)):
        for name, e in fd[i]['BoneInfo'].items():
            p = fd[i - 1]['BoneInfo'].get(name)
            if p is None:
                continue
            d = max(abs(e['RR'] - p['RR']), abs(e['RU'] - p['RU']), abs(e['RF'] - p['RF']))
            worst.append((d, i, name.replace('ValveBiped.Bip01_', '')))
    worst.sort(reverse=True)
    return worst[:top]


def closure(js):
    fd = js['FrameData']
    worst = 0.0
    for name, e0 in fd[0]['BoneInfo'].items():
        e1 = fd[-1]['BoneInfo'][name]
        worst = max(worst, max(abs(e0['RR'] - e1['RR']), abs(e0['RU'] - e1['RU']), abs(e0['RF'] - e1['RF'])))
    return worst


def gimbal(js, thresh=70.0):
    mx = {}
    for fr in js['FrameData']:
        for name, e in fr['BoneInfo'].items():
            p = abs(((e['RR'] + 180.0) % 360.0) - 180.0)
            mx[name] = max(mx.get(name, 0.0), p)
    return sorted([(k.replace('ValveBiped.Bip01_', ''), round(v, 1)) for k, v in mx.items() if v > thresh], key=lambda kv: -kv[1])


if __name__ == '__main__':
    modname = sys.argv[1] if len(sys.argv) > 1 else 'thr_dance2'
    tag = sys.argv[2] if len(sys.argv) > 2 else 'v2'
    td = importlib.import_module(modname)
    t0 = time.time()
    tl = td.Timeline()
    for kind in ('player', 'zombie'):
        rig, js, _ = build(kind, td, tl, tag=tag)
        st = CHARS[kind][1]
        s, top = replay_detail(rig, tl, js, td, st)
        print('==', kind, 'bytes', os.path.getsize(os.path.join(OUT, '%s_%s.json' % (tag, kind))), 'frames', len(js['FrameData']))
        print(' replay err deg: mean %.2f p99 %.1f max %.1f' % (s['mean'], s['p99'], s['max']))
        print(' worst replay:', [(round(e, 1), f, n) for e, f, n in top[:8]])
        print(' biggest per-frame step:', [(round(d, 1), f, n) for d, f, n in step_report(rig, js)])
        print(' loop closure (max abs diff last/first frame, deg): %.2f   |pitch|>70:' % closure(js), gimbal(js))
    print('%.1fs' % (time.time() - t0))
