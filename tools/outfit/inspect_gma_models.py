"""list the models of a workshop GMA with bones / bodygroups / material slots (reads only the MDL headers; stdlib only, run with python -I)"""
import struct
import sys

NUL = bytes([0])


def cstr(buf, p):
    e = buf.index(NUL, p)
    return buf[p:e].decode('utf-8', 'replace'), e + 1


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


def cs(raw, off):
    return cstr(raw, off)[0]


def info(raw):
    nb, bi = struct.unpack_from('<2i', raw, 156)
    bones = []
    for i in range(nb):
        o = bi + i * 216
        bones.append(cs(raw, o + struct.unpack_from('<i', raw, o)[0]))
    ntex, texidx = struct.unpack_from('<2i', raw, 204)
    texs = [cs(raw, texidx + i * 64 + struct.unpack_from('<i', raw, texidx + i * 64)[0]) for i in range(ntex)]
    nbody, bodyidx = struct.unpack_from('<2i', raw, 232)
    bgs = []
    for i in range(nbody):
        o = bodyidx + i * 16
        ni, nm, base, mi = struct.unpack_from('<4i', raw, o)
        bgs.append((cs(raw, o + ni), nm))
    natt, attidx = struct.unpack_from('<2i', raw, 240)
    atts = [cs(raw, attidx + i * 92 + struct.unpack_from('<i', raw, attidx + i * 92)[0]) for i in range(natt)]
    return bones, texs, bgs, atts


if __name__ == '__main__':
    path = sys.argv[1]
    g = Gma(path)
    names = sorted(g.offs)
    print('files:', len(names))
    mdls = [n for n in names if n.lower().endswith('.mdl')]
    print('models:', len(mdls))
    for n in mdls:
        raw = g.get(n, 4 * 1024 * 1024)
        try:
            bones, texs, bgs, atts = info(raw)
        except Exception as e:
            print(n, 'ERR', e)
            continue
        vb = sum(1 for b in bones if b.startswith('ValveBiped'))
        print('\n%s  size %d  bones %d (ValveBiped %d)  textures %d' % (n, g.offs[n][1], len(bones), vb, len(texs)))
        print('  head-ish bones:', [b for b in bones if 'head' in b.lower() or 'neck' in b.lower()][:8])
        print('  bodygroups:', bgs)
        print('  textures:', texs)
        print('  attachments:', atts[:12])
