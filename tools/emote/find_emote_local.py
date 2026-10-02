import struct, glob, os, lzma, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdl_anim import cstr
PAT = re.compile(sys.argv[1], re.I)

def parse_index(head):
    if head[:4] != b'GMAD':
        return None
    p = 21
    while True:
        s, p = cstr(head, p)
        if s == '':
            break
    title, p = cstr(head, p)
    for _ in range(2):
        _, p = cstr(head, p)
    p += 4
    out = []
    while True:
        num = struct.unpack_from('<I', head, p)[0]; p += 4
        if num == 0:
            break
        name, p = cstr(head, p)
        size, crc = struct.unpack_from('<qI', head, p); p += 12
        out.append((name, size))
    o = p
    res = []
    for n, s in out:
        res.append((n, o, s)); o += s
    return title, res

def seqnames(b):
    try:
        if b[:4] != b'IDST':
            return []
        i32 = lambda q: struct.unpack_from('<i', b, q)[0]
        ns, si = i32(188), i32(192)
        if not (0 < ns < 5000) or si + ns * 212 > len(b):
            return []
        return [cstr(b, si + k * 212 + i32(si + k * 212 + 4))[0] for k in range(ns)]
    except Exception:
        return []

base = r'C:\Program Files (x86)\Steam\steamapps'
hits = []
nmdl = 0
t0 = time.time()
# 1) plain GMA (workshop + cache)
for g in glob.glob(base + r'\workshop\content\4000\*\*.gma') + glob.glob(base + r'\common\GarrysMod\garrysmod\cache\workshop\*.gma'):
    try:
        f = open(g, 'rb'); r = parse_index(f.read(8 * 1024 * 1024))
    except Exception:
        continue
    if not r:
        continue
    title, ents = r
    for n, o, s in ents:
        if PAT.search(n):
            hits.append(('FILE', os.path.basename(os.path.dirname(g)), title, n, ''))
        if n.lower().endswith('.mdl') and s < 40 * 1024 * 1024:
            f.seek(o); b = f.read(min(s, 6 * 1024 * 1024)); nmdl += 1
            m = [x for x in seqnames(b) if PAT.search(x)]
            if m:
                hits.append(('SEQ', os.path.basename(os.path.dirname(g)), title, n, ','.join(m[:6])))
    f.close()
print('gma/cache done: %d mdl, %.0fs' % (nmdl, time.time() - t0)); sys.stdout.flush()
# 2) compressed legacy .bin workshop addons (LZMA alone): stream-decompress
for bpath in glob.glob(base + r'\workshop\content\4000\*\*.bin'):
    try:
        d = lzma.LZMADecompressor(lzma.FORMAT_ALONE)
        f = open(bpath, 'rb')
        buf = bytearray(); basepos = 0; ents = None; ei = 0; title = ''
        while True:
            chunk = f.read(4 * 1024 * 1024)
            if not chunk:
                break
            try:
                buf += d.decompress(chunk)
            except lzma.LZMAError:
                break
            if ents is None:
                if len(buf) < 8 * 1024 * 1024 and not d.eof:
                    continue
                r = parse_index(bytes(buf[:8 * 1024 * 1024]))
                if not r:
                    break
                title, allents = r
                for n, o, s in allents:
                    if PAT.search(n):
                        hits.append(('FILE', os.path.basename(os.path.dirname(bpath)), title, n, ''))
                ents = [(n, o, s) for n, o, s in allents if n.lower().endswith('.mdl') and s < 40 * 1024 * 1024]
            while ei < len(ents):
                n, o, s = ents[ei]; need = min(s, 6 * 1024 * 1024)
                if o + need > basepos + len(buf):
                    break
                b = bytes(buf[o - basepos:o - basepos + need]); nmdl += 1
                m = [x for x in seqnames(b) if PAT.search(x)]
                if m:
                    hits.append(('SEQ', os.path.basename(os.path.dirname(bpath)), title, n, ','.join(m[:6])))
                ei += 1
                if o - basepos > 64 * 1024 * 1024:
                    del buf[:o - basepos]; basepos = o
            if ents is not None and ei >= len(ents):
                break
        f.close()
    except Exception:
        continue
print('all done: %d mdl total, %.0fs' % (nmdl, time.time() - t0))
for h in hits:
    print(h)
