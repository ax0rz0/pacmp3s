"""Write the big Fortnite emote outfits (one command event + custom_animation per emote).

Main outfit  emote_fortnite.txt        -> 33 emotes, D-class base-pose files (also fine on ISD / GOC / tech expert: ~2 deg mean difference)
             emote_fortnite_isd.txt    -> exact for ISD / GOC / tech expert
             emote_fortnite_medic.txt  -> combat medic (its sequence 0 is a baton idle, so it needs its own files)
Trigger an emote:  pac_event <command> 2   (toggle).  Starting a new emote stops the previous one (StopOtherAnimations).
Events use Operator 'equal': pac's default 'find simple' is a substring test, so pac_event electroswing also switched on the 'electro' event (and onearmfloss the 'floss' one).
Jabba Switchway, Get Griddy, Default Dance, Electro Shuffle, Hip Hop, Fresh, Empty Out Your Pockets, Out West, Go Mufasa, Mask Off, Toosie Slide, Electro Swing, Droop and Orange Justice also get a `sound2` (web sound) part after the animation, copied from the user's own saved setup (see MUSIC).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_emote_outfit import uid, table, part, verify, PAC_DIR, WATERMARK
from make_fn_pack import SPECS as SPECS1
import make_fn_pack2 as p2
import make_actmod_emotes as am
from make_actmod_replace import REPLACE as AM_REPLACE

SPECS = list(SPECS1) + [(k, t, '', seq) for k, t, seq in p2.POOL if k in p2.FINAL] + [tuple(sp[:4]) for sp in am.SPECS]

URL = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/anim/fn/%s/fn_%s.json'
URL_AM = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/anim/am/%s/am_%s.json'
AM_KEYS = {r[0] for r in AM_REPLACE}     # commands whose animation now comes from ActMod (new files, the wOS fn_ ones stay in the repo)


class Raw(object):
    """a value that is written verbatim (Angle(...), Vector(...))"""
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


# Audio setup ported from the user's own saved outfit (data/pac3/read me claude.txt, Oct 3 2026): inside the emote's command event, after the animation, one web sound
# (`sound2`) part. StopOnHide stops it with the emote, PlayCount is how often the file plays (0 = loop forever), Radius 500 and Bone head are the user's choices.
RAW_URL = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/%s'
MUSIC = {'jabba': ('jabba_switchway.mp3', 13), 'griddy': ('get_griddy.mp3', 51),     # command -> (file in the repo root, PlayCount); jabba and griddy are the user's own values
         'dance': ('default_dance.mp3', 50), 'electro': ('electro_shuffle.mp3', 50),   # dance and electro: 50 plays is about six minutes, 0 would loop forever
         'hiphop': ('hip_hop.mp3', 25),                                                # 25 plays of the 14.5 s track (two animation loops) is about six minutes
         'fresh': ('fresh.mp3', 70), 'pockets': ('empty_out_your_pockets.mp3', 17),     # 70 plays of the 5.05 s track and 17 of the 20.87 s loop (two animation loops): about six minutes
         'outwest': ('out_west.mp3', 13), 'mufasa': ('go_mufasa.mp3', 47),            # 13 plays of the 27.33 s track (four animation loops), 47 of the 7.57 s one
         'maskoff': ('mask_off.mp3', 56),                                              # 56 plays of the 6.4 s loop (half an animation loop)
         'toosie': ('toosie_slide.mp3', 10),                                          # 10 plays of the 35.2 s track (six animation loops)
         'electroswing': ('electro_swing.mp3', 22),                                   # 22 plays of the 16 s track (two animation loops)
         'droop': ('droop.mp3', 48),                                                   # 48 plays of the 7.43 s loop cut from the emote's preview video (one animation loop)
         'orangejustice': ('orange_justice.mp3', 19)}                                  # 19 plays of the 18.9 s track (three phrases of 6.32 s; the dance loops every 6.5 s, as in the game)
VOLUME = {'hiphop': 0.6, 'pockets': 0.7, 'fresh': 0.85, 'outwest': 0.6, 'mufasa': 0.6, 'maskoff': 0.6, 'toosie': 0.75, 'electroswing': 0.6, 'orangejustice': 1.2}      # loud masters (-7.3 to -10.5 LUFS, true peaks up to +3.7 dBFS, against -11 to -13 for the rest): the part plays them quieter and the mp3s stay untouched


def sound_part(slug, key):
    f, plays = MUSIC[key]
    return {'AimPartName': '', 'AimPartUID': '', 'AngleOffset': Raw('Angle(0, 0, 0)'), 'Angles': Raw('Angle(0, 0, 0)'), 'Bone': 'head', 'ClassName': 'sound2',
            'Doppler': False, 'DrawOrder': 0, 'Echo': False, 'EchoDelay': 0.5, 'EchoFeedback': 0.75, 'EditorExpand': False, 'EyeAngles': False, 'FilterFraction': 1,
            'FilterType': 0, 'Hide': False, 'IsDisturbing': False, 'MaxPitch': 0, 'MinPitch': 0, 'Name': '', 'Overlapping': False, 'Path': RAW_URL % f,
            'PauseOnHide': False, 'Pitch': 1, 'PitchLFOAmount': 0, 'PitchLFOTime': 0, 'PlayCount': plays, 'PlayOnFootstep': False, 'Position': Raw('Vector(0, 0, 0)'),
            'PositionOffset': Raw('Vector(0, 0, 0)'), 'Radius': 500, 'StopOnHide': True, 'TargetEntityUID': '', 'UniqueID': uid(slug, 'sound_' + key), 'Volume': VOLUME.get(key, 1),
            'VolumeLFOAmount': 0, 'VolumeLFOTime': 0}


def outfit(slug, title, family):
    kids = ''
    for key, name, model, seq in SPECS:
        am_ver = key in AM_KEYS
        anim = {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear', 'Name': ('am_%s.json' if am_ver else 'fn_%s.json') % key,
                'StopOtherAnimations': True, 'URL': (URL_AM if am_ver else URL) % (family, key), 'UniqueID': uid(slug, 'anim_' + key)}
        ev = {'AffectChildrenOnly': True, 'Arguments': key, 'ClassName': 'event', 'Event': 'command', 'Invert': True, 'Operator': 'equal',
              'Name': '%s  (pac_event %s 2)' % (name, key), 'UniqueID': uid(slug, 'event_' + key)}
        kids += part(1, ev, part(3, anim) + (part(3, sound_part(slug, key)) if key in MUSIC else ''))
    root = {'ClassName': 'group', 'EditorExpand': True, 'Name': title, 'Notes': WATERMARK, 'UniqueID': uid(slug, 'root')}
    return '-- ' + WATERMARK + '\n\n["self"] = {\n' + table(1, root) + '},\n["children"] = {\n' + kids + '},\n'


def main():
    sets = [('emote_fortnite', 'fortnite emotes (D-class base, fine on ISD/GOC/tech)', 'classd'),
            ('emote_fortnite_isd', 'fortnite emotes (ISD / GOC / tech expert exact)', 'isd'),
            ('emote_fortnite_medic', 'fortnite emotes (combat medic)', 'medic')]
    for slug, title, fam in sets:
        text = outfit(slug, title, fam)
        probs, n = verify(text)
        with open(os.path.join(PAC_DIR, slug + '.txt'), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        print('%-24s %6d bytes %3d ids %s' % (slug + '.txt', len(text), n, 'OK' if not probs else probs))


if __name__ == '__main__':
    main()
