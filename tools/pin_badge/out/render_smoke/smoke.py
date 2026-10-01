import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import numpy as np
from PIL import Image
import pin_common as pc
import pin_render as pr

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..'))
D = 2.25
R = D / 2

RED, GREEN, BLUE, YELLOW = (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0)


def part(key, role, path, color, **kw):
    p = {'key': key, 'role': role, 'label': key, 'file': os.path.basename(path), 'local_path': path,
         'color': list(color), 'alpha': 1.0, 'translucent': False, 'hidden': False, 'material': None}
    p.update(kw)
    return p


def quadrant(name, xsign, zsign, color):
    # 2D coordinates (z, x); circle clipped to the quadrant rectangle, CCW
    big = 10
    z0, z1 = (0, big) if zsign > 0 else (-big, 0)
    x0, x1 = (0, big) if xsign > 0 else (-big, 0)
    rect = [(z0, x0), (z1, x0), (z1, x1), (z0, x1)]
    poly = pc.clip_convex(pc.circle_polygon(R, 128), rect)
    assert pc.signed_area(poly) > 0
    mb = pc.MeshBuilder()
    mb.polygon([(x, pc.dome_y(x, z, R), z) for (z, x) in poly])
    path = os.path.join(HERE, name + '.obj')
    pc.write_obj(path, mb.verts, mb.tris)
    return part(name, 'image', path, color)


def body_mesh():
    mb = pc.MeshBuilder()
    n = 128
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p = lambda a, y: (R * math.cos(a), y, R * math.sin(a))  # x = cos, z = sin
        # outward-facing quad (CCW seen from outside)
        mb.quad(p(a0, 0), p(a1, 0), p(a1, pc.BODY_THICKNESS), p(a0, pc.BODY_THICKNESS))
        c = (0, 0, 0)
        mb.polygon([c, p(a1, 0), p(a0, 0)])      # back cap faces -Y
    path = os.path.join(HERE, 'body.obj')
    pc.write_obj(path, mb.verts, mb.tris)
    return part('body', 'body', path, (0.8, 0.8, 0.8))


def uv_square():
    mb = pc.MeshBuilder()
    y = 0.3
    pts = [(-R, y, -R), (-R, y, R), (R, y, R), (R, y, -R)]
    # (x, z): (-R,-R) -> (-R,R) -> (R,R) -> (R,-R): in (z, x) = (-R,-R),(R,-R),(R,R),(-R,R) CCW
    pts = [(-R, y, -R), (-R, y, R), (R, y, R), (R, y, -R)]
    uvs = [((z / R + 1) / 2, (x / R + 1) / 2) for (x, _, z) in pts]
    mb.polygon(pts, uvs)
    path = os.path.join(HERE, 'uvsq.obj')
    r = pc.write_obj(path, mb.verts, mb.tris, mb.uvs)
    return part('face_uv', 'texture', path, (1, 1, 1))


def gloss_mesh():
    # small translucent disc patch upper-left (screen) = +X, -Z
    mb = pc.MeshBuilder()
    poly = pc.circle_polygon(0.35 * R, 48, cx=-0.45 * R, cy=0.45 * R)   # (z, x)
    mb.polygon([(x, pc.dome_y(x, z, R) + pc.GLOSS_LIFT, z) for (z, x) in poly])
    path = os.path.join(HERE, 'gloss.obj')
    pc.write_obj(path, mb.verts, mb.tris)
    return part('gloss', 'gloss', path, (1, 1, 1), alpha=0.22, translucent=True)


def close(a, b, tol=6):
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a, b))


def px(img, x, z, size):
    scale = size / (pr.VIEW_EXTENT * D)
    return img.getpixel((int(size / 2 + z * scale), int(size / 2 - x * scale)))


results = []


def check(name, cond, info=''):
    results.append((name, cond))
    print(('PASS ' if cond else 'FAIL ') + name + ' ' + str(info))


# ---------- manifest 1: 4 quadrants + body + gloss
parts = [body_mesh(),
         quadrant('c01', +1, -1, RED),      # screen top-left: x>0, z<0
         quadrant('c02', +1, +1, GREEN),    # top-right
         quadrant('c03', -1, -1, BLUE),     # bottom-left
         quadrant('c04', -1, +1, YELLOW)]   # bottom-right
