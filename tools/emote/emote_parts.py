"""pac3 part builders for the emote outfits (the class names and property sets of the user's OLD pac3 build: model2 / sound2 / event / sprite / trail2 / particles).

Everything returns the property dict of one part; make_emote_outfit.part(indent, dict, children_text) turns it into text.
Props that follow the animation sit on a carrier bone (see emote_props.py): Bone "attach left hand" / "attach right hand".
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_emote_outfit import uid, part

RAW_URL = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/%s'


class Raw(object):
    """a value that is written verbatim (Angle(...), Vector(...), Color(...))"""
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def vec(x, y, z):
    return Raw('Vector(%s, %s, %s)' % (_n(x), _n(y), _n(z)))


def ang(p, y, r):
    return Raw('Angle(%s, %s, %s)' % (_n(p), _n(y), _n(r)))


def _n(v):
    s = ('%.4f' % v).rstrip('0').rstrip('.')
    return s if s not in ('-0', '') else '0'


# ---------------------------------------------------------------- sound / event
def sound2(slug, uid_key, path_file, plays, volume=1.0, name='', radius=500):
    """The user's own web sound setup (Bone head, Radius 500, StopOnHide) with an explicit file / PlayCount / Volume."""
    return {'AimPartName': '', 'AimPartUID': '', 'AngleOffset': ang(0, 0, 0), 'Angles': ang(0, 0, 0), 'Bone': 'head', 'ClassName': 'sound2',
            'Doppler': False, 'DrawOrder': 0, 'Echo': False, 'EchoDelay': 0.5, 'EchoFeedback': 0.75, 'EditorExpand': False, 'EyeAngles': False, 'FilterFraction': 1,
            'FilterType': 0, 'Hide': False, 'IsDisturbing': False, 'MaxPitch': 0, 'MinPitch': 0, 'Name': name, 'Overlapping': False, 'Path': RAW_URL % path_file,
            'PauseOnHide': False, 'Pitch': 1, 'PitchLFOAmount': 0, 'PitchLFOTime': 0, 'PlayCount': plays, 'PlayOnFootstep': False, 'Position': vec(0, 0, 0),
            'PositionOffset': vec(0, 0, 0), 'Radius': radius, 'StopOnHide': True, 'TargetEntityUID': '', 'UniqueID': uid(slug, uid_key), 'Volume': volume,
            'VolumeLFOAmount': 0, 'VolumeLFOTime': 0}


def timerx_event(slug, uid_key, seconds, name):
    """Shows its children `seconds` after it was itself shown (the command event shows it when the emote starts, so this is 'seconds after the emote started').
    Arguments pack: seconds@@reset_on_hide@@synced_time. Old-build rule: AffectChildrenOnly true, Invert true = show while the condition is true."""
    return {'AffectChildrenOnly': True, 'Arguments': '%s@@1@@0' % _n(seconds), 'ClassName': 'event', 'Event': 'timerx', 'Invert': True, 'Operator': 'above',
            'Name': name, 'UniqueID': uid(slug, uid_key)}


# ---------------------------------------------------------------- models and effects
def model_obj(slug, uid_key, name, model, bone, color=(1.0, 1.0, 1.0), material='', size=1.0, position=(0, 0, 0), angles=(0, 0, 0), brightness=None,
              no_lighting=False, alpha=None, translucent=False):
    """model2. `model` is a repo path ending in .obj (loaded as a URL model) or a game model path."""
    url = model.endswith('.obj')
    d = {'Bone': bone, 'ClassName': 'model2', 'Color': vec(*color), 'Model': (RAW_URL % model) if url else model, 'Name': name, 'UniqueID': uid(slug, uid_key)}
    if url:
        d['ForceObjUrl'] = True
    if material:
        d['Material'] = material
    if size != 1.0:
        d['Size'] = size
    if any(position):
        d['Position'] = vec(*position)
    if any(angles):
        d['Angles'] = ang(*angles)
    if brightness is not None:
        d['Brightness'] = brightness
    if no_lighting:
        d['NoLighting'] = True
    if alpha is not None:
        d['Alpha'] = alpha
    if translucent:
        d['Translucent'] = True
    return d


def sprite(slug, uid_key, name, bone, path, size, color=(255, 255, 255), alpha=1.0):
    """billboard glow. Color is 0..255 on sprites."""
    d = {'Bone': bone, 'ClassName': 'sprite', 'Color': vec(*color), 'Name': name, 'SizeX': size, 'SizeY': size, 'SpritePath': path, 'UniqueID': uid(slug, uid_key)}
    if alpha != 1.0:
        d['Alpha'] = alpha
    return d


def trail2(slug, uid_key, name, bone, start_color, end_color, start_size, duration, path='trails/laser', end_size=0.0):
    """trail2 (develop trail class; the user's server has it). Colors are 0..1 here."""
    return {'Bone': bone, 'ClassName': 'trail2', 'Duration': duration, 'EndColor': vec(*end_color), 'EndSize': end_size, 'Name': name, 'StartColor': vec(*start_color),
            'StartSize': start_size, 'TrailPath': path, 'UniqueID': uid(slug, uid_key)}


