"""Shared helpers for the advanced outfit builders: accent palettes + the theme / pulse proxy expressions (only functions every pac3 build has: sin, abs, max, min, time, command, voice_volume)."""
import numpy as np

import adv_parts as ap

PALETTE_NEON = [(1.0, 0.12, 0.55), (0.08, 0.85, 1.0), (0.55, 1.0, 0.15), (1.0, 0.45, 0.08)]       # magenta, cyan, toxic green, orange
PALETTE_HAIR = [(0.80, 0.83, 0.91), (0.06, 0.06, 0.08), (0.96, 0.96, 1.0), (1.0, 0.55, 0.78)]       # silver, black, white, pink


def theme_expr(cmd, palette, scale, pulse='1'):
    """three comma separated colour components: a smooth blend between the palette entries selected by command(cmd), times `pulse`"""
    comps = []
    for c in range(3):
        terms = ['max(1-abs(command("%s")-%d),0)*%.3f' % (cmd, i, palette[i][c] * scale) for i in range(len(palette))]
        comps.append('(%s)*%s' % (' + '.join(terms), pulse))
    return ', '.join(comps)


PULSE_VOICE = '(0.84 + 0.16*sin(time()*2.2) + min(voice_volume()*1.5, 0.6))'
PULSE_SOFT = '(0.9 + 0.1*sin(time()*2.2))'


def friendly_bone(short):
    return ap.bone_name(short)


def tip_position(rig, parent, tip, extend=0.55):
    """world position a little beyond a finger tip bone, along parent -> tip"""
    p0 = rig.world[rig.idx['ValveBiped.Bip01_' + parent]][:3, 3]
    p1 = rig.world[rig.idx['ValveBiped.Bip01_' + tip]][:3, 3]
    d = (p1 - p0) / max(np.linalg.norm(p1 - p0), 1e-9)
    return p1 + d * extend
