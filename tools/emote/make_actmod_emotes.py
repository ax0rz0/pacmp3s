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
from emote_props import EXTRAS      # prop carrier bones per emote (trumpet, orb ...)
from mdl_anim import load_model

M01 = 'actmod:add_fortnite/anim_m_01'      # male skeleton (the job models are male); anim_f_01 is the female twin
M02 = 'actmod:add_fortnite/anim_m_02'
M03 = 'actmod:add_fortnite/anim_m_03'
M04 = 'actmod:add_fortnite/anim_m_04'      # from the "[ActMod] More Emotes Fortnite" extension (workshop 3567487307, see ACTMOD_EXT_DIR in make_fn_pack.py)
MEXP = 'actmodexp:m_ani_01'      # "[ActMod] AM4 Expansion Pack" (workshop 3682041393), see ACTMOD_EXP_DIR in make_fn_pack.py
# key (pac_event command), title, model, sequence, loop_start seconds (None = loop the whole clip), max seconds
SPECS = [
    ('jabba', 'Jabba Switchway', M01, 'Amod_Fortnite_JanuaryBop', 77 / 30, 10.2),   # 2.567 s intro, then a 7.6 s loop (frame 77 == last frame: closure 0.0 deg)
    ('griddy', 'Get Griddy', M01, 'Amod_Fortnite_Griddle', None, 10.0),         # loops cleanly over its whole 6.07 s
    ('pockets', 'Empty Out Your Pockets', M04, 'Amod_Fortnite_KelpLinen_C', 11 / 30, 10.8),   # 0.367 s intro, then a 10.433 s loop (ActMod Cycle 0.03395, Time2 10.43333; frame 11 == last frame, closure 0.14 deg)
    ('outwest', 'Out West', M01, 'Amod_Fortnite_JulyBooks', None, 6.9),         # loops over its whole 6.83 s (closure 0.06 deg); ActMod's music is exactly four loops (27.33 s)
    ('mufasa', 'Go Mufasa', M01, 'Amod_Fortnite_SandwichBop', None, 7.6),       # loops over its whole 7.567 s (closure 0.01 deg); the _walk twin is the moving version
    ('maskoff', 'Mask Off', M04, 'Amod_Fortnite_Reveal', 23 / 30, 13.6),        # 0.767 s intro (frame 23), then a 12.8 s loop (ActMod Cycle 0.0565, Time2 12.8; closure 0.10 deg); extension addon
    ('toosie', 'Toosie Slide', M04, 'Amod_Fortnite_ArtGiant', None, 5.9),       # loops over its whole 5.867 s (closure 0.08 deg); ActMod's music is exactly six loops (35.2 s); extension addon
    ('droop', 'Droop', 'fortnite1', 'CrazyDance', None, 7.5, 30),                # Droop is EID_CrazyDance; the wOS male taunt is tagged 60 fps but the game animation is 30 fps (7.4 s), so it is re-timed (7th field = real source fps)
    ('orangejustice', 'Orange Justice', M03, 'Amod_Fortnite_MaskOff', 18 / 30, 7.2, None, 60),   # EID_GoodVibes: 0.6 s intro (frame 18), then a 6.5 s loop (ActMod Cycle 0.0845, Time2 6.5; closure 0.01 deg); fast arm swings: 60 fps keys cut the replay error from p99 7.2 to 2.2 deg (8th field = key fps, default 30)
    ('thoughtiwasdead', 'Thought I Was Dead', MEXP, 'Amod_Fortnite_CanineCronutMix', 128 / 30, 19.1),   # Tyler, The Creator (internal CanineCronutMix): 4.27 s intro (frame 128), then a 14.8 s loop (ActMod Cycle 0.2238, Time2 14.8; closure 0.01 deg); the prop (a cronut) is not reproduced
    ('chickenwing', 'Chicken Wing It', M02, 'Amod_Fortnite_Noodles', 103 / 30, 10.4),                     # ActMod `noodles`: 3.43 s intro (frame 103), then a 6.97 s loop (Cycle 0.3301, Time2 6.96667; closure 0.01 deg)
    ('zany', 'Zany', M04, 'Amod_Fortnite_Bendy', None, 9.2),                                              # loops over its whole 9.1 s (closure 0.14 deg); ActMod `Repeat`, music 9.14 s; extension addon
    ('headbanger', 'Head Banger', M01, 'Amod_Fortnite_cyclone_headbang', None, 3.1),    # EID_CycloneHeadBang (Travis Scott, Astronomical): loops over its whole 3.067 s clip (closure 0.0 deg); ActMod restarts sound and animation together (AutoReAnim)
    ('mystery', "I'm a Mystery", M01, 'Amod_Fortnite_VoidRedemption', 22 / 60.0, 7.75, None, 60),   # EID_VoidRedemption (the 'You Don't Know Me' emote): 0.367 s intro (60 fps frame 22), then a 7.333 s loop (closure 0.02 deg); 60 fps keys: 30 fps left 20 deg errors in the fast moves
    ('touchingthesky', 'Touching The Sky', M04, 'Amod_Fortnite_tailor', 50 / 30.0, 9.2),            # ActMod extension `fortnite_tailor`: 1.667 s intro (frame 50, Cycle 0.18248), then a 7.467 s loop (Time2 7.46667; closure 0.01 deg; the auto loop finder picks a bad inner window, so ActMod's is used); music = 1.07 s intro + 14.93 s loop (two animation loops)
    ('leiltelomr', 'Leilt Elomr', M02, 'Amod_Fortnite_myeffort', None, 8.5),                          # ActMod `myeffort` (display name Leilt Elomr): loops over its whole 8.4 s clip (Cycle 0, closure 0.37 deg); music restarts every 16.8 s = two loops
    ('scenario', 'Scenario', M04, 'Amod_Fortnite_KPOPDance_03', None, 8.2),                              # loops over its whole 8.13 s (closure 0.13 deg); ActMod's music is exactly four loops (32.54 s); extension addon
    ('smoothmoves', 'Smooth Moves', 'fortnite2', 'Kpop_02', None, 7.8, 30),                              # EID_KPopDance02: the wOS male taunt is tagged 60 fps but the game animation is 30 fps (7.67 s), so it is re-timed; whole-clip loop (closure 0.10 deg)
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
        for spec in SPECS:
            key, title, model, seq, loop_start, max_sec = spec[:6]
            src_fps = spec[6] if len(spec) > 6 else None
            key_fps = spec[7] if len(spec) > 7 else 30
            if a.only and key not in a.only.split(','):
                continue
            js, st = fp.build((key, title, model, seq), valve, fps=key_fps, max_sec=max_sec, finger_min=60.0, loop_start=loop_start, src_fps=src_fps, extra=EXTRAS.get(key))   # source is 30 fps: native key rate
            path = os.path.join(a.out, fam, 'fn_%s.json' % key)
            with open(path, 'w', newline='\n') as f:
                json.dump(js, f, separators=(',', ':'))
            print('%-7s %-7s %2dfps %5.2fs %4d fr %2d bones %5.0f KB | restart frame %3d | root %-8s span %5.1f | loop closure %5.1f%s | replay err mean %.2f p99 %.2f max %.1f' % (
                fam, key, st['fps'], st['secs'], st['frames'], st['bones'], os.path.getsize(path) / 1024, js['RestartFrame'], st['axes'], st['span'],
                st['closure'], '+B' if st['blended'] else '  ', st['mean_err'], st['p99'], st['max_err']))
            sys.stdout.flush()


if __name__ == '__main__':
    main()
