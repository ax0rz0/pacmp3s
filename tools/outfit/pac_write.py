"""Write pac3 outfit files in the exact format of the pac editor's saves (tab indented, `[n] = {` entries, children before self).

    parts = pac_parse.load(path)            # {1: {'children': {...}, 'self': {...}}, 2: ...}  (Vector/Angle/Color arrive as ('Vector', (x, y, z)) tuples)
    text = pac_write.dump(parts, watermark='claude skill made by ax0rz0')
    pac_write.remap_uids(parts, slug)        # new deterministic 64-hex UniqueIDs ending a0c3f (also fixes *UID references)
"""
import hashlib

BS = chr(92)       # backslash
DQ = chr(34)       # double quote


def fmt_num(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if float(v) == int(v) and abs(v) < 1e15:
        return str(int(v))
    return '%.14g' % v


def fmt_str(s):
    s = s.replace(BS, BS + BS).replace(DQ, BS + DQ)
    s = s.replace(chr(10), BS + 'n').replace(chr(13), BS + 'r').replace(chr(9), BS + 't')
    return DQ + s + DQ


def fmt_val(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return fmt_str(v)
    if isinstance(v, (int, float)):
        return fmt_num(v)
    if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str):
        return '%s(%s)' % (v[0], ', '.join(fmt_num(x) for x in v[1]))
    raise TypeError('cannot serialise %r' % (v,))


def dump_part(part, indent):
    t = chr(9) * indent
    out = [t + '{' + chr(10)]
    out.append(t + chr(9) + '["children"] = {' + chr(10))
    kids = part.get('children', {}) or {}
    for i, k in enumerate(sorted(k for k in kids if isinstance(k, int)), 1):
        out.append(t + chr(9) * 2 + '[%d] = ' % i + dump_part(kids[k], indent + 2).lstrip(chr(9)))
    out.append(t + chr(9) + '},' + chr(10))
    out.append(t + chr(9) + '["self"] = {' + chr(10))
    for k in sorted(part['self']):
        out.append(t + chr(9) * 2 + '["%s"] = %s,' % (k, fmt_val(part['self'][k])) + chr(10))
    out.append(t + chr(9) + '},' + chr(10))
    out.append(t + '},' + chr(10))
    return ''.join(out)


def dump(parts, watermark=None):
    """parts: dict {1: part, 2: part, ...} or a list of parts"""
    if isinstance(parts, dict):
        parts = [parts[k] for k in sorted(k for k in parts if isinstance(k, int))]
    out = []
    if watermark:
        out.append('-- %s' % watermark + chr(10) + chr(10))
    for i, p in enumerate(parts, 1):
        out.append('[%d] = ' % i + dump_part(p, 0))
    return ''.join(out)


def walk(parts):
    items = list(parts.values()) if isinstance(parts, dict) else list(parts)
    for p in items:
        if not isinstance(p, dict) or 'self' not in p:
            continue
        yield p
        kids = p.get('children', {}) or {}
        yield from walk([kids[k] for k in sorted(k for k in kids if isinstance(k, int))])


def new_uid(slug, old):
    return hashlib.sha256((slug + ':' + old).encode()).hexdigest()[:59] + 'a0c3f'


def remap_uids(parts, slug):
    """give every part a deterministic new UniqueID (64 hex, ending a0c3f) and rewrite references (AimPartUID, EyeTargetUID, TargetEntityUID, ...) that point at a remapped id"""
    olds = {p['self'].get('UniqueID') for p in walk(parts) if p['self'].get('UniqueID')}
    m = {o: new_uid(slug, o) for o in olds}
    for p in walk(parts):
        s = p['self']
        for k, v in list(s.items()):
            if isinstance(v, str) and (k == 'UniqueID' or k.endswith('UID')) and v in m:
                s[k] = m[v]
    return m
