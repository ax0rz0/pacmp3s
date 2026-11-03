"""Build the Thriller zombie-dance pack: animation JSONs (player families + HL2 zombie), the music loop, and the pac3 outfits.

  python make_thriller.py [--repo PATH] [--pac PATH] [--no-anim] [--no-audio]

Outputs
  <repo>/anim/thriller/<family>/thriller_<family>.json     custom_animation data (families ethics, classd, isd, medic, zombie), 30 fps, 481 frames = one 16 s loop (32 beats at 120 BPM)
  <repo>/thriller_dance.mp3                                the 16 s music loop (cut by make_audio.py)
  <pac>/thriller_<family>.txt                              the big pac: 2 HL2 zombies + your dance + music, one toggle   (pac_event thriller 2)
  <pac>/thriller_zombies.txt                               the two zombies + music only (for any playermodel)
and copies of the outfits in <repo>/outfits/thriller/.

The outfit structure follows the emote pack (old pac3 build): command event (Operator equal, Invert, AffectChildrenOnly) -> children.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
EMOTE = r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\emote'
sys.path.insert(0, EMOTE)
import numpy as np

import thr_core as tc
import thr_dance2 as td
from make_emote_outfit import uid, table, part, verify, PAC_DIR, WATERMARK
from emote_parts import vec, sound2
import pac_parse as pp

REPO = r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s'
RAW = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/'
FPS = 30
FAMILIES = {'ethics': ('ethics', 'player', 'Ethics Assistant (female_04)'), 'classd': ('classd', 'player', 'D-class'),
            'isd': ('isd', 'player', 'ISD / GOC / tech expert'), 'medic': ('medic', 'player', 'combat medic'),
            'zombie': ('zombie', 'zombie', 'HL2 classic zombie')}
COMMAND = 'thriller'
MUSIC_FILE = 'thriller_dance.mp3'
LOOP_SECONDS = td.LOOP_BEATS * td.BEAT                 # 16.0
MUSIC_PLAYS = 38                                       # 38 x 16 s = about ten minutes (toggle the dance off any time; the sound stops with it)
ZOMBIE_Y = 78                                          # lateral spacing: closest bone-to-bone approach over the whole dance is about 14 units
ZOMBIE_X = -14                                         # a little behind you
RISE_SECONDS = 3.2
RISE_DEPTH = 78


# ---------------------------------------------------------------------------------------------------------------------------- animations
def build_anim(fam, tl):
    rigkey, style, _ = FAMILIES[fam]
    rig = tc.rig_for(rigkey)
    n = int(round(LOOP_SECONDS * FPS))
    frames = tc.build_frames(rig, lambda t: tl.pose(t / td.BEAT), [i / FPS for i in range(n + 1)], td.style_for(style))
    js = tc.to_json(rig, frames, FPS, name='thriller_%s' % fam)
    return rig, js, style


def check_anim(fam, rig, js, tl, style):
    """pac playback simulation (linear lerp of the Euler triples between 30 fps frames) against the exact solver pose, loop closure, pole proximity, feet"""
    import run2
    s, top = run2.replay_detail(rig, tl, js, td, style, top=2)
    closure = run2.closure(js)
    gim = run2.gimbal(js, 75.0)
    fd = js['FrameData']
    nb = len(fd[0]['BoneInfo'])
    ok = closure < 0.01 and not gim and s['p99'] < 8 and s['max'] < 30
    print('  %-7s %3d bones %4d frames | replay vs exact: mean %.2f p99 %.1f max %.1f deg | closure %.2f | pitch>75: %s | %s' %
          (fam, nb, len(fd), s['mean'], s['p99'], s['max'], closure, gim or 'none', 'OK' if ok else 'CHECK'))
    return ok


def write_anims(tl, repo, only=None):
    t0 = time.time()
    allok = True
    for fam in FAMILIES:
        rig, js, style = build_anim(fam, tl)
        allok &= check_anim(fam, rig, js, tl, style)
        d = os.path.join(repo, 'anim', 'thriller', fam)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, 'thriller_%s.json' % fam)
        with open(path, 'w', newline='\n') as f:
            json.dump(js, f, separators=(',', ':'))
        print('          wrote %s (%d bytes)' % (os.path.relpath(path, repo), os.path.getsize(path)))
    print('animations %.0fs' % (time.time() - t0))
    return allok


# ---------------------------------------------------------------------------------------------------------------------------- outfits
def anim_url(fam):
    return RAW + 'anim/thriller/%s/thriller_%s.json' % (fam, fam)


def player_anim(slug, fam):
    return {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear', 'Name': 'your dance: thriller_%s.json' % fam,
            'StopOtherAnimations': True, 'URL': anim_url(fam), 'UniqueID': uid(slug, 'anim_player')}


def rise_expr():
    u = 'clamp(timeex()/%s, 0, 1)' % ('%g' % RISE_SECONDS)
    return '-%d * (1 - %s^2 * (3 - 2*%s))' % (RISE_DEPTH, u, u)


def zombie_part(slug, side, y):
    mdl = {'Bone': 'pos_ang', 'ClassName': 'model2', 'Model': 'models/zombie/classic.mdl', 'Name': 'zombie %s (HL2 classic zombie, dances with you)' % side,
           'Position': vec(ZOMBIE_X, y, 0), 'UniqueID': uid(slug, 'zombie_' + side)}
    anim = {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear', 'Name': 'zombie dance: thriller_zombie.json',
            'StopOtherAnimations': False, 'URL': anim_url('zombie'), 'UniqueID': uid(slug, 'anim_zombie_' + side)}
    rise = {'Axis': 'z', 'ClassName': 'proxy', 'Expression': rise_expr(), 'Name': 'rises out of the ground (%g s)' % RISE_SECONDS, 'VariableName': 'Position',
            'UniqueID': uid(slug, 'rise_' + side)}
    return part(3, mdl, part(5, anim) + part(5, rise))


def outfit(slug, title, fam=None):
    kids = ''
    if fam:
        kids += part(3, player_anim(slug, fam))
    kids += zombie_part(slug, 'left', ZOMBIE_Y)
    kids += zombie_part(slug, 'right', -ZOMBIE_Y)
    kids += part(3, sound2(slug, 'sound_loop', MUSIC_FILE, MUSIC_PLAYS, 1.0, name='thriller loop (16 s = one dance loop)'))
    ev = {'AffectChildrenOnly': True, 'Arguments': COMMAND, 'ClassName': 'event', 'Event': 'command', 'Invert': True, 'Operator': 'equal',
          'Name': 'Thriller  (pac_event %s 2)' % COMMAND, 'UniqueID': uid(slug, 'event')}
    root = {'ClassName': 'group', 'EditorExpand': True, 'Name': title, 'Notes': WATERMARK, 'UniqueID': uid(slug, 'root')}
    return '-- ' + WATERMARK + '\n\n["self"] = {\n' + table(1, root) + '},\n["children"] = {\n' + part(1, ev, kids) + '},\n'


LIMITS = {'parts': (500, 3000), 'model2': (60, 150), 'proxy': (100, None), 'event': (150, None)}
BANNED = ('light', 'light2', 'halo', 'projected_texture', 'shake', 'sunbeams')


def check_outfit(path):
    text = open(path, 'rb').read().decode('utf-8')
    probs, nids = verify(text)
    t = pp.parse(text)
    counts = {}
    urls = []
    for depth, s, node in pp.walk(t):
        c = s['ClassName']
        counts[c] = counts.get(c, 0) + 1
        for k in ('URL', 'Path', 'Model'):
            if isinstance(s.get(k), str) and s[k].startswith('http'):
                urls.append(s[k])
        if c in BANNED:
            probs.append('banned class ' + c)
        if c == 'event':
            if not (s.get('AffectChildrenOnly') is True and s.get('Invert') is True and s.get('Operator') == 'equal' and s.get('Arguments') == COMMAND):
                probs.append('event flags')
    total = sum(counts.values())
    if total > LIMITS['parts'][0]:
        probs.append('parts above the heavy threshold')
    if counts.get('model2', 0) > LIMITS['model2'][0]:
        probs.append('model2 above the heavy threshold')
    return probs, counts, urls


def write_outfits(repo, pac_dir):
    os.makedirs(pac_dir, exist_ok=True)
    out2 = os.path.join(repo, 'outfits', 'thriller')
    os.makedirs(out2, exist_ok=True)
    sets = [('thriller_zombies', 'thriller: 2 zombies + music (any playermodel; pac_event thriller 2)', None)]
    for fam in ('ethics', 'classd', 'isd', 'medic'):
        sets.append(('thriller_' + fam, 'thriller: 2 zombies + your dance + music (%s; pac_event thriller 2)' % FAMILIES[fam][2], fam))
    allok = True
    for slug, title, fam in sets:
        text = outfit(slug, title, fam)
        for d in (pac_dir, out2):
            with open(os.path.join(d, slug + '.txt'), 'w', encoding='utf-8', newline='') as f:
                f.write(text)
        probs, counts, urls = check_outfit(os.path.join(pac_dir, slug + '.txt'))
        allok &= not probs
        print('  %-18s %5d bytes  parts %d (%s)  %s' % (slug + '.txt', len(text), sum(counts.values()), ', '.join('%s %d' % kv for kv in sorted(counts.items())), 'OK' if not probs else probs))
    return allok, sets


def write_audio(repo):
    """the music loop is cut by make_audio.py (python make_audio.py SRC out/audio/thriller_dance.mp3 --downbeat 270.0708); this just places it in the repo root"""
    import shutil
    src = os.path.join(HERE, 'out', 'audio', MUSIC_FILE)
    if not os.path.exists(src):
        print('  (no %s in out/audio: run make_audio.py first)' % MUSIC_FILE)
        return False
    shutil.copyfile(src, os.path.join(repo, MUSIC_FILE))
    print('  copied %s (%d bytes) to the repo root' % (MUSIC_FILE, os.path.getsize(src)))
    return True


def main():
    repo = sys.argv[sys.argv.index('--repo') + 1] if '--repo' in sys.argv else REPO
    pac_dir = sys.argv[sys.argv.index('--pac') + 1] if '--pac' in sys.argv else PAC_DIR
    tl = td.Timeline()
    ok = True
    if '--no-anim' not in sys.argv:
        ok &= write_anims(tl, repo)
    if '--no-audio' not in sys.argv:
        ok &= write_audio(repo)
    ok &= write_outfits(repo, pac_dir)[0]
    print('ALL OK' if ok else 'SOMETHING NEEDS A LOOK')


if __name__ == '__main__':
    main()
