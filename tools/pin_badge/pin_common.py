"""Shared constants and helpers for the pin badge generator.

Frame contract (see SPEC.md): the OBJ coordinates ARE the pac model2 local frame,
because pac's urlobj loader reads `v x y z` verbatim with no axis swap.
    +Y = badge face normal (points out of the chest on spine-family bones)
    +X = image UP
    +Z = image RIGHT as seen by someone standing in front of the wearer
Front faces are CCW when viewed from outside (standard OBJ). pac reverses the
winding when it builds the mesh, which is exactly what Source's CW-front wants.
For a face that looks toward +Y, "CCW from outside" means CCW in 2D (z, x)
coordinates, i.e. positive signed area with z as the horizontal axis and x as the
vertical axis.
"""
import hashlib
import math
import os
import re

# ---------------------------------------------------------------- locations
REPO = r'C:\Users\poopy\OneDrive\Documents\GitHub\pacmp3s'
RAW_BASE = 'https://github.com/ax0rz0/pacmp3s/raw/refs/heads/main/'
PAC_DIR = r'C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\data\pac3'
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(TOOL_DIR, 'out')          # previews, manifests, test images

WATERMARK = 'claude skill made by ax0rz0'

# ---------------------------------------------------------------- geometry (Source units, ~inches)
DEFAULT_DIAMETER = 2.25
BODY_THICKNESS = 0.14     # body back at y = 0, rolled edge top at y = BODY_THICKNESS
DOME_HEIGHT = 0.07        # extra bulge at the centre of the face
LAYER_LIFT = 0.0          # image layers sit exactly on the dome (they partition it)
GLOSS_LIFT = 0.006        # gloss highlight floats this far above the dome
TEXTURE_LIFT = 0.003      # optional texture face floats above the image layers
CIRCLE_SEGMENTS = 128

# default placement: mirror of the user's pocket (spine 2 local (5.1, 8.8, 3.0))
DEFAULT_BONE = 'spine 2'
DEFAULT_POSITION = (6.0, 9.0, -3.5)
DEFAULT_ANGLES = (0.0, 0.0, 0.0)

METAL_COLOR = (0.72, 0.73, 0.76)
GLOSS_ALPHA = 0.22

MAX_LAYER_TRIS = 20000    # urlobj shreds meshes past ~65k expanded vertices; stay far below


# ---------------------------------------------------------------- naming
def slugify(name):
    s = re.sub(r'[^a-z0-9]+', '_', (name or '').lower()).strip('_')
    return (s[:40].strip('_')) or 'pin'


def uid(slug, key):
    """64 lowercase hex, unique per (badge, part), watermark suffix a0c3f."""
    return hashlib.sha256((slug + ':' + key).encode('utf-8')).hexdigest()[:59] + 'a0c3f'


def obj_dir(slug):
    return os.path.join(REPO, 'obj', 'pins', slug)


def obj_url(slug, filename):
    return RAW_BASE + 'obj/pins/' + slug + '/' + filename


def obj_filename(slug, content_hash, key):
    return 'pin_%s_%s_%s.obj' % (slug, content_hash, key)


def hex_color(rgb01):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(c * 255)))) for c in rgb01)


# ---------------------------------------------------------------- shape helpers
def dome_y(x, z, radius, base=BODY_THICKNESS, height=DOME_HEIGHT):
    """Height of the domed face at (x, z). Equals `base` at the rim, base+height at the centre."""
    r2 = (x * x + z * z) / (radius * radius)
    return base + height * (1.0 - min(r2, 1.0))


def circle_polygon(radius, segments=CIRCLE_SEGMENTS, cx=0.0, cy=0.0):
    """CCW polygon [(a, b), ...] approximating a circle in any 2D plane."""
    return [(cx + radius * math.cos(2 * math.pi * i / segments),
             cy + radius * math.sin(2 * math.pi * i / segments)) for i in range(segments)]


