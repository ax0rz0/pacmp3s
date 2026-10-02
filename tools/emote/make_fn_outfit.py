"""Write the big Fortnite emote outfits (one command event + custom_animation per emote).

Main outfit  emote_fortnite.txt        -> 31 emotes, D-class base-pose files (also fine on ISD / GOC / tech expert: ~2 deg mean difference)
             emote_fortnite_isd.txt    -> exact for ISD / GOC / tech expert
             emote_fortnite_medic.txt  -> combat medic (its sequence 0 is a baton idle, so it needs its own files)
Trigger an emote:  pac_event <command> 2   (toggle).  Starting a new emote stops the previous one (StopOtherAnimations).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_emote_outfit import uid, table, part, verify, PAC_DIR, WATERMARK
from make_fn_pack import SPECS as SPECS1
import make_fn_pack2 as p2

SPECS = list(SPECS1) + [(k, t, '', seq) for k, t, seq in p2.POOL if k in p2.FINAL]

URL = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/anim/fn/%s/fn_%s.json'


def outfit(slug, title, family):
    kids = ''
    for key, name, model, seq in SPECS:
        anim = {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear', 'Name': 'fn_%s.json' % key,
                'StopOtherAnimations': True, 'URL': URL % (family, key), 'UniqueID': uid(slug, 'anim_' + key)}
        ev = {'AffectChildrenOnly': True, 'Arguments': key, 'ClassName': 'event', 'Event': 'command', 'Invert': True,
              'Name': '%s  (pac_event %s 2)' % (name, key), 'UniqueID': uid(slug, 'event_' + key)}
        kids += part(1, ev, part(3, anim))
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
