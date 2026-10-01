"""PAC3 outfit text writer / verifier / tiny Lua-table parser for the pin badge generator.

See SPEC.md 'PAC outfit rules'. Public API:
    outfit_text(manifest, bone, position, angles) -> str
    write_outfit(manifest, path, **kw)            -> path
    verify_outfit(path)                           -> dict
    parse_outfit(text)                            -> nested dict (round-trip proof)
"""
import json
import os
import re
import sys

try:
    from pin_common import (DEFAULT_ANGLES, DEFAULT_BONE, DEFAULT_POSITION, GLOSS_ALPHA,
                            RAW_BASE, REPO, WATERMARK, uid)
except ImportError:  # imported as part of a package
    from .pin_common import (DEFAULT_ANGLES, DEFAULT_BONE, DEFAULT_POSITION, GLOSS_ALPHA,
                             RAW_BASE, REPO, WATERMARK, uid)

HEADER = '-- ' + WATERMARK
DEBUG_WHITE = 'models/debug/debugwhite'


# ---------------------------------------------------------------- value formatting
def fmt_num(x):
    """Up to 4 decimals, trailing zeros stripped, never '-0'."""
    s = '%.4f' % float(x)
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s in ('-0', ''):
        s = '0'
    return s


def lua_q(s):
    """Lua %q-style string literal (backslash, quote, newline; CR and NUL as escapes)."""
    out = ['"']
    for ch in str(s):
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\0':
            out.append('\\0')
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


class Vec(tuple):
    """Marker for Vector(x, y, z)."""
    func = 'Vector'


class Ang(tuple):
    """Marker for Angle(p, y, r)."""
    func = 'Angle'


def fmt_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (Vec, Ang)):
        return '%s(%s)' % (v.func, ', '.join(fmt_num(c) for c in v))
    if isinstance(v, (int, float)):
        return fmt_num(v)
    if isinstance(v, str):
        return lua_q(v)
    raise TypeError('cannot format %r' % (v,))


# ---------------------------------------------------------------- outfit building
def _self_fields_for_part(slug, part):
    role = part.get('role')
    f = {
        'ClassName': 'model2',
        'Name': part.get('label') or part['key'],
        'Model': part['url'],
        'ForceObjUrl': True,
        'Material': part.get('material') or DEBUG_WHITE,
        'NoLighting': True,
        'UniqueID': uid(slug, part['key']),
    }
    if role == 'texture':
        f['Color'] = Vec((1, 1, 1))
    else:
        f['Color'] = Vec(tuple(part.get('color') or (1, 1, 1)))
    if role in ('image', 'texture', 'gloss'):
        f['NoCulling'] = True
    if part.get('hidden'):
        f['Hide'] = True
    if part.get('translucent') or role == 'gloss':
        f['Translucent'] = True
        a = part.get('alpha')
        f['Alpha'] = GLOSS_ALPHA if a is None else a
    return f


def _emit_fields(lines, fields, depth):
    pad = '\t' * depth
    for k in sorted(fields):
        lines.append('%s[%s] = %s,' % (pad, lua_q(k), fmt_value(fields[k])))


def _emit_part(lines, fields, children, depth):
    """One `{ ["self"] = {...}, ["children"] = {...}, },` entry at tab depth `depth`."""
    t = '\t'
    lines.append(t * depth + '{')
    lines.append(t * (depth + 1) + '["self"] = {')
    _emit_fields(lines, fields, depth + 2)
    lines.append(t * (depth + 1) + '},')
    lines.append(t * (depth + 1) + '["children"] = {')
    for cf, cc in children:
        _emit_part(lines, cf, cc, depth + 2)
    lines.append(t * (depth + 1) + '},')
    lines.append(t * depth + '},')


def outfit_text(manifest, bone=DEFAULT_BONE, position=DEFAULT_POSITION, angles=DEFAULT_ANGLES):
    slug = manifest['slug']
    parts = manifest['parts']
    bodies = [p for p in parts if p.get('role') == 'body']
    if len(bodies) != 1:
        raise ValueError('manifest needs exactly one part with role "body" (found %d)' % len(bodies))
    body = bodies[0]
    others = [p for p in parts if p is not body]

    body_fields = _self_fields_for_part(slug, body)
    body_fields['Bone'] = bone
    body_fields['Position'] = Vec(tuple(position))
    body_fields['Angles'] = Ang(tuple(angles))
    body_fields['EditorExpand'] = True

    root_fields = {
        'ClassName': 'group',
        'Name': 'pin badge: %s' % manifest.get('name', slug),
        'Notes': WATERMARK,
        'EditorExpand': True,
        'UniqueID': uid(slug, 'root'),
    }
    children = [(_self_fields_for_part(slug, p), []) for p in others]

    lines = [HEADER, '']
    lines.append('["self"] = {')
    _emit_fields(lines, root_fields, 1)
    lines.append('},')
    lines.append('["children"] = {')
    _emit_part(lines, body_fields, children, 1)
    lines.append('},')
    return '\n'.join(lines) + '\n'


