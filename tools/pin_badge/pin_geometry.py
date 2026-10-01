"""Hardware geometry for the pin badge: body, UV dome face, gloss crescent, metal back + pin, rim.

Frame (see SPEC.md / pin_common.py): +Y = face normal, +X = image up, +Z = image right (viewer's view).
Every surface is oriented by an explicit outward hint, so front faces are CCW in (z, x) for +Y-facing
surfaces, radially outward for side walls, and -Y for the back.

Public API:
    build_hardware(out_dir, file_for_key, diameter=DEFAULT_DIAMETER, edge_color=(1, 1, 1)) -> list[dict]
    build_base_set() -> list[dict]      (writes obj/pins/base/pin_base_<key>.obj)
"""
import math
import os

from pin_common import (
    REPO, DEFAULT_DIAMETER, BODY_THICKNESS, GLOSS_LIFT, TEXTURE_LIFT, CIRCLE_SEGMENTS,
    METAL_COLOR, GLOSS_ALPHA, MAX_LAYER_TRIS, MeshBuilder, write_obj, dome_y,
)

LABELS = {
    'body': 'pin badge (MOVE ME)',
    'face_uv': 'image (paste URL into material)',
    'gloss': 'gloss (hide to remove)',
    'back': 'metal back + pin',
    'rim': 'metal rim (unhide for framed look)',
}
ROLES = {'body': 'body', 'face_uv': 'texture', 'gloss': 'gloss', 'back': 'back', 'rim': 'rim'}
KEYS = ('body', 'face_uv', 'gloss', 'back', 'rim')

FACE_SEGMENTS = max(128, CIRCLE_SEGMENTS)
FACE_RINGS = 16
PLATE_THICKNESS = 0.04


