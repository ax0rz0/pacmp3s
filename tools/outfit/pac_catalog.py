"""Extract the storable property catalog of every PAC3 part class from a pac3 source tree (lua/pac3/core/client).
    python pac_catalog.py TREE_ROOT_OF_lua_pac3 [out.json]
Handles the builder style (BUILDER:GetSet("Name", default, {...}), GetSetPart) of the newer builds; material_* classes come from libraries/shader_params.lua.
Result: {ClassName: {"base": base class or None, "props": {name: default (python value or {'raw': text})}, "removed": [names]}} with inheritance resolved by `resolve()`."""
import json
import os
import re
import sys


def read(path):
    return open(path, encoding='utf-8', errors='replace').read()


def split_args(s):
    """split a Lua argument list at top-level commas"""
    out, depth, cur, q = [], 0, '', None
    i = 0
    while i < len(s):
        c = s[i]
        if q:
            cur += c
            if c == '\\':
                cur += s[i + 1]
                i += 1
            elif c == q:
                q = None
        elif c in '"\'':
            q = c
            cur += c
        elif c in '({[':
            depth += 1
            cur += c
        elif c in ')}]':
            depth -= 1
            cur += c
        elif c == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += c
        i += 1
    if cur.strip():
        out.append(cur.strip())
    return out


