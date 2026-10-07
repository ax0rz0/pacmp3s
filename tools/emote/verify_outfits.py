"""Independent check of the generated outfits against the repo: python verify_outfits.py OUTFIT.txt [...]
Checks per outfit: no BOM / CR, watermark line and root Notes, 64-hex UniqueIDs ending a0c3f and unique, command events (Operator equal, Invert, AffectChildrenOnly), one custom_animation per emote whose URL maps to a JSON file in the repo,
every sound / model URL maps to a repo file, and the three outfits hold the same emotes. Also writes pacmp3s_live_urls.json into the temp folder (every URL the outfits use + the repo file's size) for check_live.py."""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pac_parse as pp

REPO = os.path.expanduser('~/OneDrive/Documents/GitHub/pacmp3s')
LIVE_URLS = os.path.join(tempfile.gettempdir(), 'pacmp3s_live_urls.json')
RAW = 'https://raw.githubusercontent.com/ax0rz0/pacmp3s/refs/heads/main/'
GH = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
WM = 'claude skill made by ax0rz0'
problems = []
urls = {}


def bad(msg):
    problems.append(msg)
    print('  PROBLEM:', msg)


def local_for(url):
    for base in (RAW, GH):
        if url.startswith(base):
            return os.path.join(REPO, url[len(base):].replace('/', os.sep))
    return None


def audio_len(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def check(path):
    print('==', os.path.basename(path))
    raw = open(path, 'rb').read()
    if raw[:3] == b'\xef\xbb\xbf':
        bad('BOM')
    if b'\r' in raw:
        bad('CR characters')
    text = raw.decode('utf-8')
    if not text.startswith('-- ' + WM + '\n\n["self"] = {\n'):
        bad('header / watermark line')
    if not text.endswith('},\n'):
        bad('tail: ' + repr(text[-20:]))
    t = pp.parse(text)
    if t['self'].get('Notes') != WM or t['self'].get('ClassName') != 'group':
        bad('root self')
    ids = []
    classes = {}
    for depth, s, node in pp.walk(t):
        u = s.get('UniqueID', '')
        ids.append(u)
        classes[s['ClassName']] = classes.get(s['ClassName'], 0) + 1
        if not re.fullmatch(r'[0-9a-f]{64}', u) or not u.endswith('a0c3f'):
            bad('UniqueID %r' % u)
    if len(set(ids)) != len(ids):
        bad('duplicate UniqueIDs: %d of %d' % (len(ids) - len(set(ids)), len(ids)))
    print('  parts %d, ids unique %d, classes %s' % (len(ids), len(set(ids)), dict(sorted(classes.items()))))
    cmds = []
    kids = t['children']
    fam = {'emote_fortnite': 'classd', 'emote_fortnite_isd': 'isd', 'emote_fortnite_medic': 'medic'}[os.path.splitext(os.path.basename(path))[0]]
    sound_total = {}
    for k in sorted(kids):
        ev = kids[k]
        s = ev['self']
        key = s['Arguments']
        cmds.append(key)
        if (s['ClassName'], s['Event'], s['Operator'], s.get('Invert'), s.get('AffectChildrenOnly')) != ('event', 'command', 'equal', True, True):
            bad('event %s: %r' % (key, s))
        sub = [(d, ss) for d, ss, _ in pp.walk(ev) if d > 0]
        anims = [ss for d, ss in sub if ss['ClassName'] == 'custom_animation']
        if len(anims) != 1:
            bad('%s: %d animations' % (key, len(anims)))
            continue
        a = anims[0]
        if not a.get('StopOtherAnimations'):
            bad('%s: StopOtherAnimations' % key)
        m = re.fullmatch(re.escape(RAW) + r'anim/(fn|am)/%s/(fn|am)_%s\.json' % (fam, re.escape(key)), a['URL'])
        if not m or m.group(1) != m.group(2):
            bad('%s: animation URL %s' % (key, a['URL']))
        lp = local_for(a['URL'])
        urls[a['URL']] = os.path.getsize(lp) if lp and os.path.exists(lp) else None
        if not lp or not os.path.exists(lp):
            bad('%s: animation file missing %s' % (key, lp))
        else:
            js = json.load(open(lp, encoding='utf-8'))
            if js.get('Type') != 'sequence' or not js.get('FrameData'):
                bad('%s: json shape' % key)
        for d, ss in sub:
            for prop in ('Path', 'Model'):
                v = ss.get(prop)
                if isinstance(v, str) and v.startswith('http'):
                    lp = local_for(v)
                    if not lp or not os.path.exists(lp):
                        bad('%s: %s %s missing in the repo' % (key, ss['ClassName'], v))
                    else:
                        urls[v] = os.path.getsize(lp)
                        if prop == 'Path':
                            dur = audio_len(lp)
                            sound_total.setdefault(key, []).append((os.path.basename(lp), dur, ss.get('PlayCount'), ss.get('Volume')))
            if ss['ClassName'] == 'model2' and isinstance(ss.get('Model'), str) and ss['Model'].startswith('http') and not ss.get('ForceObjUrl'):
                bad('%s: url model without ForceObjUrl' % key)
            if ss['ClassName'] == 'model2' and isinstance(ss.get('Model'), str) and ss['Model'].startswith('http') and not ss['Model'].endswith('.obj'):
                bad('%s: url model name must end in .obj' % key)
    print('  emotes %d (unique %d)' % (len(cmds), len(set(cmds))))
    for key in ('thoughtiwasdead', 'mystery', 'headbanger', 'touchingthesky', 'leiltelomr'):     # the emotes with custom or special sound setups
        print('  -- %s: %s' % (key, '; '.join('%s %.2fs x%s vol %s' % (n, d or -1, c, v) for n, d, c, v in sound_total.get(key, []))))
        total = sum((d or 0) * c for n, d, c, v in sound_total.get(key, []) if c)
        print('     total audio queued: %.0f s' % total)
    return cmds


if __name__ == '__main__':
    allc = {}
    for p in sys.argv[1:]:
        allc[p] = check(p)
    if len({tuple(v) for v in allc.values()}) != 1:
        bad('the three outfits do not hold the same emotes in the same order')
    json.dump(urls, open(LIVE_URLS, 'w'), indent=1)
    print('urls written: %d' % len(urls))
    print('PROBLEMS: %d' % len(problems))
    sys.exit(1 if problems else 0)
