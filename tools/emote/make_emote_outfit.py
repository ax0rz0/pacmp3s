"""Write PAC3 outfit files that play converted emotes (custom_animation parts behind command events).

python make_emote_outfit.py                      # builds the samba outfits for the ISD/GOC/tech, medic and class D families
Each event is `command` + Arguments=<name>; trigger with  pac_event <name> 2  (toggle), bind it to a key.
"""
import hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'
ANIM_URL = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/anim/'
WATERMARK = 'claude skill made by ax0rz0'


def uid(slug, key):
    return hashlib.sha256((slug + ':' + key).encode()).hexdigest()[:59] + 'a0c3f'


def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def fmt(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return q(v)
    return repr(v)


def table(indent, d):
    t = '\t' * indent
    return ''.join('%s["%s"] = %s,\n' % (t, k, fmt(d[k])) for k in sorted(d))


def part(indent, selfd, children=''):
    t = '\t' * indent
    return (t + '{\n' + t + '\t["self"] = {\n' + table(indent + 2, selfd) + t + '\t},\n' +
            t + '\t["children"] = {\n' + children + t + '\t},\n' + t + '},\n')


def anim_part(slug, key, name, url=None, data=None):
    d = {'AnimationType': 'sequence', 'ClassName': 'custom_animation', 'Interpolation': 'linear',
         'Name': name, 'UniqueID': uid(slug, key)}
    if url:
        d['URL'] = url
    if data:
        d['Data'] = data
    return d


def emote_event(slug, command, title, anim):
    ev = {'AffectChildrenOnly': True, 'Arguments': command, 'ClassName': 'event', 'Event': 'command',
          'Invert': True, 'Name': title, 'UniqueID': uid(slug, 'event_' + command)}
    return part(1, ev, part(3, anim))


def outfit(slug, title, emotes):
    root = {'ClassName': 'group', 'EditorExpand': True, 'Name': title, 'Notes': WATERMARK, 'UniqueID': uid(slug, 'root')}
    kids = ''.join(emote_event(slug, c, t, a) for c, t, a in emotes)
    return ('-- ' + WATERMARK + '\n\n["self"] = {\n' + table(1, root) + '},\n["children"] = {\n' + kids + '},\n')


def verify(text):
    problems = []
    if text.startswith('\ufeff'): problems.append('BOM')
    if not text.startswith('-- ' + WATERMARK + '\n\n'): problems.append('header')
    if '\r' in text: problems.append('CR')
    if not text.endswith('\n'): problems.append('no trailing newline')
    if text.count('{') != text.count('}'): problems.append('unbalanced braces')
    ids = re.findall(r'\["UniqueID"\] = "([^"]*)"', text)
    if any(len(i) != 64 or not re.fullmatch(r'[0-9a-f]{64}', i) or not i.endswith('a0c3f') for i in ids): problems.append('bad UID')
    if len(ids) != len(set(ids)): problems.append('duplicate UID')
    return problems, len(ids)


def test_data():
    """Tiny inline clip: both arms straight forward + hips pushed 10 forward and 6 down (game-world). Tells us in one look
    whether custom_animation works on the server AND which way ManipulateBonePosition moves the pelvis."""
    import numpy as np
    from mdl_anim import load_model
    from retarget import Valve
    v = Valve(load_model('models/frostbyte/ia/internalsecurity_erdim.mdl'))
    pel = v.bone('Pelvis')
    t = v.Lr[pel].T @ np.array([10.0, 0.0, -6.0])
    bi = {'ValveBiped.Bip01_R_UpperArm': {'RR': 0, 'RU': -90, 'RF': 0}, 'ValveBiped.Bip01_L_UpperArm': {'RR': 0, 'RU': -90, 'RF': 0},
          'ValveBiped.Bip01_Pelvis': {'RR': 0, 'RU': 0, 'RF': 0, 'MF': round(float(t[0]), 2), 'MR': round(float(-t[1]), 2), 'MU': round(float(t[2]), 2)}}
    js = {'Type': 'sequence', 'Interpolation': 'linear', 'RestartFrame': 2,
          'FrameData': [{'FrameRate': 2, 'BoneInfo': bi}, {'FrameRate': 1, 'BoneInfo': bi}]}
    return json.dumps(js, separators=(',', ':'))


def build_all(out_dir=PAC_DIR):
    data = test_data()
    sets = [
        ('emote_samba', 'emote: samba (ISD / GOC / tech expert)', [
            ('samba', 'samba (with hip travel)', anim_part('emote_samba', 'a_samba', 'samba.json', url=ANIM_URL + 'samba.json')),
            ('sambastill', 'samba (no hip travel, fallback)', anim_part('emote_samba', 'a_still', 'samba_still.json', url=ANIM_URL + 'samba_still.json')),
            ('animtest', 'readiness test: arms forward, hips forward+down', anim_part('emote_samba', 'a_test', 'animtest (inline data)', data=data))]),
        ('emote_samba_medic', 'emote: samba (combat medic)', [
            ('samba', 'samba (with hip travel)', anim_part('emote_samba_medic', 'a_samba', 'samba_medic.json', url=ANIM_URL + 'samba_medic.json')),
            ('animtest', 'readiness test: arms forward, hips forward+down', anim_part('emote_samba_medic', 'a_test', 'animtest (inline data)', data=data))]),
        ('emote_samba_classd', 'emote: samba (D-class)', [
            ('samba', 'samba (with hip travel)', anim_part('emote_samba_classd', 'a_samba', 'samba_classd.json', url=ANIM_URL + 'samba_classd.json')),
            ('animtest', 'readiness test: arms forward, hips forward+down', anim_part('emote_samba_classd', 'a_test', 'animtest (inline data)', data=data))]),
    ]
    for slug, title, emotes in sets:
        text = outfit(slug, title, emotes)
        probs, n = verify(text)
        path = os.path.join(out_dir, slug + '.txt')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        print('%-22s %6d bytes  %d ids  %s' % (slug + '.txt', len(text), n, 'OK' if not probs else probs))
    print('test clip:', data)


if __name__ == '__main__':
    build_all()
