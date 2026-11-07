"""the guitar pac: `pac_event guitar 2` puts a Martin D-45 (the velkon_guitar model) on your chest and you play Brain Damage (the instrumental recording, 3:50) with it.
Layer A (body sway, nod, foot tap and the picking hand) is scrubbed along the beats of the recording by a proxy on the animation's Offset (Rate 0), layer B (the fretting hand) is a long
sparse keyframe animation following the chord changes read from the recording.  Children text for one root; see build_children()."""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik
import outfit_lib as ol
import guitar_build as gb
import guitar_scene as gs
from retarget import angles_matrix

SLUG = 'eca_guitar'
COMMAND = 'guitar'
FAMILY = 'ethics'
ANIM_A_URL = ol.RAW + 'anim/guitar/%s/guitar_play_%s.json' % (FAMILY, FAMILY)
ANIM_B_URL = ol.RAW + 'anim/guitar/%s/guitar_chords_%s.json' % (FAMILY, FAMILY)
AUDIO_FILE = 'brain_damage.mp3'
VOLUME = 1.2                         # the recording is quiet (about -18 LUFS, quiet verses far lower); the loud emote masters play at 0.6..0.85


def friendly_bone(name):
    """ValveBiped.Bip01_Spine4 -> 'spine 4' (pac's bone naming)"""
    s = name.replace('ValveBiped.Bip01_', '').replace('ValveBiped.', '').lower()
    return re.sub(r'(?<=[a-z])(?=\d)', ' ', s)


def build_children(G, expr, slug=SLUG, base=1):
    b2, b3 = base + 2, base + 4
    bone = friendly_bone(G.rig.names[G.sp4])
    kids = ''
    a = {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear',
         'Name': 'you: sway, nod and the picking hand, scrubbed along the beats of the song (guitar_play_%s.json)' % FAMILY,
         'Rate': 0, 'StopOtherAnimations': True, 'URL': ANIM_A_URL, 'UniqueID': ol.uid(slug, 'animA')}
    prox = {'ClassName': 'proxy', 'Name': 'beat clock: picking-pattern cycles of the recording (its tempo curve) -> Offset', 'UniqueID': ol.uid(slug, 'proxy'),
            'VariableName': 'Offset', 'Expression': expr}
    kids += ol.part(b2, a, ol.part(b3, prox))
    b = {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear',
         'Name': 'you: fretting hand follows the chords (guitar_chords_%s.json)' % FAMILY,
         'StopOtherAnimations': False, 'URL': ANIM_B_URL, 'UniqueID': ol.uid(slug, 'animB')}
    kids += ol.part(b2, b)
    pitch, yaw, roll = ik.euler_for(G.local_R)
    assert np.allclose(angles_matrix((pitch, yaw, roll)), G.local_R, atol=1e-6), 'guitar angles do not reproduce the rotation'
    g = ol.model2(slug, 'guitar', 'guitar (velkon_guitar: Martin D-45) on the chest', gs.MODEL, bone, tuple(float(v) for v in G.local_pos), size=gs.SIZE, angles=(pitch, yaw, roll))
    kids += ol.part(b2, g)
    snd = ol.sound2(slug, 'sound', AUDIO_FILE, 1, VOLUME, name='Brain Damage, instrumental (%s; 0.25 s of lead silence = the animations\' ease-in)' % AUDIO_FILE)
    kids += ol.part(b2, snd)
    ev = ol.command_event(slug, COMMAND, 'Guitar: Brain Damage  (pac_event %s 2)' % COMMAND)
    return ol.part(base, ev, kids)


def write_assets(jsA, jsB, repo=ol.REPO):
    d = os.path.join(repo, 'anim', 'guitar', FAMILY)
    os.makedirs(d, exist_ok=True)
    out = []
    for js, nm in ((jsA, 'guitar_play_%s.json' % FAMILY), (jsB, 'guitar_chords_%s.json' % FAMILY)):
        p = os.path.join(d, nm)
        with open(p, 'w', newline='\n') as f:
            json.dump(js, f, separators=(',', ':'))
        out.append(p)
    return out


def standalone_text(G, expr):
    return ol.standalone(SLUG, 'guitar: play Brain Damage (instrumental) on a Martin D-45 (pac_event guitar 2)', build_children(G, expr, SLUG, 1))


if __name__ == '__main__':
    G, jsA, infoA, jsB, infoB, expr, terms, beats = gb.build(FAMILY)
    paths = write_assets(jsA, jsB, sys.argv[1] if len(sys.argv) > 1 else ol.REPO)
    for p in paths:
        print('wrote', p, os.path.getsize(p), 'bytes')
    text = standalone_text(G, expr)
    probs, n = ol.verify(text)
    print('standalone outfit', len(text), 'bytes', n, 'ids', 'OK' if not probs else probs)
    print('guitar on bone %r, Position %s, Angles %s' % (friendly_bone(G.rig.names[G.sp4]), np.round(G.local_pos, 2), np.round(ik.euler_for(G.local_R), 1)))