def signed_area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def clip_convex(subject, clip):
    """Sutherland-Hodgman: clip polygon `subject` by CONVEX CCW polygon `clip` (both 2D lists).
    Returns the clipped polygon (possibly empty), keeping the subject's orientation."""
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12

    def intersect(p, q, a, b):
        dx1, dy1 = q[0] - p[0], q[1] - p[1]
        dx2, dy2 = b[0] - a[0], b[1] - a[1]
        den = dx1 * dy2 - dy1 * dx2
        if abs(den) < 1e-15:
            return q
        t = ((a[0] - p[0]) * dy2 - (a[1] - p[1]) * dx2) / den
        return (p[0] + t * dx1, p[1] + t * dy1)

    out = list(subject)
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        inp, out = out, []
        if not inp:
            break
        s = inp[-1]
        for e in inp:
            if inside(e, a, b):
                if not inside(s, a, b):
                    out.append(intersect(s, e, a, b))
                out.append(e)
            elif inside(s, a, b):
                out.append(intersect(s, e, a, b))
            s = e
    return out


# ---------------------------------------------------------------- mesh building / OBJ io
class MeshBuilder:
    """Indexed triangle mesh with vertex welding (rounded-position key) and optional UVs."""

    def __init__(self, weld_digits=6):
        self.verts = []
        self.uvs = []
        self.tris = []
        self._index = {}
        self._digits = weld_digits

    def vertex(self, p, uv=None):
        key = (round(p[0], self._digits), round(p[1], self._digits), round(p[2], self._digits))
        if uv is not None:
            key = key + (round(uv[0], self._digits), round(uv[1], self._digits))
        i = self._index.get(key)
        if i is None:
            i = len(self.verts)
            self._index[key] = i
            self.verts.append((float(p[0]), float(p[1]), float(p[2])))
            if uv is not None:
                self.uvs.append((float(uv[0]), float(uv[1])))
        return i

    def tri(self, a, b, c):
        if a != b and b != c and a != c:
            self.tris.append((a, b, c))

    def polygon(self, pts, uvs=None):
        """Fan-triangulate a convex polygon given as 3D points in front-facing (CCW) order."""
        idx = [self.vertex(p, uvs[k] if uvs else None) for k, p in enumerate(pts)]
        for k in range(1, len(idx) - 1):
            self.tri(idx[0], idx[k], idx[k + 1])

    def quad(self, p0, p1, p2, p3):
        self.polygon([p0, p1, p2, p3])

    def merge(self, other):
        for (a, b, c) in other.tris:
            self.tri(self.vertex(other.verts[a]), self.vertex(other.verts[b]), self.vertex(other.verts[c]))


def write_obj(path, verts, tris, uvs=None, comment='pin badge'):
    """Plain OBJ the old pac urlobj parser accepts: `v`, optional `vt`, 1-based `f` triangles."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='\n', encoding='ascii') as f:
        f.write('# %s by %s\n' % (comment, WATERMARK))
        for v in verts:
            f.write('v %.5f %.5f %.5f\n' % v)
        if uvs:
            assert len(uvs) == len(verts), 'one vt per v'
            for uv in uvs:
                f.write('vt %.5f %.5f\n' % uv)
            for a, b, c in tris:
                f.write('f %d/%d %d/%d %d/%d\n' % (a + 1, a + 1, b + 1, b + 1, c + 1, c + 1))
        else:
            for a, b, c in tris:
                f.write('f %d %d %d\n' % (a + 1, b + 1, c + 1))
    return {'path': path, 'verts': len(verts), 'tris': len(tris)}


def read_obj(path):
    """Minimal reader matching what pac accepts. Returns (verts, tris, uvs_or_None)."""
    verts, uvs, tris = [], [], []
    with open(path, encoding='ascii') as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == 'v':
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif p[0] == 'vt':
                uvs.append((float(p[1]), float(p[2])))
            elif p[0] == 'f':
                idx = [int(t.split('/')[0]) - 1 for t in p[1:]]
                for k in range(1, len(idx) - 1):
                    tris.append((idx[0], idx[k], idx[k + 1]))
    return verts, tris, (uvs or None)
