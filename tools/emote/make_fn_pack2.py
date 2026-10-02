"""Second Fortnite emote pack: adaptive keyframe thinning on 60 fps source frames (smaller downloads, same error model).

python make_fn_pack2.py --pool --families classd --out pool_out          # screen the whole candidate pool, print quality table
python make_fn_pack2.py --final --out ..\\..\\anim\\fn                   # build the chosen emotes for isd / medic / classd
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import make_fn_pack as fp
import make_emote as me
from fn_thin import thin, eulers_to_R, rot_err_deg
from mdl_anim import load_model, angle_between
from retarget import Retargeter, Valve, ValveAnimSource

# (command, title, sequence label in the male set)
POOL = [
    ('boneless', 'Boneless', 'Dance_NoBones'), ('swipeit', 'Swipe It', 'Dance_SwipeIt'), ('shoot', 'Shoot', 'Dance_Shoot'),
    ('bunnyhop', 'Bunny Hop', 'BunnyHop'), ('robot', 'Robot', 'Cool_Robot'), ('crab', 'Crab Rave', 'Crab_Dance'),
    ('candy', 'Candy Dance', 'Candy_Dance'), ('electroswing', 'Electro Swing', 'ElectroSwing'), ('twist', 'Twist', 'Twist'),
    ('zippy', 'Zippy Dance', 'Zippy_Dance'), ('smoothride', 'Smooth Ride', 'Smooth_Ride'), ('poplock', 'Pop Lock', 'PopLock'),
    ('disco', 'Disco Fever', 'Dance_Disco_T3'), ('boogiedown', 'Boogie Down', 'Boogie_Down'), ('hotstuff', 'Hot Stuff', 'Hotstuff'),
    ('fancyfeet', 'Fancy Feet', 'FancyFeet'), ('dreamfeet', 'Dream Feet', 'DreamFeet'), ('takethew', 'Take the W', 'Take_the_W'),
    ('onearmfloss', 'One Arm Floss', 'OneArmFloss'), ('sprinkler', 'Sprinkler', 'Sprinkler'), ('kpop', 'K-Pop', 'KPop_Dance03'),
    ('hiphop', 'Hip Hop', 'Hip_Hop'), ('goat', 'Goat Dance', 'GoatDance'), ('hula', 'Hula', 'Hula'), ('micdrop', 'Mic Drop', 'Mic_Drop'),
    ('yeet', 'Yeet', 'Yeet'), ('facepalm', 'Facepalm', 'Facepalm'), ('calculated', 'Calculated', 'Calculated'),
    ('jazz', 'Jazz Dance', 'Jazz_Dance'), ('flamenco', 'Flamenco', 'Flamenco'), ('treadmill', 'Treadmill', 'TreadmillDance'),
    ('breakdance', 'Break Dance', 'Break_Dance'), ('swingdance', 'Swing Dance', 'SwingDance'), ('funktime', 'Funk Time', 'Funk_Time'),
    ('gabby', 'Gabby Hip Hop', 'Gabby_HipHop'), ('groovejam', 'Groove Jam', 'GrooveJam'), ('hitwoah', 'Hit the Woah', 'Hit_The_Woah'),
    ('wavedance', 'Wave Dance', 'Wave_Dance'), ('showstopper', 'Showstopper', 'Showstopper_Dance'), ('skeleton', 'Skeleton Dance', 'SkeletonDance'),
    ('worm', 'The Worm', 'Dance_Worm'),
]
# the emotes that go into the outfit (filled in after screening)
FINAL = ['swipeit', 'shoot', 'boneless', 'bunnyhop', 'crab', 'candy', 'electroswing', 'twist', 'zippy', 'smoothride', 'hotstuff', 'fancyfeet',
         'takethew', 'onearmfloss', 'hiphop', 'hula', 'yeet', 'showstopper', 'hitwoah', 'calculated']


def find_model(seq):
    for model in ('fortnite1', 'fortnite2', 'fortnite3'):
        if seq.lower() in fp.taunt(model)[2]:
            return model
    raise KeyError(seq)


def build_thin(spec, valve, max_sec=10.0, ease_in=0.25, blend=0.35, decimals=1, finger_min=45.0, tol_body=0.9, tol_finger=4.0, tol_pos=0.4):
    key, title, seq = spec
    model = find_model(seq)
    m, ani, seqs = fp.taunt(model)
    src = ValveAnimSource(m, ani, seqs[seq.lower()])
    fps = src.fps
    dur = min(src.duration, max_sec)
    n = int(round(dur * fps)) + 1
    times = [i / fps for i in range(n)]
    pel = np.array([src.pose(t)['Pelvis'][1] for t in times[::3]])
    span = max(np.ptp(pel[:, 0]), np.ptp(pel[:, 1]))
    rest_z = src.rest()['Pelvis'][1][2]
    drop = float(rest_z - pel[:, 2].min())
    axes = 'full' if span <= 30 else 'vertical'
    rt = Retargeter(src, valve, root_motion=True, root_axes=axes)
    frames = me.sample(rt, times, True)
    names = {b: valve.m.names[b] for b in frames[0][0]}
    keep = {b for b, nm in names.items() if fp.body_bone(nm)}
    for side in ('R', 'L'):
        for chain in (('0', '01', '02'), ('1', '11', '12'), ('2', '21', '22'), ('3', '31', '32'), ('4', '41', '42')):
            members = [b for b, nm in names.items() if any(nm.endswith('Bip01_%s_Finger%s' % (side, c)) for c in chain)]
            if members and max(np.ptp(np.array([f[0][b] for f in frames]), axis=0).max() for b in members) > finger_min:
                keep.update(members)
    bones = sorted(keep)
    pelvis_i = [i for i, b in enumerate(bones) if names[b].endswith('Pelvis')][0]
    E = np.array([[frames[i][0][b] for b in bones] for i in range(n)])
    T = np.array([frames[i][1] for i in range(n)])
    tol = np.array([tol_finger if 'Finger' in names[b] else tol_body for b in bones])
    kidx = thin(E, T, tol, tol_pos)
    data = []
    for j, k in enumerate(kidx):
        info = {}
        for bi, b in enumerate(bones):
            a = E[k, bi]
            e = {'RR': round(float(a[0]), decimals), 'RU': round(float(a[1]), decimals), 'RF': round(float(a[2]), decimals)}
            if bi == pelvis_i:
                t = T[k]
                e['MF'] = round(float(t[0]), decimals); e['MR'] = round(float(-t[1]), decimals); e['MU'] = round(float(t[2]), decimals)
            info[names[b]] = e
        data.append({'FrameRate': round(1.0 / ease_in if j == 0 else fps / (k - kidx[j - 1]), 3), 'BoneInfo': info})
    js = {'Type': 'sequence', 'Interpolation': 'linear', 'RestartFrame': 2, 'FrameData': data, 'Name': title, 'Notes': 'claude skill made by ax0rz0'}
    mean_err, p99, max_err, pos_err = simulate(rt, valve, js, bones, names, kidx, fps, pelvis_i)
    A, B = rt.solve(times[0])[3], rt.solve(times[-1])[3]
    closure = max(angle_between(A[b], B[b]) for b in A)
    blended = closure > 5.0
    if blended:
        first, last = data[0]['BoneInfo'], data[-1]['BoneInfo']
        cp = {}
        for nm, e in first.items():
            prev = np.array([last[nm]['RR'], last[nm]['RU'], last[nm]['RF']])
            c = me.continuous(prev, np.array([e['RR'], e['RU'], e['RF']]))
            d = dict(e); d['RR'], d['RU'], d['RF'] = [round(float(x), decimals) for x in c]
            cp[nm] = d
        data.append({'FrameRate': round(1.0 / blend, 3), 'BoneInfo': cp})
    st = dict(key=key, title=title, seq=seq, model=model, secs=dur, src_secs=src.duration, src_frames=n, keys=len(kidx), frames=len(data), bones=len(keep),
              axes=axes, span=float(span), drop=drop, closure=float(closure), blended=blended, mean_err=mean_err, p99=p99, max_err=max_err, pos_err=pos_err)
    return js, st


def simulate(rt, valve, js, bones, names, kidx, fps, pelvis_i):
    """Replay the (rounded) JSON like pac: linear Euler lerp between the kept frames; compare world bone rotations with the exact retarget."""
    fd = js['FrameData']
    K = len(kidx)
    Er = np.array([[[fd[j]['BoneInfo'][names[b]][c] for c in ('RR', 'RU', 'RF')] for b in bones] for j in range(K)])
    Tk = np.array([[fd[j]['BoneInfo'][names[bones[pelvis_i]]][c] for c in ('MF', 'MR', 'MU')] for j in range(K)])
    Tk[:, 1] *= -1.0
    tk = np.array(kidx) / fps
    probes = np.arange(0.0, tk[-1] + 1e-9, 0.5 / fps)
    errs = []
    perr = 0.0
    for tau in probes:
        j = int(np.searchsorted(tk, tau, side='left'))
        j = max(1, min(K - 1, j))
        d = (tau - tk[j - 1]) / (tk[j] - tk[j - 1])
        e = (1 - d) * Er[j - 1] + d * Er[j]
        Rs = eulers_to_R(e)
        _, trans, (XR, _), _ = rt.solve(tau)
        M = {b: Rs[i] for i, b in enumerate(bones)}
        WR = [None] * valve.m.n
        for b in range(valve.m.n):
            p = valve.parent[b]
            PR = WR[p] if p >= 0 else np.eye(3)
            WR[b] = PR @ valve.Lr[b] @ M.get(b, np.eye(3))
        for b in bones:
            errs.append(angle_between(WR[b], XR[b]))
        tl = (1 - d) * Tk[j - 1] + d * Tk[j]
        perr = max(perr, float(np.linalg.norm(tl - trans)))
    errs = np.array(errs)
    return float(errs.mean()), float(np.percentile(errs, 99)), float(errs.max()), perr


def row(fam, st, kb):
    return ('%-7s %-12s %-16s %4.1fs %3d->%3d keys %2d bones %5.0f KB | root %-8s span %5.1f drop %4.1f | closure %5.1f%s | err mean %.2f p99 %.2f max %5.1f pos %.2f' % (
        fam, st['key'], st['seq'], st['secs'], st['src_frames'], st['keys'], st['bones'], kb, st['axes'], st['span'], st['drop'], st['closure'],
        '+B' if st['blended'] else '  ', st['mean_err'], st['p99'], st['max_err'], st['pos_err']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pool', action='store_true')
    ap.add_argument('--final', action='store_true')
    ap.add_argument('--only', default=None)
    ap.add_argument('--families', default='isd,medic,classd')
    ap.add_argument('--out', default='pool_out')
    a = ap.parse_args()
    specs = POOL if a.pool else [s for s in POOL if s[0] in FINAL]
    if a.only:
        specs = [s for s in POOL if s[0] in a.only.split(',')]
    for fam in a.families.split(','):
        valve = Valve(load_model(fp.FAMILIES[fam]))
        os.makedirs(os.path.join(a.out, fam), exist_ok=True)
        for spec in specs:
            try:
                js, st = build_thin(spec, valve)
            except Exception as e:
                print('%-7s %-12s FAILED %s' % (fam, spec[0], e)); continue
            path = os.path.join(a.out, fam, 'fn_%s.json' % spec[0])
            with open(path, 'w', newline='\n') as f:
                json.dump(js, f, separators=(',', ':'))
            print(row(fam, st, os.path.getsize(path) / 1024)); sys.stdout.flush()


if __name__ == '__main__':
    main()