def lua_value(txt):
    t = txt.strip()
    if t in ('true', 'false'):
        return t == 'true'
    if t == 'nil':
        return None
    if re.fullmatch(r'-?\d+(\.\d+)?', t):
        return float(t) if '.' in t else int(t)
    m = re.fullmatch(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', t)
    if m:
        return m.group(1) if m.group(1) is not None else m.group(2)
    m = re.fullmatch(r'(Vector|Angle|Color)\((.*)\)', t)
    if m:
        vals = [lua_value(a) for a in split_args(m.group(2))]
        if all(isinstance(v, (int, float)) for v in vals):
            return {m.group(1): vals}
    if t == '{}':
        return {}
    return {'raw': t}


def call_args(text, start):
    """text[start] is just after an opening '(': return the argument string up to the matching ')'"""
    depth, i, q = 1, start, None
    while i < len(text):
        c = text[i]
        if q:
            if c == '\\':
                i += 1
            elif c == q:
                q = None
        elif c in '"\'':
            q = c
        elif c in '({[':
            depth += 1
        elif c in ')}]':
            depth -= 1
            if depth == 0:
                return text[start:i], i
        i += 1
    return text[start:], len(text)


def parse_part_file(path):
    t = read(path)
    t = re.sub(r'--\[\[.*?\]\]', '', t, flags=re.S)
    t = re.sub(r'(?m)--[^\n]*$', '', t)
    out = []
    # a file may register several classes: split on PartTemplate / PART = {} starts
    starts = [m.start() for m in re.finditer(r'(?:local\s+BUILDER\s*,\s*PART\s*=\s*pac\.PartTemplate\(|local\s+PART\s*=\s*\{\s*\}|BUILDER\s*,\s*PART\s*=\s*pac\.PartTemplate\()', t)]
    if not starts:
        return out
    starts.append(len(t))
    for a, b in zip(starts, starts[1:]):
        seg = t[a:b]
        base = None
        m = re.search(r'PartTemplate\(\s*"([^"]+)"', seg)
        if m:
            base = m.group(1)
        m = re.search(r'PART\.Base\s*=\s*"([^"]+)"', seg)
        if m:
            base = m.group(1)
        m = re.search(r'PART\.ClassName\s*=\s*"([^"]+)"', seg)
        cname = m.group(1) if m else None
        if not cname:
            continue
        props, removed = {}, []
        for m in re.finditer(r'(?:BUILDER)?\s*:\s*GetSet\(', seg):
            args, _ = call_args(seg, m.end())
            parts = split_args(args)
            if len(parts) >= 2 and parts[0][0] in '"\'':
                props[lua_value(parts[0])] = lua_value(parts[1])
            elif len(parts) == 1 and parts[0][0] in '"\'':
                props[lua_value(parts[0])] = None
        for m in re.finditer(r'pac\.GetSet\(\s*PART\s*,', seg):
            args, _ = call_args(seg, m.end())
            parts = split_args(args)
            if len(parts) >= 2 and parts[0][0] in '"\'':
                props[lua_value(parts[0])] = lua_value(parts[1])
        for m in re.finditer(r'GetSetPart\(', seg):
            args, _ = call_args(seg, m.end())
            parts = split_args(args)
            if parts and parts[0][0] in '"\'':
                props[lua_value(parts[0]) + 'UID'] = ''
        for m in re.finditer(r'(?:BUILDER\s*:\s*RemoveProperty|pac\.RemoveProperty)\(\s*(?:PART\s*,\s*)?"([^"]+)"', seg):
            removed.append(m.group(1))
        out.append((cname, base, props, removed))
    return out


def parse_shader_params(path):
    t = read(path)
    res = {}
    # property name = lowercase key (as the saved parts show); matrix params add Position/Scale/Angle/AngleCenter
    shaders = {}
    m = re.search(r'shaders\s*=\s*\{', t)
    body = t[m.end():]
    # crude: find shader blocks "\t\tname = {" at depth 2
    for sm in re.finditer(r'\n\t\t([a-z0-9_]+)\s*=\s*\{', body):
        shaders[sm.group(1)] = sm.end()
    return shaders


def build(root):
    parts_dir = os.path.join(root, 'core', 'client', 'parts')
    classes = {}
    for fn in ['base_part.lua', 'base_movable.lua', 'base_drawable.lua']:
        p = os.path.join(root, 'core', 'client', fn)
        if os.path.exists(p):
            for cname, base, props, removed in parse_part_file(p):
                classes[cname] = {'base': base, 'props': props, 'removed': removed}
    for dirpath, _, files in os.walk(parts_dir):
        if os.path.basename(dirpath) == 'legacy':
            continue
        for fn in sorted(files):
            if fn.endswith('.lua'):
                for cname, base, props, removed in parse_part_file(os.path.join(dirpath, fn)):
                    classes[cname] = {'base': base, 'props': props, 'removed': removed}
    return classes


def resolve(classes, name, _seen=None):
    c = classes[name]
    props = {}
    if c['base'] and c['base'] in classes and c['base'] != name:
        props.update(resolve(classes, c['base']))
    props.update(c['props'])
    for r in c['removed']:
        props.pop(r, None)
    return props


if __name__ == '__main__':
    root = sys.argv[1]
    classes = build(root)
    if len(sys.argv) > 2:
        json.dump(classes, open(sys.argv[2], 'w'), indent=1)
    print(len(classes), 'classes:', sorted(classes))


# ---------------------------------------------------------------------------------------------------------------------------------------------- shader parameters (material_3d / material_2d / material_refract ...)
def _tokenize(t):
    t = re.sub(r'--\[\[.*?\]\]', '', t, flags=re.S)
    t = re.sub(r'(?m)--[^\n]*$', '', t)
    return re.findall(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|-?\d+\.?\d*(?:e-?\d+)?|[A-Za-z_][A-Za-z_0-9\.]*|[{}()=,\[\]]', t)


def parse_lua_table(text):
    """parse a Lua file of the form `return { ... }` made of tables, strings, numbers, booleans and Vector()/Angle()/Color() calls"""
    toks = _tokenize(text)
    pos = [toks.index('return') + 1]

    def value():
        t = toks[pos[0]]
        if t == '{':
            return table()
        pos[0] += 1
        if t in ('true', 'false'):
            return t == 'true'
        if t == 'nil':
            return None
        if t[0] in '"\'':
            return t[1:-1]
        if re.fullmatch(r'-?\d+\.?\d*(?:e-?\d+)?', t):
            return float(t) if ('.' in t or 'e' in t) else int(t)
        if toks[pos[0]] == '(':
            pos[0] += 1
            args = []
            while toks[pos[0]] != ')':
                if toks[pos[0]] == ',':
                    pos[0] += 1
                    continue
                args.append(value())
            pos[0] += 1
            return {t: args}
        return {'raw': t}

    def table():
        pos[0] += 1                      # {
        out = {}
        idx = 1
        while toks[pos[0]] != '}':
            t = toks[pos[0]]
            if t == ',':
                pos[0] += 1
                continue
            if t == '[':
                pos[0] += 1
                k = value()
                if isinstance(k, (dict, list)):
                    k = repr(k)
                pos[0] += 1              # ]
                pos[0] += 1              # =
                out[k] = value()
            elif pos[0] + 1 < len(toks) and toks[pos[0] + 1] == '=':
                pos[0] += 2
                out[t] = value()
            else:
                out[idx] = value()
                idx += 1
        pos[0] += 1
        return out

    return value()


def shader_classes(tree_root):
    """{ClassName: {param property name: {'type': ..., 'default': ...}}} for the material_* classes"""
    sp = parse_lua_table(read(os.path.join(tree_root, 'libraries', 'shader_params.lua')))
    translate = {'vertexlitgeneric': '3d', 'unlitgeneric': '2d', 'eyerefract': 'eye refract'}
    base = sp.get('base', {})
    out = {}
    for shader, groups in sp['shaders'].items():
        merged = {}
        for gname in set(groups) | set(base):
            g = dict(groups.get(gname, {}))
            g.update(base.get(gname, {}))
            for key, info in g.items():
                if isinstance(info, dict) and 'type' in info:
                    merged[key] = info
        props = {}
        for key, info in merged.items():
            typ = info['type']
            if typ == 'matrix':
                props[key + 'Position'] = {'Vector': [0, 0, 0]}          # the shader key already ends in 'transform' (basetexturetransform -> basetexturetransformPosition)
                props[key + 'Scale'] = {'Vector': [1, 1, 1]}
                props[key + 'Angle'] = 0
                props[key + 'AngleCenter'] = {'Vector': [0.5, 0.5, 0]}
                continue
            props[key] = info.get('default', '' if typ == 'texture' else None)
            if info.get('partial_hdr'):
                props[key + 'NoHDR'] = False
        props['MaterialOverride'] = 'all'
        props['LoadVmt'] = ''
        out['material_' + translate.get(shader, shader)] = props
    return out
