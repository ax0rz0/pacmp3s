"""Minimal Source .mdl reader: skeleton (bind + poseToBone) and local-animation frame decode."""
import struct, math
import numpy as np


def cstr(b, off):
    e = b.index(b'\0', off)
    return b[off:e].decode('latin-1'), e + 1


def quat_to_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def euler_to_mat(rx, ry, rz):
    """Source RadianEuler (roll=x, pitch=y, yaw=z) -> Rz(yaw) Ry(pitch) Rx(roll)."""
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def half(h):
    return float(np.frombuffer(struct.pack('<H', h), dtype='<f2')[0])


def unpack_q48(b, o):
    a, bb, c = struct.unpack_from('<HHH', b, o)
    x = (a - 32768) / 32768.0
    y = (bb - 32768) / 32768.0
    z = ((c & 0x7FFF) - 16384) / 16384.0
    w = math.sqrt(max(0.0, 1 - x * x - y * y - z * z))
    return (x, y, z, -w if c & 0x8000 else w)


def unpack_q64(b, o):
    v = struct.unpack_from('<Q', b, o)[0]
    x = ((v & 0x1FFFFF) - 1048576) / 1048576.5
    y = (((v >> 21) & 0x1FFFFF) - 1048576) / 1048576.5
    z = (((v >> 42) & 0x1FFFFF) - 1048576) / 1048576.5
    w = math.sqrt(max(0.0, 1 - x * x - y * y - z * z))
    return (x, y, z, -w if (v >> 63) & 1 else w)


class Mdl:
    def __init__(self, b):
        self.b = b
        i32 = lambda q: struct.unpack_from('<i', b, q)[0]
        self.i32 = i32
        nb, bi = i32(156), i32(160)
        self.names, self.parent = [], []
        self.pos, self.quat, self.rot, self.posscale, self.rotscale = [], [], [], [], []
        self.bindR, self.bindP = [], []
        for i in range(nb):
            o = bi + i * 216
            self.names.append(cstr(b, o + i32(o))[0])
            self.parent.append(i32(o + 4))
            self.pos.append(np.array(struct.unpack_from('<3f', b, o + 32)))
            self.quat.append(struct.unpack_from('<4f', b, o + 44))
            self.rot.append(struct.unpack_from('<3f', b, o + 60))
            self.posscale.append(np.array(struct.unpack_from('<3f', b, o + 72)))
            self.rotscale.append(np.array(struct.unpack_from('<3f', b, o + 84)))
            m = struct.unpack_from('<12f', b, o + 96)
            R = np.array([[m[0], m[1], m[2]], [m[4], m[5], m[6]], [m[8], m[9], m[10]]])
            t = np.array([m[3], m[7], m[11]])
            self.bindR.append(R.T)              # columns = bone axes in model space
            self.bindP.append(-R.T @ t)         # bone origin in model space
        self.n = nb
        self.index = {n: i for i, n in enumerate(self.names)}

    def local_bind(self):
        out = []
        for i in range(self.n):
            p = self.parent[i]
            if p < 0:
                out.append((self.bindR[i].copy(), self.bindP[i].copy()))
            else:
                out.append((self.bindR[p].T @ self.bindR[i], self.bindR[p].T @ (self.bindP[i] - self.bindP[p])))
        return out

    def seq_info(self, s):
        b, i32 = self.b, self.i32
        q = i32(192) + s * 212
        label = cstr(b, q + i32(q + 4))[0]
        a0 = struct.unpack_from('<h', b, q + i32(q + 60))[0]
        return label, a0

    def anim_frame(self, anim, frame=0):
        """Local (rot 3x3, pos) per bone for one frame of local anim; bones without data keep their default local transform."""
        b, i32 = self.b, self.i32
        ad = i32(184) + anim * 100
        nframes, aflags, animindex = i32(ad + 16), i32(ad + 12), i32(ad + 56)
        assert i32(ad + 52) == 0, 'anim stored in block file (.ani): not supported'
        res = [(quat_to_mat(self.quat[i]), self.pos[i].copy()) for i in range(self.n)]
        touched = set()

        def rle(off):
            f = frame
            while True:
                valid, total = b[off], b[off + 1]
                if f < total:
                    k = min(f, valid - 1)
                    return struct.unpack_from('<h', b, off + 2 + 2 * k)[0]
                f -= total
                off += 2 + 2 * valid

        o = ad + animindex
        while True:
            bone, flags, nxt = b[o], b[o + 1], struct.unpack_from('<h', b, o + 2)[0]
            p = o + 4
            rotm = None
            posv = None
            if flags & 0x20:
                rotm = quat_to_mat(unpack_q64(b, p)); p += 8
            elif flags & 0x02:
                rotm = quat_to_mat(unpack_q48(b, p)); p += 6
            elif flags & 0x08:
                offs = struct.unpack_from('<3h', b, p)
                e = [self.rot[bone][k] + (rle(p + offs[k]) * self.rotscale[bone][k] if offs[k] else 0) for k in range(3)]
                rotm = euler_to_mat(*e); p += 6
            if flags & 0x01:
                posv = np.array([half(h) for h in struct.unpack_from('<3H', b, p)]); p += 6
            elif flags & 0x04:
                offs = struct.unpack_from('<3h', b, p)
                posv = np.array([self.pos[bone][k] + (rle(p + offs[k]) * self.posscale[bone][k] if offs[k] else 0) for k in range(3)]); p += 6
            R0, P0 = res[bone]
            res[bone] = (rotm if rotm is not None else R0, posv if posv is not None else P0)
            touched.add(bone)
            if nxt == 0:
                break
            o += nxt
        return res, nframes, aflags, touched

    def fk(self, local):
        W = []
        for i in range(self.n):
            R, P = local[i]
            p = self.parent[i]
            if p < 0:
                W.append((R, P))
            else:
                W.append((W[p][0] @ R, W[p][1] + W[p][0] @ P))
        return W


