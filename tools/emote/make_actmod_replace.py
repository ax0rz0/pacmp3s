"""ActMod versions that replace the older wOS-derived emotes (same commands, new files under anim/am/<family>/am_<key>.json).

python make_actmod_replace.py [--families isd,medic,classd] [--out DIR] [--only floss,dance]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_fn_pack as fp
from fn_loop import find_loop
from retarget import Valve, ValveAnimSource
from mdl_anim import load_model

M03 = 'actmod:add_fortnite/anim_m_03'
M02 = 'actmod:add_fortnite/anim_m_02'
M01 = 'actmod:add_fortnite/anim_m_01'
M04 = 'actmod:add_fortnite/anim_m_04'      # "[ActMod] More Emotes Fortnite" extension (workshop 3567487307)
# command, title, model, sequence (the ActMod equivalent of the emote of the same name)
REPLACE = [
    ('floss', 'Floss', M03, 'Amod_Fortnite_FlossDance'),
    ('dance', 'Default Dance', M03, 'Amod_Fortnite_DanceMoves'),
    ('electro', 'Electro Shuffle', M03, 'Amod_Fortnite_ElectroShuffle'),
    ('hiphop', 'Hip Hop', M03, 'Amod_Fortnite_Hip_Hop'),
    ('fresh', 'Fresh', M04, 'Amod_Fortnite_Fresh'),
    ('electroswing', 'Electro Swing', M04, 'Amod_Fortnite_Electroswing'),
]


def build_one(spec, valve, max_sec=10.2):
    key, title, model, seq = spec
    m, ani, seqs = fp.taunt(model)
    src = ValveAnimSource(m, ani, seqs[seq.lower()])
    lp = find_loop(src, max_sec=max_sec)
    s_time = lp['s'] / src.fps if lp['s'] > 0 else None
    js, st = fp.build((key, title, model, seq), valve, fps=int(src.fps), max_sec=lp['e'] / src.fps, finger_min=60.0, loop_start=s_time)
    st['loop'] = lp
    return js, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--families', default='isd,medic,classd')
    ap.add_argument('--out', default='am_out')
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    for fam in a.families.split(','):
        valve = Valve(load_model(fp.FAMILIES[fam]))
        os.makedirs(os.path.join(a.out, fam), exist_ok=True)
        for spec in REPLACE:
            if a.only and spec[0] not in a.only.split(','):
                continue
            js, st = build_one(spec, valve)
            path = os.path.join(a.out, fam, 'am_%s.json' % spec[0])
            with open(path, 'w', newline='\n') as f:
                json.dump(js, f, separators=(',', ':'))
            lp = st['loop']
            print('%-7s %-8s %-27s %2dfps clip 0-%.2fs of %.2fs, loop restart %.2fs | closure %.1f deg vel %.2f | %3d fr %2d bones %5.0f KB | replay err mean %.2f p99 %.2f max %.1f%s' % (
                fam, spec[0], spec[3], st['fps'], lp['e'] / lp['fps'], (lp['nframes'] - 1) / lp['fps'], lp['s'] / lp['fps'], lp['closure'], lp['vel'], st['frames'], st['bones'],
                os.path.getsize(path) / 1024, st['mean_err'], st['p99'], st['max_err'], ' +blend' if st['blended'] else ''))
            sys.stdout.flush()


if __name__ == '__main__':
    main()