def sparkles(slug, uid_key, name, bone, color1=(120, 220, 255), color2=(255, 255, 255), size=3.0, life=0.5, rate=0.04):
    """a few small glowing dots drifting off a bone (particles, property names as saved by the user's editor)"""
    return {'Bone': bone, 'ClassName': 'particles', 'Collide': False, 'Color1': vec(*color1), 'Color2': vec(*color2), 'DieTime': life, 'EndAlpha': 0, 'EndSize': 0.0,
            'FireDelay': rate, 'Gravity': vec(0, 0, -12), 'Lighting': False, 'Material': 'sprites/light_glow02_add', 'Name': name, 'NumberParticles': 1,
            'RandomColor': True, 'Spread': 0.7, 'StartAlpha': 255, 'StartSize': size, 'UniqueID': uid(slug, uid_key), 'Velocity': 10}


# ---------------------------------------------------------------- per-emote extras (children of the emote's command event, after the animation)
def extras_thoughtiwasdead(slug, family):
    """Gold trumpet on the left carrier bone (held, thrown, parked by the animation itself) + the trumpet intro, then the loop 4.52 s later."""
    kids = part(3, model_obj(slug, 'trumpet', 'trumpet (rides the animation)', 'obj/props/trumpet.obj', 'attach left hand', color=(1.0, 0.78, 0.25), material='models/shiny'))
    kids += part(3, sound2(slug, 'sound_intro', 'thought_i_was_dead_intro.mp3', 1, 0.8, name='trumpet intro (lead silence = 0.25 s ease-in + 0.2 s)'))
    loop = sound2(slug, 'sound_thoughtiwasdead', 'thought_i_was_dead.mp3', 24, 0.45, name='loop')
    kids += part(3, timerx_event(slug, 'event_loop', 4.5167, 'loop starts 4.52 s after the emote (intro length)'), part(5, loop))
    return kids


def extras_mystery(slug, family):
    """I'm a Mystery: the orb (right carrier) and the hoop (left carrier) are choreographed by the animation itself (emote_props.py); trails and sparkles ride real bones;
    music = a sting with the lead silence folded in, plus the 29.3 s loop rotated so its downbeat lands on the dance loop (no timer involved)."""
    R, L = 'attach right hand', 'attach left hand'
    kids = ''
    kids += part(3, model_obj(slug, 'orb_core', 'orb (rides the right carrier bone)', 'models/hunter/misc/sphere025x025.mdl', R, color=(0.9, 0.98, 1.0),
                              material='models/debug/debugwhite', size=0.37, no_lighting=True))
    kids += part(3, sprite(slug, 'orb_glow', 'orb glow', R, 'sprites/light_glow02_add', 16, (170, 230, 255)))
    kids += part(3, sprite(slug, 'orb_halo', 'orb halo', R, 'sprites/light_glow02_add', 42, (60, 170, 255), 0.4))
    kids += part(3, model_obj(slug, 'hoop', 'hoop (rides the left carrier bone)', 'obj/props/hoop.obj', L, color=(0.65, 0.96, 1.0), material='models/debug/debugwhite', no_lighting=True))
    kids += part(3, model_obj(slug, 'hoop_halo', 'hoop halo', 'obj/props/hoop_glow.obj', L, color=(0.15, 0.65, 1.0), material='models/debug/debugwhite', no_lighting=True,
                              alpha=0.28, translucent=True))
    for key, bone in (('r_hand', 'right hand'), ('l_hand', 'left hand'), ('r_foot', 'right foot'), ('l_foot', 'left foot')):
        kids += part(3, trail2(slug, 'trail_' + key, 'swoosh ' + bone, bone, (0.6, 0.97, 1.0), (0.1, 0.45, 1.0), 3.6, 0.32))
    for key, bone in (('r_hand', 'right hand'), ('l_hand', 'left hand')):
        kids += part(3, sparkles(slug, 'spark_' + key, 'sparkles ' + bone, bone))
    kids += part(3, sound2(slug, 'sound_sting', 'im_a_mystery_sting.mp3', 1, 0.9, name='sting (lead silence = pac 0.25 s ease-in)'))
    kids += part(3, sound2(slug, 'sound_mystery', 'im_a_mystery.mp3', 12, 0.9, name='loop, rotated 0.617 s (downbeat on the dance loop start)'))
    return kids


def extras_touchingthesky(slug, family):
    """Touching The Sky: ActMod's two tracks untouched (1.07 s intro, 14.93 s loop = two dance loops). ActMod starts them 0.01 s and 1.0667 s after the emote on its own clock, but the animation here starts
    0.25 s late (pac's ease-in), so each track sits under its own timerx event (0.26 s and 1.3167 s) inside the command event. Part keys carry a tts_ prefix: UniqueIDs are hashed per outfit, not per emote."""
    intro = sound2(slug, 'tts_sound_intro', 'touching_the_sky_intro.mp3', 1, 0.65, name='intro')
    loop = sound2(slug, 'tts_sound_loop', 'touching_the_sky.mp3', 24, 0.65, name='loop')
    kids = part(3, timerx_event(slug, 'tts_event_intro', 0.26, 'intro starts 0.26 s after the emote (ActMod delay 0.01 s + pac ease-in 0.25 s)'), part(5, intro))
    kids += part(3, timerx_event(slug, 'tts_event_loop', 1.3167, 'loop starts 1.32 s after the emote (ActMod delay 1.0667 s + pac ease-in 0.25 s)'), part(5, loop))
    return kids


EXTRA_PARTS = {'thoughtiwasdead': extras_thoughtiwasdead, 'mystery': extras_mystery, 'touchingthesky': extras_touchingthesky}
# commands whose sound parts the extras build themselves (the generic MUSIC entry is skipped for them)
CUSTOM_SOUND = {'thoughtiwasdead', 'mystery', 'touchingthesky'}
