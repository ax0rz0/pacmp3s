"""Binary FBX reader + skeletal animation evaluator (stdlib + numpy). Built for Mixamo exports."""
import struct, zlib, math
import numpy as np

KTIME = 46186158000.0  # FBX ticks per second


# ------------------------------------------------------------------ binary container
class Node:
    __slots__ = ('name', 'props', 'children')

    def __init__(self, name):
        self.name, self.props, self.children = name, [], []

    def find(self, name):
        return [c for c in self.children if c.name == name]

    def first(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None


def read_fbx(path):
    b = open(path, 'rb').read()
    assert b[:20] == b'Kaydara FBX Binary  ', 'not a binary FBX'
    ver = struct.unpack_from('<I', b, 23)[0]
    wide = ver >= 7500
    hdr = 24 if wide else 12
    pos = 27

    def read_prop(p):
        t = chr(b[p]); p += 1
        if t == 'Y': return struct.unpack_from('<h', b, p)[0], p + 2
        if t == 'C': return bool(b[p]), p + 1
        if t == 'I': return struct.unpack_from('<i', b, p)[0], p + 4
        if t == 'F': return struct.unpack_from('<f', b, p)[0], p + 4
        if t == 'D': return struct.unpack_from('<d', b, p)[0], p + 8
        if t == 'L': return struct.unpack_from('<q', b, p)[0], p + 8
        if t in 'fdlib':
            n, enc, clen = struct.unpack_from('<III', b, p); p += 12
            raw = b[p:p + clen]; p += clen
            if enc == 1: raw = zlib.decompress(raw)
            dt = {'f': '<f4', 'd': '<f8', 'l': '<i8', 'i': '<i4', 'b': 'u1'}[t]
            return np.frombuffer(raw, dtype=dt, count=n), p
        if t in 'SR':
            n = struct.unpack_from('<I', b, p)[0]; p += 4
            raw = b[p:p + n]; p += n
            return (raw.decode('latin-1') if t == 'S' else raw), p
        raise ValueError('bad property type %r' % t)

    def read_node(p):
        if wide:
            end, nprops, plen, nlen = struct.unpack_from('<QQQB', b, p); p += 25
        else:
            end, nprops, plen, nlen = struct.unpack_from('<IIIB', b, p); p += 13
        if end == 0:
            return None, p
        node = Node(b[p:p + nlen].decode('latin-1')); p += nlen
        for _ in range(nprops):
            v, p = read_prop(p)
            node.props.append(v)
        while p < end:
            c, p = read_node(p)
            if c is None:
                break
            node.children.append(c)
        return node, end

    root = Node('')
    while pos < len(b) - 32:
        n, pos = read_node(pos)
        if n is None:
            break
        root.children.append(n)
    return root


# ------------------------------------------------------------------ scene model
ROT_ORDERS = {0: 'XYZ', 1: 'XZY', 2: 'YZX', 3: 'YXZ', 4: 'ZXY', 5: 'ZYX'}


def rot_axis(axis, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    if axis == 'X': return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == 'Y': return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler_matrix(xyz_deg, order='XYZ'):
    """FBX Euler: rotations applied in `order` (first letter first) -> M = R_last @ R_mid @ R_first."""
    ang = {'X': xyz_deg[0], 'Y': xyz_deg[1], 'Z': xyz_deg[2]}
    M = np.eye(3)
    for ax in order:
        M = rot_axis(ax, ang[ax]) @ M
    return M


class Scene:
    def __init__(self, path):
        root = read_fbx(path)
        objs = root.first('Objects')
        conns = root.first('Connections')
        self.models = {}          # id -> dict
        self.curvenodes = {}      # id -> dict(name, defaults)
        self.curves = {}          # id -> (times_ticks, values)
        for n in objs.children:
            if n.name == 'Model':
                d = dict(id=n.props[0], name=n.props[1].split('\x00')[0], kind=n.props[2], props={}, parent=None)
                p70 = n.first('Properties70')
                if p70:
                    for p in p70.children:
                        if p.name == 'P' and len(p.props) >= 5:
                            d['props'][p.props[0]] = p.props[4:] if len(p.props) > 5 else p.props[4]
                self.models[d['id']] = d
            elif n.name == 'AnimationCurveNode':
                d = dict(id=n.props[0], name=n.props[1].split('\x00')[0], defaults={})
                p70 = n.first('Properties70')
                if p70:
                    for p in p70.children:
                        if p.name == 'P' and len(p.props) >= 5:
                            d['defaults'][p.props[0]] = p.props[4]
                self.curvenodes[d['id']] = d
            elif n.name == 'AnimationCurve':
                kt = n.first('KeyTime'); kv = n.first('KeyValueFloat')
                self.curves[n.props[0]] = (np.asarray(kt.props[0], dtype=np.int64), np.asarray(kv.props[0], dtype=np.float64))
        self.node_curves = {}     # (model_id, prop) -> {'X': curveid, ...} via curvenode
        cn_target = {}            # curvenode id -> (model id, prop)
        cn_curves = {}            # curvenode id -> {axis: curve id}
        for c in conns.children:
            if c.name != 'C':
                continue
            kind, src, dst = c.props[0], c.props[1], c.props[2]
            if kind == 'OO':
                if src in self.models and dst in self.models:
                    self.models[src]['parent'] = dst
            elif kind == 'OP':
                prop = c.props[3] if len(c.props) > 3 else ''
                if src in self.curvenodes and dst in self.models:
                    cn_target[src] = (dst, prop)
                elif src in self.curves and dst in self.curvenodes:
                    cn_curves.setdefault(dst, {})[prop.split('|')[-1]] = src
        self.channels = {}        # (model_id, 'Lcl Rotation') -> {'X': (times, vals), ...}
        for cn, (mid, prop) in cn_target.items():
            ch = {}
            for axis, cid in cn_curves.get(cn, {}).items():
                ch[axis] = self.curves[cid]
            self.channels[(mid, prop)] = ch
            self.channels[(mid, prop, 'defaults')] = self.curvenodes[cn]['defaults']
        self.by_name = {m['name']: m for m in self.models.values()}
        # ordered model list parents-first
        self.order = []
        seen = set()

        def visit(mid):
            if mid in seen:
                return
            p = self.models[mid]['parent']
            if p in self.models:
                visit(p)
            seen.add(mid); self.order.append(mid)
        for mid in self.models:
            visit(mid)

    # ---- evaluation
    def _static(self, m, prop, default):
        v = m['props'].get(prop)
        if v is None:
            return list(default)
        return [float(x) for x in v] if isinstance(v, (list, tuple)) else list(default)

    def _sample(self, mid, prop, t_ticks, static):
        ch = self.channels.get((mid, prop))
        out = list(static)
        if not ch:
            return out
        defaults = self.channels.get((mid, prop, 'defaults'), {})
        for k, axis in enumerate('XYZ'):
            cv = ch.get(axis)
            if cv is not None:
                times, vals = cv
                out[k] = float(np.interp(t_ticks, times, vals))
            elif ('d|' + axis) in defaults:
                out[k] = float(defaults['d|' + axis])
        return out

    def duration(self):
        mx = 0
        for key, ch in self.channels.items():
            if len(key) == 2:
                for axis, (times, vals) in ch.items():
                    mx = max(mx, int(times.max()))
        return mx / KTIME

    def local_matrix(self, mid, t_ticks=None):
        m = self.models[mid]
        T = self._static(m, 'Lcl Translation', (0, 0, 0)); R = self._static(m, 'Lcl Rotation', (0, 0, 0)); S = self._static(m, 'Lcl Scaling', (1, 1, 1))
        if t_ticks is not None:
            T = self._sample(mid, 'Lcl Translation', t_ticks, T); R = self._sample(mid, 'Lcl Rotation', t_ticks, R); S = self._sample(mid, 'Lcl Scaling', t_ticks, S)
        order = ROT_ORDERS.get(int(m['props'].get('RotationOrder', 0) or 0), 'XYZ')
        pre = self._static(m, 'PreRotation', (0, 0, 0)); post = self._static(m, 'PostRotation', (0, 0, 0))
        Rm = euler_matrix(pre, 'XYZ') @ euler_matrix(R, order) @ np.linalg.inv(euler_matrix(post, 'XYZ'))
        M = np.eye(4)
        M[:3, :3] = Rm @ np.diag(S)
        M[:3, 3] = T
        return M

    def world_matrices(self, t_ticks=None):
        W = {}
        for mid in self.order:
            L = self.local_matrix(mid, t_ticks)
            p = self.models[mid]['parent']
            W[mid] = (W[p] @ L) if p in W else L
        return W


def rot_of(M):
    """Orthonormal rotation part of a 4x4 (removes scale)."""
    R = M[:3, :3].copy()
    for k in range(3):
        n = np.linalg.norm(R[:, k])
        if n > 1e-12:
            R[:, k] /= n
    return R
