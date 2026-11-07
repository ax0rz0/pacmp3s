"""small helpers shared by the generators: the emote pack's part / table writers, root blocks for the multi-root file format of the user's saved outfits, and a few part builders"""
import os
import sys

sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\emote')
from make_emote_outfit import uid, table, part, verify, PAC_DIR, WATERMARK          # noqa: E402,F401
from emote_parts import Raw, vec, ang, sound2, timerx_event, sprite                  # noqa: E402,F401
import pac_parse as pp                                                               # noqa: E402,F401

REPO = r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s'
RAW = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/'
GH = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
FLAT = 'models/debug/debugwhite'


def command_event(slug, command, title, key='event'):
    """the emote pack's command event (old build): shown while `pac_event <command> 2` is on"""
    return {'AffectChildrenOnly': True, 'Arguments': command, 'ClassName': 'event', 'Event': 'command', 'Invert': True, 'Operator': 'equal', 'Name': title, 'UniqueID': uid(slug, key)}


def model2(slug, key, name, model, bone, pos, scale=None, size=None, color=None, material=None, angles=None, no_lighting=False, alpha=None):
    d = {'Bone': bone, 'ClassName': 'model2', 'Model': model, 'Name': name, 'UniqueID': uid(slug, key)}
    if any(abs(v) > 1e-9 for v in pos):
        d['Position'] = vec(*pos)
    if scale is not None:
        d['Scale'] = vec(*scale)
    if size is not None and size != 1:
        d['Size'] = size
    if color is not None:
        d['Color'] = vec(*color)
    if material:
        d['Material'] = material
    if angles is not None and any(abs(a) > 1e-6 for a in angles):
        d['Angles'] = ang(*angles)
    if no_lighting:
        d['NoLighting'] = True
    if alpha is not None:
        d['Alpha'] = alpha
    return d


def root_block(index, slug, title, children_text, expand=True):
    """one root of the multi-root file (the format of the user's saved outfits: [1] = {...}, [2] = {...}, ...)"""
    root = {'ClassName': 'group', 'EditorExpand': expand, 'Name': title, 'Notes': WATERMARK, 'UniqueID': uid(slug, 'root')}
    return '[%d] = {\n\t["children"] = {\n%s\t},\n\t["self"] = {\n%s\t},\n},\n' % (index, children_text, table(2, root))


def standalone(slug, title, children_text):
    root = {'ClassName': 'group', 'EditorExpand': True, 'Name': title, 'Notes': WATERMARK, 'UniqueID': uid(slug, 'root')}
    return '-- ' + WATERMARK + '\n\n["self"] = {\n' + table(1, root) + '},\n["children"] = {\n' + children_text + '},\n'


def indent_block(text, extra):
    """shift a block of generated part text right by `extra` tab stops (parts are written for indent 1; the multi-root file wants them at 2)"""
    pad = '\t' * extra
    return ''.join(pad + line if line.strip() else line for line in text.splitlines(True))