def angle_between(R1, R2):
    c = (np.trace(R1.T @ R2) - 1) / 2
    return math.degrees(math.acos(max(-1, min(1, c))))


# ---------------------------------------------------------------- content readers
def _vpk_get(dirvpk, wantpath):
    vb = open(dirvpk, 'rb').read()
    sig, ver, tree_size = struct.unpack_from('<III', vb, 0)
    hdr = 28
    p = hdr
    while True:
        ext, p = cstr(vb, p)
        if ext == '':
            break
        while True:
            path, p = cstr(vb, p)
            if path == '':
                break
            while True:
                fn, p = cstr(vb, p)
                if fn == '':
                    break
                crc, preload, arch, off, ln = struct.unpack_from('<IHHII', vb, p)
                p += 18
                pre = vb[p:p + preload]
                p += preload
                if ('%s/%s.%s' % (path, fn, ext)).lower() == wantpath:
                    if arch == 0x7fff:
                        return pre + vb[hdr + tree_size + off: hdr + tree_size + off + ln]
                    with open(dirvpk[:-8] + '_%03d.vpk' % arch, 'rb') as f:
                        f.seek(off)
                        return pre + f.read(ln)


class Gma:
    def __init__(self, path):
        self.f = open(path, 'rb')
        head = self.f.read(8 * 1024 * 1024)
        p = 21
        while True:
            s, p = cstr(head, p)
            if s == '':
                break
        for _ in range(3):
            _, p = cstr(head, p)
        p += 4
        entries = []
        while True:
            num = struct.unpack_from('<I', head, p)[0]
            p += 4
            if num == 0:
                break
            name, p = cstr(head, p)
            size, crc = struct.unpack_from('<qI', head, p)
            p += 12
            entries.append((name, size))
        o = p
        self.offs = {}
        for name, size in entries:
            self.offs[name] = (o, size)
            o += size

    def get(self, name, limit=16 * 1024 * 1024):
        o, sz = self.offs[name]
        self.f.seek(o)
        return self.f.read(min(sz, limit))


SCP_GMA = r'C:\Program Files (x86)\Steam\steamapps\workshop\content\4000\2830971578\gmpublisher.gma'
HL2_VPK = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\sourceengine\hl2_misc_dir.vpk'


def load_model(path):
    if path.lower().startswith('models/humans/'):
        return Mdl(_vpk_get(HL2_VPK, path.lower()))
    return Mdl(Gma(SCP_GMA).get(path))
