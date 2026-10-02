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
    """Cycling probe, arms forward the whole time. Hips (game-world units, applied as a parent-space offset):
    rest -> 20 forward -> 20 up -> 20 to the character's left -> rest, 2 s per leg. Tells us in one watch whether custom_animation works
    AND exactly how the pelvis position offset maps to game axes (describe the order of movements you see)."""
    def fr(rate, dp):
        MF, MR, MU = dp[0], -dp[1], dp[2]     # (x, y, z) = (MF, -MR, MU)
        bi = {'ValveBiped.Bip01_R_UpperArm': {'RR': 0, 'RU': -90, 'RF': 0}, 'ValveBiped.Bip01_L_UpperArm': {'RR': 0, 'RU': -90, 'RF': 0},
              'ValveBiped.Bip01_Pelvis': {'RR': 0, 'RU': 0, 'RF': 0, 'MF': MF, 'MR': MR, 'MU': MU}}
        return {'FrameRate': rate, 'BoneInfo': bi}
    js = {'Type': 'sequence', 'Interpolation': 'linear', 'RestartFrame': 1,
          'FrameData': [fr(2, (0, 0, 0)), fr(0.5, (20, 0, 0)), fr(0.5, (0, 0, 20)), fr(0.5, (0, 20, 0)), fr(0.5, (0, 0, 0))]}
    return json.dumps(js, separators=(',', ':'))


def build_all(out_dir=PAC_DIR):
    data = test_data()
    sets = [
        ('emote_samba', 'emote: samba (ISD / GOC / tech expert)', [
            ('samba', 'samba (with hip travel)', anim_part('emote_samba', 'a_samba', 'samba.json', url=ANIM_URL + 'samba.json')),
            ('sambastill', 'samba (no hip travel, fallback)', anim_part('emote_samba', 'a_still', 'samba_still.json', url=ANIM_URL + 'samba_still.json')),
            ('animtest', 'readiness test: arms forward, hips cycle forward / up / left', anim_part('emote_samba', 'a_test', 'animtest (inline data)', data=data))]),
        ('emote_samba_medic', 'emote: samba (combat medic)', [
            ('samba', 'samba (with hip travel)', anim_part('emote_samba_medic', 'a_samba', 'samba_medic.json', url=ANIM_URL + 'samba_medic.json')),
            ('animtest', 'readiness test: arms forward, hips cycle forward / up / left', anim_part('emote_samba_medic', 'a_test', 'animtest (inline data)', data=data))]),
        ('emote_samba_classd', 'emote: samba (D-class)', [
            ('samba', 'samba (with hip travel)', anim_part('emote_samba_classd', 'a_samba', 'samba_classd.json', url=ANIM_URL + 'samba_classd.json')),
            ('animtest', 'readiness test: arms forward, hips cycle forward / up / left', anim_part('emote_samba_classd', 'a_test', 'animtest (inline data)', data=data))]),
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