man = {'name': 'smoke', 'slug': 'smoke', 'diameter': D, 'parts': parts}
size = 640
img = pr.render(man, 'front', size, ssaa=1, shading=False)
img.save(os.path.join(OUT, 'smoke_front_quadrants.png'))
q = R / 2
tl, tr, bl, br = px(img, q, -q, size), px(img, q, q, size), px(img, -q, -q, size), px(img, -q, q, size)
check('front TL red', close(tl, (255, 0, 0)), tl)
check('front TR green', close(tr, (0, 255, 0)), tr)
check('front BL blue', close(bl, (0, 0, 255)), bl)
check('front BR yellow', close(br, (255, 255, 0)), br)
check('background corner', close(img.getpixel((2, 2)), pr.BACKGROUND, 1), img.getpixel((2, 2)))
# shaded default render keeps colours within ~1%
img_s = pr.render(man, 'front', size)
tl_s = px(img_s, q, -q, size)
check('front shaded TL ~red (<=3% dark)', tl_s[0] >= 247 and tl_s[1] <= 3 and tl_s[2] <= 3, tl_s)
# culling of correct winding changes nothing
img_c = pr.render(man, 'front', size, cull=True, ssaa=1, shading=False)
d = np.abs(np.asarray(img_c, dtype=int) - np.asarray(img, dtype=int)).max()
check('cull=True front identical (winding CCW)', d == 0, d)

# ---------- orientation_check, res=2 and res=8
ref2 = Image.new('RGB', (2, 2))
ref2.putpixel((0, 0), (255, 0, 0)); ref2.putpixel((1, 0), (0, 255, 0))
ref2.putpixel((0, 1), (0, 0, 255)); ref2.putpixel((1, 1), (255, 255, 0))
oc = pr.orientation_check(man, ref2, 2)
print(oc)
check('orientation res2 ok', oc['ok'] and oc['best'] == 'as_is' and oc['as_is'] < 1, oc['as_is'])
ref8 = ref2.resize((8, 8), Image.NEAREST)
oc8 = pr.orientation_check(man, ref8, 8)
print(oc8)
check('orientation res8 ok', oc8['ok'], oc8['as_is'])
for nm, tf in (('lr', Image.FLIP_LEFT_RIGHT), ('ud', Image.FLIP_TOP_BOTTOM), ('rot180', Image.ROTATE_180)):
    o = pr.orientation_check(man, ref8.transpose(tf), 8)
    check('orientation flipped reference (%s) not ok' % nm, (not o['ok']) and o['best'] != 'as_is', (o['best'], round(o['margin'], 3)))

# ---------- manifest 2: UV square with texture (TL red, TR green, BL blue, BR yellow)
tex = Image.new('RGB', (64, 64))
for (cx, cy, col) in ((0, 0, (255, 0, 0)), (32, 0, (0, 255, 0)), (0, 32, (0, 0, 255)), (32, 32, (255, 255, 0))):
    tex.paste(Image.new('RGB', (32, 32), col), (cx, cy))
tex.save(os.path.join(OUT, 'smoke_texture.png'))
man2 = {'name': 'smoke uv', 'slug': 'smokeuv', 'diameter': D, 'parts': [uv_square()]}
img2 = pr.render(man2, 'front', size, texture_image=tex, ssaa=1, shading=False)
img2.save(os.path.join(OUT, 'smoke_front_uvsquare.png'))
tl2, tr2 = px(img2, q, -q, size), px(img2, q, q, size)
bl2, br2 = px(img2, -q, -q, size), px(img2, -q, q, size)
check('uv square TL red', close(tl2, (255, 0, 0)), tl2)
check('uv square TR green', close(tr2, (0, 255, 0)), tr2)
check('uv square BL blue', close(bl2, (0, 0, 255)), bl2)
check('uv square BR yellow', close(br2, (255, 255, 0)), br2)
img2n = pr.render(man2, 'front', size, texture_image=None, ssaa=1)
check('texture skipped when texture_image None', close(px(img2n, q, -q, size), pr.BACKGROUND, 1))
oc2 = pr.orientation_check(man2, ref8, 8, texture_image=tex)
print(oc2)
check('orientation with texture ok', oc2['ok'], oc2['as_is'])

# ---------- translucent gloss + all views + contact sheet
man3 = dict(man, parts=parts + [gloss_mesh()])
img_g = pr.render(man3, 'front', size, ssaa=1, shading=False)
tlg = px(img_g, 0.45 * R, -0.45 * R, size)
exp = tuple(int(255 * 0.78 + 255 * 0.22) if i == 0 else int(0.22 * 255) for i in range(3))
check('gloss blends over red (alpha .22)', close(tlg, exp, 4), (tlg, exp))
views = [pr.render(man3, v, 480) for v in pr.VIEWS]
sheet = pr.contact_sheet(views, ['front', 'three_quarter', 'side'], os.path.join(OUT, 'smoke_views.png'))
print('sheet', sheet)
# translucent part must not draw over background
check('gloss outside body untouched', close(px(img_g, 0, R * 1.1, size), pr.BACKGROUND, 1))
# hidden part skipped
hp = [dict(p) for p in parts]; hp[1]['hidden'] = True
img_h = pr.render(dict(man, parts=hp), 'front', size, ssaa=1, shading=False)
check('hidden part skipped', not close(px(img_h, q, -q, size), RED and (255, 0, 0)))

bad = [n for n, c in results if not c]
print('\n%d checks, %d failed' % (len(results), len(bad)))
sys.exit(1 if bad else 0)
