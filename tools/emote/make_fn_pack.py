"""Convert emotes from the wOS 'Custom Taunt' Fortnite animation models (already on the Valve skeleton) into PAC3 custom_animation JSON.

python make_fn_pack.py [--only floss] [--families isd,medic,classd] [--out DIR] [--max-sec 10]
"""
import argparse, glob, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mdl_anim import Mdl, Gma, load_model, angle_between
from retarget import Retargeter, Valve, ValveAnimSource, angles_matrix, source_angles
import make_emote as me

TAUNT_GMA = glob.glob(r'C:\Program Files (x86)\Steam\steamapps\workshop\content\4000\2274808442\*.gma')
FAMILIES = {   # family -> representative job model (same base pose within a family)
    'isd': 'models/frostbyte/ia/internalsecurity_erdim.mdl',      # ISD, GOC, technical expert
    'medic': 'models/frostbyte/cn_s65_combatmedic.mdl',
    'classd': 'models/player/kerry/class_d_7.mdl',
}
# key (also the pac_event command), title, model file, sequence label (male set; the f_ twins are the female skeleton)
SPECS = [
    ('floss', 'Floss', 'fortnite3', 'FlossDance'),
    ('dance', 'Default Dance', 'fortnite3', 'DanceMoves'),
    ('takethel', 'Take the L', 'fortnite2', 'Loser_Dance'),
    ('deepdab', 'Deep Dab', 'fortnite3', 'DeepDab'),
    ('infinidab', 'Infinite Dab', 'fortnite2', 'InfiniDab'),
    ('electro', 'Electro Shuffle', 'fortnite1', 'ElectroShuffle2'),
    ('fresh', 'Fresh', 'fortnite1', 'Fresh'),
    ('wiggle', 'Wiggle', 'fortnite3', 'Wiggle'),
    ('moonwalk', 'Moonwalk', 'fortnite2', 'Moonwalking'),
    ('ragequit', 'Rage Quit', 'fortnite2', 'RageQuit'),
    ('windmill', 'Windmill Floss', 'fortnite3', 'WindmillFloss'),
]
_cache = {}


ACTMOD_DIR = os.path.join(os.path.expanduser('~'), 'Downloads', 'actmod_2538387266', 'models', 'player', 'ani_am4')
# the "[ActMod] More Emotes Fortnite" extension (workshop 3567487307) adds anim_m_04 / anim_m_05 to the same add_fortnite folder; set ACTMOD_EXT_DIR to its extracted models/player/ani_am4
ACTMOD_EXT_DIR = os.environ.get('ACTMOD_EXT_DIR', os.path.join(os.path.expanduser('~'), 'Downloads', 'actmod_3567487307', 'models', 'player', 'ani_am4'))


# the "[ActMod] AM4 Expansion Pack" (workshop 3682041393, the Commission Hub) keeps its animations in models/player/ani_am4/m_ani_01.mdl; set ACTMOD_EXP_DIR to its extracted models/player/ani_am4
ACTMOD_EXP_DIR = os.environ.get('ACTMOD_EXP_DIR', os.path.join(os.path.expanduser('~'), 'Downloads', 'actmod_3682041393', 'models', 'player', 'ani_am4'))


def taunt(model):
    if model.startswith('actmodexp:'):        # e.g. 'actmodexp:m_ani_01'
        if model not in _cache:
            base = os.path.join(ACTMOD_EXP_DIR, *model[10:].split('/'))
            m = Mdl(open(base + '.mdl', 'rb').read())
            ani = open(base + '.ani', 'rb').read()
            _cache[model] = (m, ani, {m.seq_info(k)[0].lower(): m.seq_info(k)[1] for k in range(m.i32(188))})
        return _cache[model]
    if model.startswith('actmod:'):          # e.g. 'actmod:add_fortnite/anim_m_01' (extracted ActMod folder)
        if model not in _cache:
            base = os.path.join(ACTMOD_DIR, *model[7:].split('/'))
            if not os.path.exists(base + '.mdl'):
                base = os.path.join(ACTMOD_EXT_DIR, *model[7:].split('/'))
            m = Mdl(open(base + '.mdl', 'rb').read())
            ani = open(base + '.ani', 'rb').read()
            _cache[model] = (m, ani, {m.seq_info(k)[0].lower(): m.seq_info(k)[1] for k in range(m.i32(188))})
        return _cache[model]
    if model not in _cache:
        g = Gma(TAUNT_GMA[0])
        m = Mdl(g.get('models/player/custom_taunt/%s.mdl' % model, limit=64 * 1024 * 1024))
        ani = g.get('models/player/custom_taunt/%s.ani' % model, limit=128 * 1024 * 1024)
        seqs = {}
        for k in range(m.i32(188)):
            label, a0 = m.seq_info(k)
            seqs[label.lower()] = a0
        _cache[model] = (m, ani, seqs)
    return _cache[model]


def body_bone(name):
    return 'Finger' not in name


