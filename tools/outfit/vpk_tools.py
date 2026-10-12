"""List / read entries of a Source VPK (v1/v2 _dir.vpk + numbered archives) without loading the archives into memory."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdl_anim import cstr


def entries(dirvpk):
    vb = open(dirvpk, 'rb').read()
    sig, ver, tree_size = struct.unpack_from('<III', vb, 0)
    hdr = 28 if ver == 2 else 12
    p = hdr
    out = {}
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
                out[('%s/%s.%s' % (path, fn, ext)).lower()] = (arch, off, ln, pre)
    return out, hdr + tree_size


def read(dirvpk, table, base, name):
    arch, off, ln, pre = table[name.lower()]
    if arch == 0x7fff:
        with open(dirvpk, 'rb') as f:
            f.seek(base + off)
            return pre + f.read(ln)
    with open(dirvpk[:-8] + '_%03d.vpk' % arch, 'rb') as f:
        f.seek(off)
        return pre + f.read(ln)


if __name__ == '__main__':
    d = sys.argv[1]
    t, base = entries(d)
    print(len(t), 'entries')
    for k in sorted(t):
        if all(s in k for s in sys.argv[2:]):
            print(k, t[k][2])
