import sys, os, math, io, threading, http.server
sys.path.insert(0, r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s\tools\pin_badge')
from PIL import Image
import numpy as np
import pin_image as pi_
from pin_common import read_obj, DEFAULT_DIAMETER, OUT_DIR

OUT = os.path.join(OUT_DIR, 'smoke_image')
RED, GREEN, BLUE, YEL = (220, 30, 30), (30, 200, 40), (30, 60, 220), (240, 220, 20)

# --- synthetic image: 4 quadrants + transparent bottom-right corner
im = Image.new('RGBA', (200, 200))
px = im.load()
for y in range(200):
    for x in range(200):
        px[x, y] = (RED if y < 100 and x < 100 else GREEN if y < 100 else BLUE if x < 100 else YEL) + (255,)
        if x >= 120 and y >= 120:
            px[x, y] = (0, 0, 0, 0)
RES = 48
p = pi_.prepare(im, res=RES)
assert p.size == (RES, RES) and p.mode == 'RGB'
grid, pal = pi_.quantize(p, colors=16)
print('palette', pal)
parts, edge = pi_.build_mosaic(grid, pal, OUT, lambda k: 'smoke_%s.obj' % k)
print('edge', edge)
R = DEFAULT_DIAMETER / 2
area = 0
tl_part = None
for part in parts:
    v, t, _ = read_obj(part['local_path'])
    assert len(v) == part['verts'] and len(t) == part['tris']
    for a, b, c in t:
        A, B, C = v[a], v[b], v[c]
        # (z,x) coords
        ar = 0.5 * ((B[2]-A[2])*(C[0]-A[0]) - (C[2]-A[2])*(B[0]-A[0]))
        assert ar > 1e-12, ('degenerate/cw tri', part['key'], ar)
        area += ar
    col255 = tuple(round(c * 255) for c in part['color'])
    print(part['key'], part['label'], part['pixels'], part['verts'], part['tris'], col255)
    if min(abs(col255[i]-RED[i]) for i in range(1)) < 40 and col255[0] > 180 and col255[1] < 80:
        tl_part = (part, v)
ratio = area / (math.pi * R * R)
print('area ratio', ratio)
assert abs(ratio - 1) < 0.01
part, v = tl_part
assert all(x > -1e-6 and z < 1e-6 for x, y, z in v), 'top-left layer not at x>0,z<0'
print('TL layer ok: x range %.3f..%.3f z range %.3f..%.3f' % (min(q[0] for q in v), max(q[0] for q in v), min(q[2] for q in v), max(q[2] for q in v)))
assert all(abs(c) <= 1 for c in edge)

# --- weld check: every non-boundary edge shared by exactly 2 tris across all layers combined
from collections import Counter
ec = Counter(); allv = {}
for part in parts:
    v, t, _ = read_obj(part['local_path'])
    def k(i): return tuple(round(c, 5) for c in v[i])
    for a, b, c in t:
        for e in ((a, b), (b, c), (c, a)):
            ec[(k(e[0]), k(e[1]))] += 1
bad = [e for e in ec if ec[(e[1], e[0])] == 0]
# boundary edges should lie on the circle
import math as m
offc = [e for e in bad if abs(m.hypot(e[0][2], e[0][0]) - R) > 1e-3 or abs(m.hypot(e[1][2], e[1][0]) - R) > 1e-3]
print('unmatched edges', len(bad), 'not on rim', len(offc))
assert not offc

# --- load_image variants
os.makedirs(OUT, exist_ok=True)
base = Image.new('RGBA', (30, 20), (10, 20, 30, 255))
base.save(os.path.join(OUT, 't.png'))
base.convert('RGB').save(os.path.join(OUT, 't.jpg'))
base.save(os.path.join(OUT, 't.webp'))
base.convert('L').save(os.path.join(OUT, 'g.png'))
pal_im = base.convert('RGB').quantize(4); pal_im.info['transparency'] = 0
pal_im.save(os.path.join(OUT, 'p.png'), transparency=0)
fr = [Image.new('RGB', (8, 8), c) for c in ((255, 0, 0), (0, 255, 0))]
fr[0].save(os.path.join(OUT, 'a.gif'), save_all=True, append_images=fr[1:])
for f in ('t.png', 't.jpg', 't.webp', 'g.png', 'p.png', 'a.gif'):
    r = pi_.load_image(os.path.join(OUT, f))
    assert r.mode == 'RGBA', f
    print('load', f, r.size, r.getpixel((0, 0)))
assert pi_.load_image(os.path.join(OUT, 'a.gif')).getpixel((0, 0))[:3][0] > 200

# --- URL load with redirect + UA check
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == '/redir':
            self.send_response(302); self.send_header('Location', '/t.png'); self.end_headers(); return
        if 'Mozilla' not in self.headers.get('User-Agent', ''):
            self.send_response(403); self.end_headers(); return
        data = open(os.path.join(OUT, 't.png'), 'rb').read()
        self.send_response(200); self.send_header('Content-Type', 'image/png'); self.end_headers(); self.wfile.write(data)
srv = http.server.HTTPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
r = pi_.load_image('http://127.0.0.1:%d/redir' % srv.server_port)
assert r.size == (30, 20)
print('url+redirect ok')

# --- prepare: pad / nearest / crop
wide = Image.new('RGBA', (100, 50), (255, 0, 0, 255))
pd = pi_.prepare(wide, res=20, fit='pad', bg=(0, 0, 255))
assert pd.getpixel((10, 0)) == (0, 0, 255) and pd.getpixel((10, 10)) == (255, 0, 0)
cr = pi_.prepare(wide, res=20, fit='crop')
assert cr.getpixel((0, 0)) == (255, 0, 0)
art = Image.new('RGBA', (16, 16), (0, 0, 0, 255)); art.putpixel((0, 0), (255, 0, 0, 255))
up = pi_.prepare(art, res=64)
assert set(up.getdata()) == {(0, 0, 0), (255, 0, 0)}, 'auto must be nearest for pixel art'
print('prepare ok')

# --- quantize: min_pixels / merge
t = Image.new('RGB', (40, 40), (100, 100, 100))
t.putpixel((20, 20), (255, 0, 0))                      # single in-circle pixel -> folded
for x in range(40): t.putpixel((x, 0), (104, 100, 100))  # near-dup, outside circle
g2, p2 = pi_.quantize(t, colors=8, min_pixels=3, merge_dist=10)
print('quantize fold', p2)
assert len(p2) == 1
print('ALL OK')