def write_outfit(manifest, path, **kw):
    text = outfit_text(manifest, **kw)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(text.encode('utf-8'))
    return path


# ---------------------------------------------------------------- tiny Lua-table parser
class LuaParseError(ValueError):
    pass


_NUM_RE = re.compile(r'-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
_IDENT_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


class _Parser:
    def __init__(self, text):
        self.s = text
        self.i = 0

    def err(self, msg):
        line = self.s.count('\n', 0, self.i) + 1
        raise LuaParseError('%s at line %d (offset %d)' % (msg, line, self.i))

    def ws(self):
        s, n = self.s, len(self.s)
        while self.i < n:
            c = s[self.i]
            if c in ' \t\r\n':
                self.i += 1
            elif s.startswith('--', self.i):
                j = s.find('\n', self.i)
                self.i = n if j < 0 else j + 1
            else:
                break

    def peek(self):
        self.ws()
        return self.s[self.i] if self.i < len(self.s) else ''

    def expect(self, ch):
        if self.peek() != ch:
            self.err('expected %r, got %r' % (ch, self.peek()))
        self.i += 1

    def string(self):
        self.expect('"')
        s, out = self.s, []
        while True:
            if self.i >= len(s):
                self.err('unterminated string')
            c = s[self.i]
            self.i += 1
            if c == '"':
                return ''.join(out)
            if c == '\\':
                if self.i >= len(s):
                    self.err('dangling backslash')
                e = s[self.i]
                self.i += 1
                if e == 'n':
                    out.append('\n')
                elif e == 'r':
                    out.append('\r')
                elif e == 't':
                    out.append('\t')
                elif e == '\n':
                    out.append('\n')          # %q writes a newline as backslash + newline
                elif e in '\\"\'':
                    out.append(e)
                elif e.isdigit():
                    d = e
                    while len(d) < 3 and self.i < len(s) and s[self.i].isdigit():
                        d += s[self.i]
                        self.i += 1
                    out.append(chr(int(d)))
                else:
                    self.err('bad escape \\%s' % e)
            else:
                out.append(c)

    def number(self):
        m = _NUM_RE.match(self.s, self.i)
        if not m:
            self.err('expected number')
        self.i = m.end()
        t = m.group(0)
        return float(t) if any(ch in t for ch in '.eE') else int(t)

    def value(self):
        c = self.peek()
        if c == '"':
            return self.string()
        if c == '{':
            return self.table()
        if c == '-' or c.isdigit() or c == '.':
            return self.number()
        m = _IDENT_RE.match(self.s, self.i)
        if not m:
            self.err('unexpected %r' % c)
        name = m.group(0)
        self.i = m.end()
        if name == 'true':
            return True
        if name == 'false':
            return False
        if name in ('Vector', 'Angle'):
            self.expect('(')
            nums = []
            for k in range(3):
                if k:
                    self.expect(',')
                self.ws()
                nums.append(self.number())
            self.expect(')')
            return (Vec if name == 'Vector' else Ang)(tuple(nums))
        self.err('unsupported token %r' % name)

    def key(self):
        self.expect('[')
        k = self.string()
        self.expect(']')
        return k

    def entries(self, closer):
        """Entries up to `closer` ('}' or '' for EOF). Dict if keyed, list if positional."""
        keyed, positional = {}, []
        while True:
            c = self.peek()
            if c == closer:
                break
            if c == '':
                self.err('unexpected end of input')
            if c == '[':
                k = self.key()
                self.expect('=')
                if k in keyed:
                    self.err('duplicate key %r' % k)
                keyed[k] = self.value()
            else:
                positional.append(self.value())
            c = self.peek()
            if c in (',', ';'):
                self.i += 1
            elif c != closer:
                self.err('expected , or %r, got %r' % (closer or 'EOF', c))
        if keyed and positional:
            self.err('mixed keyed and positional entries')
        return keyed if keyed else positional

    def table(self):
        self.expect('{')
        r = self.entries('}')
        self.expect('}')
        return r


def parse_outfit(text):
    """Parse an outfit file (canonical no-outer-brace form or a braced table) to nested
    dict/list/str/number/bool; Vector/Angle become Vec/Ang tuples. Raises LuaParseError."""
    if text.startswith('\ufeff'):
        text = text[1:]
    p = _Parser(text)
    p.ws()
    if p.peek() == '{':          # tolerate a fully braced outfit
        r = p.table()
        p.ws()
        if p.i != len(p.s):
            p.err('trailing content')
        return r
    r = p.entries('')
    if not isinstance(r, dict):
        p.err('top level is not a keyed table')
    return r


# ---------------------------------------------------------------- verification
_HEX64 = re.compile(r'^[0-9a-f]{64}$')


def _braces_balanced(text):
    """Count { } outside string literals; also reports negative depth."""
    depth, i, n, in_str = 0, 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            if c == '\\':
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0 and not in_str


def url_to_repo_path(url):
    if not url.startswith(RAW_BASE):
        return None
    return os.path.join(REPO, *url[len(RAW_BASE):].split('/'))


def _walk(node, depth, out):
    """Yield (self_dict, depth) for every part."""
    for ch in node.get('children', []) or []:
        s = ch.get('self', {})
        out.append((s, depth))
        _walk(ch, depth + 1, out)


def verify_outfit(path):
    checks, msgs = {}, []

    def chk(name, ok, msg=None):
        checks[name] = bool(ok)
        if not ok:
            msgs.append('%s: %s' % (name, msg or 'failed'))

    with open(path, 'rb') as f:
        raw = f.read()
    chk('no_bom', not raw.startswith(b'\xef\xbb\xbf'), 'file starts with a UTF-8 BOM')
    try:
        text = raw.decode('utf-8')
        chk('utf8', True)
    except UnicodeDecodeError as e:
        chk('utf8', False, str(e))
        text = raw.decode('utf-8', 'replace')
    chk('lf_newlines', b'\r' not in raw, 'CR characters present')
    chk('header', text.startswith(HEADER + '\n\n'), 'line 1 must be %r followed by a blank line' % HEADER)
    chk('trailing_newline', text.endswith('\n') and not text.endswith('\n\n'),
        'file must end with exactly one newline')
    last = text.rstrip('\n').split('\n')[-1].strip() if text.strip() else ''
    chk('no_trailing_comment', not last.startswith('--') and last == '},',
        'last line is %r (expected "},")' % last)
    chk('braces_balanced', _braces_balanced(text), 'unbalanced braces')

    tree = None
    try:
        tree = parse_outfit(text)
        chk('values_ok', True)
    except LuaParseError as e:
        chk('values_ok', False, 'every value must be %q string/number/true/false/Vector(3)/Angle(3)/table: ' + str(e))
    if tree is not None and '\\\n' in text:
        pass  # multi-line %q strings are legal; nothing to flag

    counts = {'bytes': len(raw), 'lines': text.count('\n'), 'parts': 0, 'models': 0,
              'hidden': 0, 'translucent': 0, 'unique_urls': 0, 'missing_files': 0}
    if tree is None:
        return {'ok': False, 'checks': checks, 'messages': msgs, 'counts': counts}

    parts = []
    root = tree.get('self')
    chk('root_present', isinstance(root, dict) and isinstance(tree.get('children'), list),
        'missing top-level self/children')
    root = root if isinstance(root, dict) else {}
    _walk(tree, 0, parts)
    counts['parts'] = len(parts) + 1
    all_selves = [root] + [s for s, _ in parts]

    chk('root_group', root.get('ClassName') == 'group' and str(root.get('Name', '')).startswith('pin badge: '),
        'root must be group named "pin badge: <name>"')
    chk('root_notes_watermark', root.get('Notes') == WATERMARK, 'root Notes must be %r' % WATERMARK)
    chk('root_expand', root.get('EditorExpand') is True, 'root EditorExpand must be true')

    # structure: root -> one body -> the rest
    top = tree.get('children') or []
    body_ok = (len(top) == 1 and isinstance(top[0], dict) and
               top[0].get('self', {}).get('ClassName') == 'model2' and
               'Bone' in top[0].get('self', {}))
    chk('body_single_child_of_root', body_ok, 'root must have exactly one child: the model2 body with Bone')
    if body_ok:
        bs = top[0]['self']
        chk('body_transform', isinstance(bs.get('Position'), Vec) and isinstance(bs.get('Angles'), Ang)
            and bs.get('EditorExpand') is True, 'body needs Position Vector, Angles Angle, EditorExpand true')
        kids = top[0].get('children') or []
        bad = [k['self'].get('Name') for k in kids
               if any(x in k['self'] for x in ('Bone', 'Position', 'Angles'))
               or k['self'].get('ClassName') != 'model2' or k.get('children')]
        chk('children_plain', not bad, 'children must be bare model2 with no Bone/transform: %r' % bad)

    # key order inside every self table (self/children themselves are canonical, not sorted)
    unsorted = [str(sd.get('Name')) for sd in all_selves if list(sd) != sorted(sd)]
    tops = list(tree)
    if tops != ['self', 'children']:
        unsorted.append('top-level order %r' % tops)
    chk('keys_alphabetised', not unsorted, 'keys out of order in %s' % unsorted[:3])

    # unique ids
    ids = [s.get('UniqueID') for s in all_selves]
    badid = [u for u in ids if not (isinstance(u, str) and _HEX64.match(u) and u.endswith('a0c3f'))]
    chk('uniqueid_format', not badid, 'UniqueID must be 64 lowercase hex ending a0c3f: %r' % badid[:2])
    chk('uniqueid_unique', len(set(ids)) == len(ids), 'duplicate UniqueIDs')

    # models
    models = [s for s in all_selves if s.get('ClassName') == 'model2']
    urls = [s.get('Model') for s in models]
    counts['models'] = len(models)
    counts['hidden'] = sum(1 for s in models if s.get('Hide') is True)
    counts['translucent'] = sum(1 for s in models if s.get('Translucent') is True)
    counts['unique_urls'] = len(set(urls))
    bad_https = [u for u in urls if not (isinstance(u, str) and u.startswith('https://'))]
    chk('model_https', not bad_https, 'non-https Model: %r' % bad_https[:2])
    bad_ext = [u for u in urls if not (isinstance(u, str) and u.endswith('.obj')
                                       and '?' not in u and '#' not in u)]
    chk('model_obj_ext', not bad_ext, 'Model must end exactly in .obj, no query: %r' % bad_ext[:2])
    bad_base = [u for u in urls if not (isinstance(u, str) and u.startswith(RAW_BASE))]
    chk('model_raw_base', not bad_base, 'Model must start with RAW_BASE: %r' % bad_base[:2])
    chk('model_urls_unique', len(set(urls)) == len(urls), 'duplicate Model URLs')
    chk('model_flags', all(s.get('ForceObjUrl') is True and s.get('NoLighting') is True
                           and isinstance(s.get('Color'), Vec) and isinstance(s.get('Material'), str)
                           for s in models), 'every model2 needs ForceObjUrl, NoLighting, Color Vector, Material')

    missing = []
    for u in urls:
        p = url_to_repo_path(u) if isinstance(u, str) else None
        if p is None or not os.path.isfile(p):
            missing.append(u)
    counts['missing_files'] = len(missing)
    chk('local_files_exist', not missing, 'no local file in repo for: %s' % ', '.join(map(str, missing[:6])))

    return {'ok': all(checks.values()), 'checks': checks, 'messages': msgs, 'counts': counts}


# ---------------------------------------------------------------- self test
def _selftest():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pin_common import (OUT_DIR, TOOL_DIR, GLOSS_ALPHA as GA, METAL_COLOR, MeshBuilder,
                            obj_filename, obj_url, write_obj)

    smoke_dir = os.path.join(OUT_DIR, 'pac_smoke')
    os.makedirs(smoke_dir, exist_ok=True)
    slug, h = 'smoke_badge', 'a1b2c3'
    img = 'https://files.catbox.moe/abc123.png'

    def make(key, role, label, color, **kw):
        fn = obj_filename(slug, h, key)
        mb = MeshBuilder()
        mb.polygon([(0, 0, 0), (0, 0, 1), (1, 0, 0)])
        info = write_obj(os.path.join(smoke_dir, fn), mb.verts, mb.tris)
        p = {'key': key, 'role': role, 'label': label, 'file': fn,
             'local_path': info['path'], 'url': obj_url(slug, fn), 'color': list(color),
             'alpha': 1.0, 'translucent': False, 'hidden': False, 'material': None,
             'verts': info['verts'], 'tris': info['tris']}
        p.update(kw)
        return p

    manifest = {'name': 'smoke "test"\\badge', 'slug': slug, 'hash': h, 'diameter': 2.25,
                'image_url': img, 'source_image': None, 'res': 64, 'colors': 16,
                'parts': [
                    make('body', 'body', 'pin badge (MOVE ME)', (0.722, 0.73, 0.76)),
                    make('face_uv', 'texture', 'image (paste URL into material)', (1, 1, 1), material=img),
                    make('c01', 'image', 'mosaic #1a2b3c', (0.1, 0.2, 0.3), hidden=True),
                    make('c02', 'image', 'mosaic #4d5e6f', (0.9, 0.85, 0.0), hidden=True),
                    make('gloss', 'gloss', 'gloss', (1, 1, 1), translucent=True, alpha=GA),
                    make('rim', 'rim', 'rim', METAL_COLOR, hidden=True),
                ]}

    out_path = os.path.join(OUT_DIR, 'pac_smoke.txt')
    write_outfit(manifest, out_path)
    with open(out_path, 'rb') as f:
        raw = f.read()
    print('wrote', out_path, len(raw), 'bytes')
    print(raw.decode('utf-8'))

    res = verify_outfit(out_path)
    print('verify (fake manifest, files not pushed to repo, expect only local_files_exist to fail):')
    print(json.dumps(res, indent=2))
    failing = [k for k, v in res['checks'].items() if not v]
    assert failing == ['local_files_exist'], failing

    # parse round trip
    tree = parse_outfit(raw.decode('utf-8'))
    root = tree['self']
    assert root['Name'] == 'pin badge: ' + manifest['name'], root['Name']
    assert root['Notes'] == WATERMARK
    body = tree['children'][0]
    assert body['self']['Bone'] == DEFAULT_BONE
    assert body['self']['Position'] == (6, 9, -3.5) and isinstance(body['self']['Position'], Vec)
    assert body['self']['Angles'] == (0, 0, 0) and isinstance(body['self']['Angles'], Ang)
    kids = body['children']
    assert [k['self']['Name'] for k in kids] == [p['label'] for p in manifest['parts'][1:]]
    for k, p in zip(kids, manifest['parts'][1:]):
        s = k['self']
        assert s['Model'] == p['url'] and s['UniqueID'] == uid(slug, p['key'])
        assert s['Material'] == (p['material'] or DEBUG_WHITE)
        assert s.get('Hide', False) == p['hidden']
        assert k['children'] == []
    assert kids[0]['self']['Color'] == (1, 1, 1)
    assert kids[3]['self']['Alpha'] == GA and kids[3]['self']['Translucent'] is True
    assert kids[3]['self']['NoCulling'] is True and 'NoCulling' not in kids[4]['self']
    assert 'Vector(0.722, 0.73, 0.76)' in raw.decode() and 'Vector(6, 9, -3.5)' in raw.decode()
    # re-serialise equivalence: parse -> every key present once, sorted
    print('parse_outfit round trip OK:', len(kids), 'children under body')

    # existence check against a real repo file (re-use an existing obj to prove the positive path)
    real = os.path.join(REPO, 'obj', 'HELMET.obj')
    if os.path.isfile(real):
        m2 = json.loads(json.dumps(manifest))
        m2['parts'] = m2['parts'][:1]
        m2['parts'][0]['url'] = RAW_BASE + 'obj/HELMET.obj'
        p2 = os.path.join(OUT_DIR, 'pac_smoke_real.txt')
        write_outfit(m2, p2)
        r2 = verify_outfit(p2)
        print('verify with real repo file:', r2['ok'], r2['counts'], r2['messages'])
        assert r2['ok'], r2['messages']

    # negative tests: verify must catch problems rather than crash
    bad = raw.decode('utf-8')
    cases = {
        'bom': b'\xef\xbb\xbf' + raw,
        'http': raw.replace(b'https://github.com', b'http://github.com', 1),
        'query': raw.replace(b'_body.obj"', b'_body.obj?x=1"', 1),
        'trailing_comment': raw + b'-- hi\n',
        'bad_value': raw.replace(b'true,', b'nil,', 1),
        'crlf': raw.replace(b'\n', b'\r\n'),
        'unbalanced': raw[:-4] + b'\n',
    }
    for name, data in cases.items():
        p = os.path.join(OUT_DIR, 'pac_smoke_bad_%s.txt' % name)
        with open(p, 'wb') as f:
            f.write(data)
        r = verify_outfit(p)
        assert not r['ok'], name
        print('negative case %-17s -> caught: %s' % (name, [k for k, v in r['checks'].items() if not v]))
        os.remove(p)
    print('SELFTEST PASSED')


if __name__ == '__main__':
    _selftest()
