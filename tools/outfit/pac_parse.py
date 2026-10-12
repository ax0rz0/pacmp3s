"""Tiny parser for pac3 outfit files (Lua table literals as written by pac's luadata).
Returns nested dicts (array entries use int keys); Vector/Angle/Color calls become (name, (args...)) tuples."""
import re

TOK = re.compile(r'''\s*(?:(--[^\n]*)|("(?:[^"\\]|\\.)*")|(-?\d+\.?\d*(?:[eE][+-]?\d+)?|-?inf|nan)|([A-Za-z_][A-Za-z_0-9]*)|([\[\]{}(),=]))''', re.S)
ESC = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\', "'": "'"}


def unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            n = s[i + 1]
            if n.isdigit():
                j = i + 1
                while j < len(s) and j < i + 4 and s[j].isdigit():
                    j += 1
                out.append(chr(int(s[i + 1:j])))
                i = j
                continue
            out.append(ESC.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def tokens(text):
    pos, out = 0, []
    while pos < len(text):
        m = TOK.match(text, pos)
        if not m:
            if text[pos:].strip() == '':
                break
            raise ValueError('parse error at %d: %r' % (pos, text[pos:pos + 40]))
        pos = m.end()
        if m.group(1):
            continue
        if m.group(2) is not None:
            out.append(('str', unescape(m.group(2)[1:-1])))
        elif m.group(3) is not None:
            s = m.group(3)
            out.append(('num', float(s) if re.search(r'[.eE]|inf|nan', s) else int(s)))
        elif m.group(4) is not None:
            out.append(('name', m.group(4)))
        else:
            out.append(('p', m.group(5)))
    return out


class P:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, kind=None, val=None):
        tk = self.t[self.i]
        if (kind and tk[0] != kind) or (val is not None and tk[1] != val):
            raise ValueError('expected %s %s got %s at token %d' % (kind, val, tk, self.i))
        self.i += 1
        return tk

    def value(self):
        k, v = self.peek()
        if k == 'str' or k == 'num':
            self.i += 1
            return v
        if k == 'name':
            self.i += 1
            if v in ('true', 'false'):
                return v == 'true'
            if v == 'nil':
                return None
            self.eat('p', '(')
            args = []
            while self.peek() != ('p', ')'):
                args.append(self.value())
                if self.peek() == ('p', ','):
                    self.i += 1
            self.eat('p', ')')
            return (v, tuple(args))
        if (k, v) == ('p', '{'):
            return self.table()
        raise ValueError('bad value %s at %d' % ((k, v), self.i))

    def table(self):
        self.eat('p', '{')
        d, n = {}, 1
        while self.peek() != ('p', '}'):
            if self.peek() == ('p', '['):
                self.i += 1
                key = self.value()
                self.eat('p', ']')
                self.eat('p', '=')
                d[key] = self.value()
            else:
                d[n] = self.value()
                n += 1
            if self.peek() == ('p', ','):
                self.i += 1
        self.eat('p', '}')
        return d


def parse(text):
    return P(tokens('{' + text + '}')).table()


def load(path):
    return parse(open(path, encoding='utf-8', errors='replace').read())


def walk(node, depth=0):
    """yield (depth, self-dict, node) for every part (handles [1]={children,self} lists and a bare {self,children})."""
    if isinstance(node, dict) and 'self' in node:
        yield depth, node['self'], node
        kids = node.get('children', {})
        for k in sorted(k for k in kids if isinstance(k, int)):
            yield from walk(kids[k], depth + 1)
    elif isinstance(node, dict):
        for k in sorted(k for k in node if isinstance(k, int)):
            yield from walk(node[k], depth)