# ---------------------------------------------------------------- small vector helpers
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add3(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    l = math.sqrt(_dot(a, a))
    return (a[0] / l, a[1] / l, a[2] / l)


def _oriented_tri(mb, pa, pb, pc, hint, uvs=None):
    """Add triangle whose right-handed normal ((b-a)x(c-a)) agrees with `hint` (outward direction)."""
    n = _cross(_sub(pb, pa), _sub(pc, pa))
    if _dot(n, n) < 1e-18:
        return
    if _dot(n, hint) < 0:
        pb, pc = pc, pb
        if uvs:
            uvs = (uvs[0], uvs[2], uvs[1])
    ia = mb.vertex(pa, uvs[0] if uvs else None)
    ib = mb.vertex(pb, uvs[1] if uvs else None)
    ic = mb.vertex(pc, uvs[2] if uvs else None)
    mb.tri(ia, ib, ic)


def _tube(mb, p0, p1, r0, r1, sides, cap0=True, cap1=True):
    """Closed (optionally capped) frustum/cylinder from p0 to p1. r1 == 0 makes a cone tip."""
    axis = _norm(_sub(p1, p0))
    ref = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.9 else (1.0, 0.0, 0.0)
    e1 = _norm(_sub(ref, _scale(axis, _dot(ref, axis))))
    e2 = _cross(axis, e1)

    def ring(c, r):
        return [_add3(c, _add3(_scale(e1, r * math.cos(2 * math.pi * i / sides)),
                               _scale(e2, r * math.sin(2 * math.pi * i / sides)))) for i in range(sides)]

    def radial(p):
        rel = _sub(p, p0)
        return _sub(rel, _scale(axis, _dot(rel, axis)))

    ra = ring(p0, r0)
    rb = ring(p1, r1) if r1 > 0 else None
    for i in range(sides):
        j = (i + 1) % sides
        if rb is not None:
            a, b, c, d = ra[i], ra[j], rb[j], rb[i]
            hint = radial(_scale(_add3(_add3(a, b), _add3(c, d)), 0.25))
            _oriented_tri(mb, a, b, c, hint)
            _oriented_tri(mb, a, c, d, hint)
        else:
            hint = radial(_scale(_add3(ra[i], ra[j]), 0.5))
            _oriented_tri(mb, ra[i], ra[j], p1, hint)
        if cap0 and r0 > 0:
            _oriented_tri(mb, p0, ra[i], ra[j], _scale(axis, -1.0))
        if cap1 and rb is not None:
            _oriented_tri(mb, p1, rb[i], rb[j], axis)


# ---------------------------------------------------------------- parts
def _body(R):
    mb = MeshBuilder()
    _tube(mb, (0.0, 0.0, 0.0), (0.0, BODY_THICKNESS, 0.0), R, R, CIRCLE_SEGMENTS)
    return mb


def _face_uv(R):
    """Polar dome: one centre vertex + FACE_RINGS rings of FACE_SEGMENTS vertices, vt per vertex."""
    mb = MeshBuilder()
    up = (0.0, 1.0, 0.0)

    def vert(x, z):
        y = dome_y(x, z, R) + TEXTURE_LIFT
        return (x, y, z), ((z / R + 1.0) * 0.5, (x / R + 1.0) * 0.5)

    rings = []
    for k in range(1, FACE_RINGS + 1):
        r = R * k / FACE_RINGS
        row = []
        for i in range(FACE_SEGMENTS):
            t = 2 * math.pi * i / FACE_SEGMENTS
            row.append(vert(r * math.sin(t), r * math.cos(t)))      # x = r sin, z = r cos (CCW in (z, x))
        rings.append(row)
    centre = vert(0.0, 0.0)
    n = FACE_SEGMENTS
    for i in range(n):
        j = (i + 1) % n
        _oriented_tri(mb, centre[0], rings[0][i][0], rings[0][j][0], up,
                      (centre[1], rings[0][i][1], rings[0][j][1]))
    for k in range(FACE_RINGS - 1):
        for i in range(n):
            j = (i + 1) % n
            a, b, c, d = rings[k][i], rings[k + 1][i], rings[k + 1][j], rings[k][j]
            _oriented_tri(mb, a[0], b[0], c[0], up, (a[1], b[1], c[1]))
            _oriented_tri(mb, a[0], c[0], d[0], up, (a[1], c[1], d[1]))
    return mb


def _gloss(R):
    """Crescent between circle A (r = 0.92R at origin) and circle B shifted toward the lower-right
    (-X, +Z): occupies the viewer's upper-left (+X, -Z) of the dome, spanning about +-65 degrees."""
    a = 0.92 * R
    d = 0.30 * R
    phi0 = math.radians(65.0)
    b = math.sqrt(a * a + d * d + 2 * a * d * math.cos(phi0))
    psi0 = math.atan2(a * math.sin(phi0), a * math.cos(phi0) + d)
    s2 = math.sqrt(0.5)
    u = (s2, -s2)       # (x, z) toward the upper-left
    w = (s2, s2)        # perpendicular
    segs, rows = 48, 4

    def on_circle(cx, cz, rad, ang):
        return (cx + rad * (math.cos(ang) * u[0] + math.sin(ang) * w[0]),
                cz + rad * (math.cos(ang) * u[1] + math.sin(ang) * w[1]))

    outer, inner = [], []
    for i in range(segs + 1):
        f = i / segs
        outer.append(on_circle(0.0, 0.0, a, -phi0 + 2 * phi0 * f))
        inner.append(on_circle(-d * u[0], -d * u[1], b, -psi0 + 2 * psi0 * f))
    inner[0], inner[-1] = outer[0], outer[-1]          # endpoints coincide exactly

    def pt(i, k):
        t = k / rows
        x = outer[i][0] + (inner[i][0] - outer[i][0]) * t
        z = outer[i][1] + (inner[i][1] - outer[i][1]) * t
        return (x, dome_y(x, z, R) + GLOSS_LIFT, z)

    mb = MeshBuilder()
    up = (0.0, 1.0, 0.0)
    for i in range(segs):
        for k in range(rows):
            p00, p10, p11, p01 = pt(i, k), pt(i + 1, k), pt(i + 1, k + 1), pt(i, k + 1)
            _oriented_tri(mb, p00, p10, p11, up)
            _oriented_tri(mb, p00, p11, p01, up)
    return mb


def _back(R):
    mb = MeshBuilder()
    # plate: y in [-PLATE_THICKNESS, 0], radius 0.9R
    _tube(mb, (0.0, -PLATE_THICKNESS, 0.0), (0.0, 0.0, 0.0), 0.9 * R, 0.9 * R, CIRCLE_SEGMENTS)
    yc = -PLATE_THICKNESS - 0.05                       # needle / barrel axis height (barrel touches the plate)
    # hinge barrel across X at the -Z end
    _tube(mb, (-0.12, yc, -0.72 * R), (0.12, yc, -0.72 * R), 0.05, 0.05, 14)
    # needle along Z with a sharpened tip at +Z
    _tube(mb, (0.0, yc, -0.72 * R), (0.0, yc, 0.62 * R), 0.02, 0.02, 10)
    _tube(mb, (0.0, yc, 0.62 * R), (0.0, yc, 0.78 * R), 0.02, 0.0, 10, cap0=False)
    return mb


def _rim(R):
    """Thin raised metal ring: chamfered profile swept around Y, wrapping the edge."""
    T = BODY_THICKNESS
    ri, ro = R - 0.07, R + 0.012
    yb, yt = T - 0.02, T + 0.035
    prof = [(ri, yb), (ro, yb), (ro, yt - 0.015), (ro - 0.015, yt), (ri + 0.02, yt), (ri, yt - 0.015)]
    pc = (sum(p[0] for p in prof) / len(prof), sum(p[1] for p in prof) / len(prof))
    n = CIRCLE_SEGMENTS
    mb = MeshBuilder()

    def at(pr, t):
        return (pr[0] * math.sin(t), pr[1], pr[0] * math.cos(t))

    for i in range(n):
        t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        tm = 0.5 * (t0 + t1)
        for j in range(len(prof)):
            p, q = prof[j], prof[(j + 1) % len(prof)]
            mid = ((p[0] + q[0]) * 0.5 - pc[0], (p[1] + q[1]) * 0.5 - pc[1])
            hint = (mid[0] * math.sin(tm), mid[1], mid[0] * math.cos(tm))
            a, b, c, d = at(p, t0), at(p, t1), at(q, t1), at(q, t0)
            _oriented_tri(mb, a, b, c, hint)
            _oriented_tri(mb, a, c, d, hint)
    return mb


_BUILDERS = {'body': _body, 'face_uv': _face_uv, 'gloss': _gloss, 'back': _back, 'rim': _rim}


# ---------------------------------------------------------------- public API
def build_hardware(out_dir, file_for_key, diameter=DEFAULT_DIAMETER, edge_color=(1, 1, 1)):
    """Write the five hardware OBJs into out_dir and return their manifest part dicts.

    `file_for_key(key)` supplies the OBJ filename. 'url' is left for the caller to fill in.
    """
    R = diameter / 2.0
    parts = []
    for key in KEYS:
        mb = _BUILDERS[key](R)
        assert 0 < len(mb.tris) <= MAX_LAYER_TRIS, (key, len(mb.tris))
        fname = file_for_key(key)
        path = os.path.join(out_dir, fname)
        write_obj(path, mb.verts, mb.tris, mb.uvs if mb.uvs else None, comment='pin badge ' + key)
        if key == 'body':
            color = [float(c) for c in edge_color]
        elif key in ('back', 'rim'):
            color = [float(c) for c in METAL_COLOR]
        else:
            color = [1.0, 1.0, 1.0]
        parts.append({
            'key': key, 'role': ROLES[key], 'label': LABELS[key], 'file': fname, 'local_path': path,
            'color': color, 'alpha': GLOSS_ALPHA if key == 'gloss' else 1.0,
            'translucent': key == 'gloss', 'hidden': key == 'rim', 'material': None,
            'verts': len(mb.verts), 'tris': len(mb.tris),
        })
    return parts


def build_base_set():
    """Write the static shared set obj/pins/base/pin_base_<key>.obj and return its parts list."""
    base_dir = os.path.join(REPO, 'obj', 'pins', 'base')
    return build_hardware(base_dir, lambda key: 'pin_base_%s.obj' % key, DEFAULT_DIAMETER, (1, 1, 1))


# ---------------------------------------------------------------- smoke test
def _smoke():
    from pin_common import read_obj, OUT_DIR
    R = DEFAULT_DIAMETER / 2.0
    scratch = os.path.join(OUT_DIR, 'geom_test')
    parts_a = build_hardware(scratch, lambda k: 'test_%s.obj' % k, 2.25, (0.2, 0.4, 0.8))
    parts = build_base_set()
    assert [p['key'] for p in parts] == list(KEYS)
    assert [(p['verts'], p['tris']) for p in parts] == [(p['verts'], p['tris']) for p in parts_a]

    def tri_geom(verts, tris):
        for a, b, c in tris:
            pa, pb, pc = verts[a], verts[b], verts[c]
            n = _cross(_sub(pb, pa), _sub(pc, pa))
            yield pa, pb, pc, n

    def volume(verts, tris):
        return sum(_dot(pa, _cross(pb, pc)) for pa, pb, pc, _ in tri_geom(verts, tris)) / 6.0

    for p in parts:
        verts, tris, uvs = read_obj(p['local_path'])
        assert len(verts) == p['verts'] and len(tris) == p['tris'], p['key']
        assert all(0 <= i < len(verts) for t in tris for i in t)
        assert len(tris) <= MAX_LAYER_TRIS
        areas = [0.5 * math.sqrt(_dot(n, n)) for _, _, _, n in tri_geom(verts, tris)]
        assert min(areas) > 1e-8, (p['key'], 'degenerate', min(areas))
        print('%-8s verts=%5d tris=%5d min_area=%.2e uv=%s' % (p['key'], len(verts), len(tris), min(areas),
                                                               'yes' if uvs else 'no'))
        assert (uvs is not None) == (p['key'] == 'face_uv')

    def load(key):
        return read_obj(next(p['local_path'] for p in parts if p['key'] == key))

    # body: closed, outward, volume ~ pi R^2 T
    v, t, _ = load('body')
    vol = volume(v, t)
    exp = math.pi * R * R * BODY_THICKNESS
    assert 0.98 * exp < vol <= exp * 1.001, (vol, exp)
    c = (0.0, BODY_THICKNESS / 2, 0.0)
    assert all(_dot(n, _sub(((pa[0] + pb[0] + pc[0]) / 3, (pa[1] + pb[1] + pc[1]) / 3, (pa[2] + pb[2] + pc[2]) / 3), c)) > 0
               for pa, pb, pc, n in tri_geom(v, t)), 'body not outward'
    print('body volume %.4f (cylinder %.4f)' % (vol, exp))

    # face_uv: +Y facing, projected area ~ pi R^2, UV mapping
    v, t, uv = load('face_uv')
    proj = 0.0
    for pa, pb, pc, n in tri_geom(v, t):
        assert n[1] > 0, 'face_uv triangle not +Y facing'
        proj += 0.5 * n[1]
    print('face_uv projected area %.4f vs pi R^2 %.4f (ratio %.5f)' % (proj, math.pi * R * R, proj / (math.pi * R * R)))
    assert abs(proj / (math.pi * R * R) - 1) < 0.005
    for (x, y, z), (u, w) in zip(v, uv):
        assert abs(u - (z / R + 1) / 2) < 1e-4 and abs(w - (x / R + 1) / 2) < 1e-4
        assert abs(y - (dome_y(x, z, R) + TEXTURE_LIFT)) < 1e-4
        assert x * x + z * z <= R * R * 1.0001
    tx, tz = R * 0.7, -R * 0.7
    k = min(range(len(v)), key=lambda i: (v[i][0] - tx) ** 2 + (v[i][2] - tz) ** 2)
    print('vertex nearest (x=0.7R, z=-0.7R): pos=%s uv=%s' % (v[k], uv[k]))
    assert uv[k][0] < 0.5 and uv[k][1] > 0.5
    rim_n = sum(1 for p in v if abs(math.hypot(p[0], p[2]) - R) < 1e-4)
    rings = len({round(math.hypot(p[0], p[2]), 3) for p in v})
    print('face_uv rim segments %d, radial rings %d' % (rim_n, rings - 1))
    assert rim_n >= 128 and rings - 1 >= 12

    # gloss: +Y facing, upper-left (+X, -Z), lifted
    v, t, _ = load('gloss')
    for pa, pb, pc, n in tri_geom(v, t):
        assert n[1] > 0
    assert all(abs(p[1] - (dome_y(p[0], p[2], R) + GLOSS_LIFT)) < 1e-4 for p in v)
    mx = sum(p[0] for p in v) / len(v)
    mz = sum(p[2] for p in v) / len(v)
    print('gloss centroid x=%.3f z=%.3f (expect x>0, z<0), bbox x[%.2f,%.2f] z[%.2f,%.2f]' % (
        mx, mz, min(p[0] for p in v), max(p[0] for p in v), min(p[2] for p in v), max(p[2] for p in v)))
    assert mx > 0 and mz < 0

    # back + rim: closed solids with positive (outward) volume; back lies at y <= 0
    v, t, _ = load('back')
    assert volume(v, t) > 0 and max(p[1] for p in v) <= 1e-9 and min(p[1] for p in v) < -0.1
    ys = [p[1] for p in v]
    print('back volume %.4f, y range [%.3f, %.3f], z range [%.3f, %.3f]' % (
        volume(v, t), min(ys), max(ys), min(p[2] for p in v), max(p[2] for p in v)))
    assert not any(n[1] > 0 and abs(pa[1] + PLATE_THICKNESS) < 1e-9 and abs(pb[1] + PLATE_THICKNESS) < 1e-9
                   and abs(pc[1] + PLATE_THICKNESS) < 1e-9 for pa, pb, pc, n in tri_geom(v, t)), 'plate bottom faces up'
    v, t, _ = load('rim')
    assert volume(v, t) > 0
    print('rim volume %.4f, hidden=%s' % (volume(v, t), parts[4]['hidden']))
    print('ALL OK')


if __name__ == '__main__':
    _smoke()