def build(spec, valve, fps=None, max_sec=10.0, ease_in=0.25, blend=0.35, decimals=1, finger_min=20.0, loop_start=None, src_fps=None):
    """fps=None picks the lowest key rate whose pac-replay error is small (30, 40 or 60). src_fps re-times a source whose fps tag is wrong (wOS male taunts of 30 fps animations are tagged 60 and run twice too fast)."""
    if fps is None:
        for cand in (30, 40, 60):
            js, st = build(spec, valve, cand, max_sec, ease_in, blend, decimals, finger_min, loop_start, src_fps)
            if (st['p99'] <= 4.0 and st['mean_err'] <= 0.8) or cand == 60:
                st['fps'] = cand
                return js, st

    key, title, model, seq = spec
    m, ani, seqs = taunt(model)
    src = ValveAnimSource(m, ani, seqs[seq.lower()])
    if src_fps:
        src.fps = float(src_fps)
        src.duration = (src.nframes - 1) / src.fps
    dur = min(src.duration, max_sec)
    n = int(round(dur * fps)) + 1
    times = [i / fps for i in range(n)]
    # root travel: keep sway, drop travel (moonwalk, runs) so the body stays with the player
    pel = [src.pose(t)['Pelvis'][1] for t in times[::3]]
    span = max(np.ptp([p[0] for p in pel]), np.ptp([p[1] for p in pel]))
    axes = 'full' if span <= 30 else 'vertical'
    rt = Retargeter(src, valve, root_motion=True, root_axes=axes)
    frames = me.sample(rt, times, True)
    names = {b: valve.m.names[b] for b in frames[0][0]}
    keep = {b for b, nm in names.items() if body_bone(nm)}
    # fingers: keep or drop a WHOLE chain (a kept tip joint with a dropped parent would sit at the wrong world angle)
    for side in ('R', 'L'):
        for chain in (('0', '01', '02'), ('1', '11', '12'), ('2', '21', '22'), ('3', '31', '32'), ('4', '41', '42')):
            members = [b for b, nm in names.items() if nm.endswith('Bip01_%s_Finger%s' % (side, chain[0])) or any(nm.endswith('Bip01_%s_Finger%s' % (side, c)) for c in chain)]
            if not members:
                continue
            motion = max(np.ptp(np.array([f[0][b] for f in frames]), axis=0).max() for b in members)
            if motion > finger_min:
                keep.update(members)
    data = []
    for i, (ang, trans) in enumerate(frames):
        info = {}
        for b in keep:
            a = ang[b]
            e = {'RR': round(float(a[0]), decimals), 'RU': round(float(a[1]), decimals), 'RF': round(float(a[2]), decimals)}
            if names[b].endswith('Pelvis') and trans is not None:
                e['MF'] = round(float(trans[0]), decimals); e['MR'] = round(float(-trans[1]), decimals); e['MU'] = round(float(trans[2]), decimals)
            info[names[b]] = e
        data.append({'FrameRate': (1.0 / ease_in if i == 0 else float(fps)), 'BoneInfo': info})
    s_idx = int(round(loop_start * fps)) if loop_start else 0     # the loop restarts at this source frame (an intro plays once)
    js = {'Type': 'sequence', 'Interpolation': 'linear', 'RestartFrame': s_idx + 2, 'FrameData': data, 'Name': title, 'Notes': 'claude skill made by ax0rz0'}
    worst, errs = me.simulate_pac(rt, js, fps, ease_in)
    # loop closure: end pose vs start pose (body bones), blend back if they differ
    A, B = rt.solve(times[s_idx])[3], rt.solve(times[-1])[3]
    closure = max(angle_between(A[b], B[b]) for b in A)
    blended = closure > 5.0
    if blended:
        first = data[s_idx]['BoneInfo']; last = data[-1]['BoneInfo']
        cp = {}
        for nm, e in first.items():
            prev = np.array([last[nm]['RR'], last[nm]['RU'], last[nm]['RF']])
            c = me.continuous(prev, np.array([e['RR'], e['RU'], e['RF']]))
            d = dict(e); d['RR'], d['RU'], d['RF'] = [round(float(x), decimals) for x in c]
            cp[nm] = d
        data.append({'FrameRate': 1.0 / blend, 'BoneInfo': cp})
    stats = dict(fps=fps, key=key, title=title, seq=seq, secs=dur, src_secs=src.duration, frames=len(data), bones=len(keep), axes=axes, span=float(span),
                 closure=float(closure), blended=blended, mean_err=float(errs.mean()), p99=float(np.percentile(errs, 99)), max_err=float(errs.max()),
                 palm=sorted(rt.n_valve))
    return js, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    ap.add_argument('--families', default='isd,medic,classd')
    ap.add_argument('--out', default='fn_out')
    ap.add_argument('--max-sec', type=float, default=10.0)
    ap.add_argument('--fps', type=float, default=None)
    a = ap.parse_args()
    for fam in a.families.split(','):
        valve = Valve(load_model(FAMILIES[fam]))
        os.makedirs(os.path.join(a.out, fam), exist_ok=True)
        for spec in SPECS:
            if a.only and spec[0] != a.only:
                continue
            js, st = build(spec, valve, fps=a.fps, max_sec=a.max_sec)
            path = os.path.join(a.out, fam, 'fn_%s.json' % spec[0])
            with open(path, 'w', newline='\n') as f:
                json.dump(js, f, separators=(',', ':'))
            print('%-7s %-9s %2dfps %5.1fs/%.1fs %4d fr %2d bones %6.0f KB | root %-8s span %5.1f | closure %5.1f%s | pac replay err mean %.2f p99 %.2f max %.1f | palm %s' % (
                fam, st['key'], st['fps'], st['secs'], st['src_secs'], st['frames'], st['bones'], os.path.getsize(path) / 1024, st['axes'], st['span'], st['closure'],
                ' +blend' if st['blended'] else '       ', st['mean_err'], st['p99'], st['max_err'], ''.join(st['palm']) or 'none'))
            sys.stdout.flush()


if __name__ == '__main__':
    main()
