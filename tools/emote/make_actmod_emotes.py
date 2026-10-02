"""Convert emotes from an extracted ActMod addon (workshop 2538387266) into PAC3 custom_animation JSON.

ActMod stores its Fortnite emotes as sequences on the standard Valve skeleton in models/player/ani_am4/add_fortnite/anim_{m,f}_NN.mdl + .ani
(30 fps, sectioned). Internal names come from lua/actmod/am_actmod_lan.lua (januarybop = Jabba Switchway, griddle = Get Griddy).
The animation models have no 'reference' animation, so the bind pose rotated into the game frame is used as the rest pose.

python make_actmod_emotes.py [--families isd,medic,classd] [--out DIR]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_fn_pack as fp
from retarget import Valve
from mdl_anim import load_model

M01 = 'actmod:add_fortnite/anim_m_01'      # male skeleton (the job models are male); anim_f_01 is the female twin
# key (pac_event command), title, model, sequence, loop_start seconds (None = loop the whole clip), max seconds
SPECS = [
    ('jabba', 'Jabba Switchway', M01, 'Amod_Fortnite_JanuaryBop', 77 / 30, 10.2),   # 2.567 s intro, then a 7.6 s loop (frame 77 == last frame: closure 0.0 deg)
    ('griddy', 'Get Griddy', M01, 'Amod_Fortnite_Griddle', None, 10.0),         # loops cleanly over its whole 6.07 s
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--families', default='isd,medic,classd')
    ap.add_argument('--out', default='actmod_out')
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    for fam in a.families.split(','):
        valve = Valve(load_model(fp.FAMILIES[fam]))
        os.makedirs(os.path.join(a.out, fam), exist_ok=True)
        for key, title, model, seq, loop_start, max_sec in SPECS:
            if a.only and key not in a.only.split(','):
                continue
            js, st = fp.build((key, title, model, seq), valve, fps=30, max_sec=max_sec, finger_min=60.0, loop_start=loop_start)   # source is 30 fps: native key rate
            path = os.path.join(a.out, fam, 'fn_%s.json' % key)
            with open(path, 'w', newline='\n') as f:
                json.dump(js, f, separators=(',', ':'))
            print('%-7s %-7s %2dfps %5.2fs %4d fr %2d bones %5.0f KB | restart frame %3d | root %-8s span %5.1f | loop closure %5.1f%s | replay err mean %.2f p99 %.2f max %.1f' % (
                fam, key, st['fps'], st['secs'], st['frames'], st['bones'], os.path.getsize(path) / 1024, js['RestartFrame'], st['axes'], st['span'],
                st['closure'], '+B' if st['blended'] else '  ', st['mean_err'], st['p99'], st['max_err']))
            sys.stdout.flush()


if __name__ == '__main__':
    main()
