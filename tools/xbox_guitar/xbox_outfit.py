"""the Xbox pac: a table with a TV and a console in front of you; `pac_event xbox 2` shows them.  You hold a pad (models/maxofs2d/button_06.mdl) in your left hand, lean in and press the console's
power button, the LED lights up and the TV plays a real Xbox One boot (frames and startup sound from a capture, a few frames a second) into the real home screen, while you stand there holding the
pad with both hands.  Children text for one root; see build_children()."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ik
import outfit_lib as ol
import thr_core as tc
import xbox_anim as xa
import xbox_anim2 as xa2
import xbox_ctrl as xc
import xbox_real as xr
import xbox_scene as sc
from retarget import angles_matrix

SLUG = 'eca_xbox'
COMMAND = 'xbox'
BONE = 'nobone'                                   # an invalid bone: the part sits at your origin with your view yaw (the zombies' test showed this is what the user wants)
ANIM_URL = ol.RAW + 'anim/xbox/ethics/xbox_ethics_v2.json'
VTF_URL = ol.RAW + 'tex/xbox/xbox_screen_game.vtf'
AUDIO_FILE = 'xbox_startup.mp3'
VOLUME = 1.0
GAME_AUDIO_FILE = 'xbox_game_loop.mp3'
GAME_VOLUME = 1.0
BOOT_START = xr.BOOT_START                         # seconds after the toggle: the press happens at about 1.45 s, the boot starts a beat later
LED_AT = 1.5
FRAMES = len(xr.TIMES) + 1 + xr.GAME_N             # boot frames, one black frame, the gameplay loop


def friendly_bone(name):
    import re
    s = name.replace('ValveBiped.Bip01_', '').replace('ValveBiped.', '').lower()
    return re.sub(r'(?<=[a-z])(?=\d)', ' ', s)


def controller_part(slug):
    """model2 of the pad on the chest bone, placed from the solver (the pad is chest relative; see xbox_ctrl.py)"""
    rig = tc.rig_for('ethics')
    arms = ik.Arms(rig, xa.STYLE)
    lp, lR = xc.local_in_chest(arms, xa.calm(**xa2.P_WATCH))
    pitch, yaw, roll = ik.euler_for(lR)
    assert np.allclose(angles_matrix((pitch, yaw, roll)), lR, atol=1e-4), 'controller angles do not reproduce the rotation'       # the bone frames carry ~1e-5 of float noise
    bone = friendly_bone(rig.names[rig.spine[-1]])
    return ol.model2(slug, 'controller', 'controller (maxofs2d button_06) in your hands', xc.MODEL, bone, tuple(float(v) for v in lp), size=xc.SIZE, angles=(pitch, yaw, roll))


def build_children(slug=SLUG, base=1):
    b2, b3 = base + 2, base + 4
    kids = ''
    anim = {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear',
            'Name': 'you: hold the pad, press the power button, then watch with both hands on it (xbox_ethics_v2.json)',
            'StopOtherAnimations': True, 'URL': ANIM_URL, 'UniqueID': ol.uid(slug, 'anim')}
    kids += ol.part(b2, anim)
    kids += ol.part(b2, controller_part(slug))
    parts = sc.table_parts() + sc.tv_parts() + sc.console_parts()
    for i, p in enumerate(parts):
        d = ol.model2(slug, 'p%d' % i, 'xbox: ' + p['name'], p['model'], BONE, p['pos'], scale=p['scale'], color=p['color'], material=ol.FLAT)
        kids += ol.part(b2, d)
    led = ol.sprite(slug, 'led', 'power LED glow', BONE, 'sprites/light_glow02_add', 3.4, (235, 255, 235))
    led['Position'] = ol.vec(*(sc.BUTTON + np.array([-0.6, 0.0, 0.0])))
    kids += ol.part(b2, ol.timerx_event(slug, 'led_timer', LED_AT, 'power LED (%.1f s after the toggle)' % LED_AT), ol.part(b3, led))
    scr = sc.screen_part()
    pitch, yaw, roll = ik.euler_for(scr['R'])
    assert np.allclose(angles_matrix((pitch, yaw, roll)), scr['R'], atol=1e-6), 'screen angles do not reproduce the rotation'
    sd = ol.model2(slug, 'screen', 'xbox: tv screen (a plate, uv 0..1, standing on edge)', scr['model'], BONE, scr['pos'], scale=scr['scale'], angles=(pitch, yaw, roll))
    mat = {'ClassName': 'material_2d', 'Name': 'xbox screen (real captures: the Xbox One boot, then a gameplay loop; %d frames, animated VTF)' % FRAMES, 'UniqueID': ol.uid(slug, 'mat'), 'basetexture': VTF_URL, 'frame': 0}
    prox = {'ClassName': 'proxy', 'Name': 'screen frames: boot from %.1f s, home screen, dark at %.1f s, then a %.2f s gameplay loop from %.1f s' % (BOOT_START, xr.T_BLACK, xr.GAME_LEN, xr.T_GAME),
            'UniqueID': ol.uid(slug, 'proxy'), 'VariableName': 'frame', 'Expression': xr.frame_expr()}
    kids += ol.part(b2, sd, ol.part(b3, mat, ol.part(b3 + 2, prox)))
    snd = ol.sound2(slug, 'sound', AUDIO_FILE, 1, VOLUME, name='Xbox startup sound (the capture\'s audio behind %.1f s of silence = the moment the TV boots)' % BOOT_START)
    kids += ol.part(b2, snd)
    gtimer = ol.timerx_event(slug, 'game_audio_timer', xr.T_GAME, 'gameplay sound loop starts %.1f s after the toggle (with the picture loop)' % xr.T_GAME)
    gsnd = ol.sound2(slug, 'game_sound', GAME_AUDIO_FILE, 0, GAME_VOLUME, name='gameplay sound, %.2f s loop (Need for Speed Rivals capture)' % xr.GAME_LEN)
    kids += ol.part(b2, gtimer, ol.part(b3, gsnd))
    ev = ol.command_event(slug, COMMAND, 'Xbox  (pac_event %s 2)' % COMMAND)
    return ol.part(base, ev, kids)


def write_assets(repo=ol.REPO, rewrite_anim=False):
    rig, arms, K, js, misses, info = xa2.build('ethics')
    d = os.path.join(repo, 'anim', 'xbox', 'ethics')
    os.makedirs(d, exist_ok=True)
    jp = os.path.join(d, 'xbox_ethics_v2.json')
    if rewrite_anim or not os.path.exists(jp):               # the pushed gesture file is left alone (same data; renaming is the way to change a file clients may have cached)
        with open(jp, 'w', newline='\n') as f:
            json.dump(js, f, separators=(',', ':'))
    frames, vp, n, ap, mx, gain, gp, g = xr.build_assets(repo)
    return jp, vp, ap, gp, js


def standalone_text():
    return ol.standalone(SLUG, 'xbox: turn on the console and watch it boot (pac_event xbox 2)', build_children(SLUG, 1))


if __name__ == '__main__':
    repo = sys.argv[1] if len(sys.argv) > 1 else ol.REPO
    jp, vp, ap, gp, js = write_assets(repo)
    print('wrote', jp, os.path.getsize(jp), 'bytes;', vp, os.path.getsize(vp), 'bytes;', ap, os.path.getsize(ap), 'bytes;', gp, os.path.getsize(gp), 'bytes;', len(js['FrameData']), 'animation frames')
    text = standalone_text()
    probs, n = ol.verify(text)
    print('standalone outfit', len(text), 'bytes', n, 'ids', 'OK' if not probs else probs)
