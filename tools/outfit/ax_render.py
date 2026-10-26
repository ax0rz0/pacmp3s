"""Preview renders in the ax3d engine (headless Vulkan, PBR, shadows, bloom) instead of the CPU splat renderer.

    ax = Ax()                                   # launches `ax3d.exe --mcp --project <scratchpad>/adv/ax` (own folder, nothing in the user's repo)
    body = export_body(scene)                   # femsuit_04 in the bind pose, split by material slot, textures as PNG
    items = body + export_parts(parts, 'oni')   # accessory meshes (source frame) -> OBJ in the engine frame
    img = ax.render(items, views=('front', '34'), focus=HEAD, ...)

Frame conversion: Source (x forward, y left, z up, inches-ish) -> ax3d (+Y up, -Z forward, +X right, metres): ax = (-y, z, -x) * 0.0254.
"""
import base64
import io
import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_geom as ag
from meshgen import Mesh

AX_EXE = r'C:\Users\poopy\OneDrive\Documents\claude-workspace\ax3d\bin\ax3d.exe'
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HERE, 'adv', 'ax')
S = 0.0254
HEAD = (0.4, 0.0, 65.0)

VIEWS = {'front': (1.0, 0.0, 0.04), '34': (0.82, 0.57, 0.10), '34r': (0.82, -0.57, 0.10), 'left': (0.0, 1.0, 0.03), 'right': (0.0, -1.0, 0.03), 'back': (-1.0, 0.0, 0.08),
         '34b': (-0.75, -0.6, 0.15), 'top': (0.45, 0.15, 0.9), 'low': (0.8, 0.3, -0.45)}


def to_ax(V):
    V = np.asarray(V, float)
    return np.stack([-V[..., 1], V[..., 2], -V[..., 0]], -1) * S


def hexcol(c):
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in c)


class Ax:
    def __init__(self, project=PROJECT, exe=AX_EXE):
        os.makedirs(project, exist_ok=True)
        self.project = project
        self.p = subprocess.Popen([exe, '--mcp', '--project', project], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1)
        self.next_id = 1
        self.resp = {}
        self.lock = threading.Lock()
        self.log = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._err, daemon=True).start()
        self.request('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'pac-preview', 'version': '0.1'}})
        self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def _read(self):
        for line in self.p.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            for x in (m if isinstance(m, list) else [m]):
                if 'id' in x and ('result' in x or 'error' in x):
                    with self.lock:
                        self.resp[x['id']] = x

    def _err(self):
        for line in self.p.stderr:
            self.log.append(line)

    def _send(self, msg):
        self.p.stdin.write(json.dumps(msg, separators=(',', ':')) + '\n')
        self.p.stdin.flush()

    def request(self, method, params=None, timeout=180.0):
        i = self.next_id
        self.next_id += 1
        msg = {'jsonrpc': '2.0', 'id': i, 'method': method}
        if params is not None:
            msg['params'] = params
        self._send(msg)
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if i in self.resp:
                    r = self.resp.pop(i)
                    if 'error' in r:
                        raise RuntimeError('%s: %s' % (method, json.dumps(r['error'])[:600]))
                    return r['result']
            if self.p.poll() is not None:
                raise RuntimeError('ax3d exited: ' + ''.join(self.log[-5:]))
            time.sleep(0.005)
        raise TimeoutError(method)

    def call(self, tool, args=None):
        r = self.request('tools/call', {'name': tool, 'arguments': args or {}})
        img, txt = None, []
        for b in r.get('content', []):
            if b.get('type') == 'image':
                img = Image.open(io.BytesIO(base64.b64decode(b['data']))).convert('RGB')
            elif b.get('type') == 'text':
                txt.append(b['text'])
        if r.get('isError'):
            raise RuntimeError('%s failed: %s' % (tool, ' '.join(txt)[:800]))
        return img, ' '.join(txt)

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


# ------------------------------------------------------------------------------------------------------------------------------ geometry export
def write_obj_ax(mesh, path, name, smooth_deg=35.0, uv=None):
    """accessory mesh in the Source frame -> OBJ in the ax3d frame with smoothing-angle normals"""
    m = Mesh(to_ax(mesh.V), mesh.UV.copy() if len(mesh.UV) else np.zeros((len(mesh.V), 2)), mesh.F.copy())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return ag.write_obj_smooth(m, path, name, smooth_deg=smooth_deg, watermark='preview export')


def export_parts(parts, tag, subdir='models', smooth_deg=35.0):
    """parts: {name: dict(mesh=Mesh, color=(r,g,b), nolight=bool, ...)} -> item dicts for Ax.render"""
    items = []
    for name, p in parts.items():
        rel = '%s/%s_%s.obj' % (subdir, tag, name)
        write_obj_ax(p['mesh'], os.path.join(PROJECT, rel), '%s_%s' % (tag, name), smooth_deg=p.get('smooth', smooth_deg))
        items.append(dict(name='%s_%s' % (tag, name), obj=rel, color=p.get('color', (200, 200, 200)), glow=bool(p.get('nolight')) or bool(p.get('glow')), rough=p.get('rough', 0.45),
                          metal=p.get('metal', 0.0), alpha=p.get('alpha'), emissive=p.get('emissive'), double=p.get('double', False), pivot=p.get('pivot'), tex=p.get('tex')))
    return items


_BODY_CACHE = {}


def export_body(sc, skirt=False, skip=()):
    """the playermodel, split by material slot: flat colours or the stock textures (saved as PNG under tex/)"""
    key = ('body', skirt, tuple(skip))
    if key in _BODY_CACHE:
        return _BODY_CACHE[key]
    b = sc.b
    tr = b.triangles(skirt=skirt)
    names = np.array(b.mesh.textures)
    pos = to_ax(tr['pos'])
    nrm = tr['nrm'].copy()
    nrm = np.stack([-nrm[..., 1], nrm[..., 2], -nrm[..., 0]], -1)
    uv = tr['uv']
    flat = {'eyeball_l': (232, 232, 236), 'eyeball_r': (232, 232, 236), 'handfemale': (226, 182, 158), 'fmouth': (150, 70, 70)}
    os.makedirs(os.path.join(PROJECT, 'tex'), exist_ok=True)
    os.makedirs(os.path.join(PROJECT, 'models'), exist_ok=True)
    items = []
    for slot in np.unique(tr['slot']):
        n = str(names[slot])
        if n in skip:
            continue
        sel = np.nonzero(tr['slot'] == slot)[0]
        if len(sel) == 0:
            continue
        P = pos[sel].reshape(-1, 3)
        N = nrm[sel].reshape(-1, 3)
        U = uv[sel].reshape(-1, 2).copy()
        U[:, 1] = 1.0 - U[:, 1]
        rel = 'models/body_%s.obj' % n
        with open(os.path.join(PROJECT, rel), 'w', newline='\n') as f:
            f.write('# body slot %s\n' % n)
            f.write('o body_%s\n' % n)
            for v in P:
                f.write('v %.5f %.5f %.5f\n' % tuple(v))
            for t in U:
                f.write('vt %.5f %.5f\n' % tuple(t))
            for v in N:
                f.write('vn %.5f %.5f %.5f\n' % tuple(v / max(np.linalg.norm(v), 1e-9)))
            for t in range(len(sel)):
                a = 3 * t + 1
                f.write('f %d/%d/%d %d/%d/%d %d/%d/%d\n' % (a, a, a, a + 1, a + 1, a + 1, a + 2, a + 2, a + 2))
        texrel = None
        if n in b.stock and b.stock[n] is not None and n not in flat:
            arr = np.asarray(b.stock[n])
            texrel = 'tex/body_%s.png' % n
            Image.fromarray(arr[..., :3].astype(np.uint8)).save(os.path.join(PROJECT, texrel))
        items.append(dict(name='body_' + n, obj=rel, color=flat.get(n, (170, 170, 176)), glow=False, rough=0.55 if n != 'handfemale' else 0.45, metal=0.0, alpha=None, emissive=None, double=True,
                          pivot=None, tex=texrel, body=True))
    _BODY_CACHE[key] = items
    return items


# ------------------------------------------------------------------------------------------------------------------------------ scene text + rendering
def _mat_line(it):
    col = it['color']
    f = []
    if it.get('tex'):
        f.append('basecolourtexture=%s' % it['tex'])
        f.append('basecolour=#FFFFFF')
    else:
        f.append('basecolour=%s' % hexcol(col))
    f.append('roughness=%.3f metallic=%.3f' % (it['rough'], it['metal']))
    if it.get('glow'):
        e = it.get('emissive')
        if e is None:
            e = tuple(c / 255.0 * 3.2 for c in col)
        f = ['basecolour=#000000', 'roughness=0.8', 'emissive=%.3f,%.3f,%.3f' % tuple(e)]
    elif it.get('emissive') is not None:
        f.append('emissive=%.3f,%.3f,%.3f' % tuple(it['emissive']))
    if it.get('alpha') is not None:
        f.append('alphamode=Blend')
        c = it['color']
        f = [x for x in f if not x.startswith('basecolour=')]
        f.append('basecolour=#%02X%02X%02X%02X' % (int(c[0]), int(c[1]), int(c[2]), int(round(255 * it['alpha']))))
    if it.get('mask'):
        f.append('alphamode=Mask alphacutoff=0.5')
    if it.get('double'):
        f.append('doublesided=true')
    return 'Material ' + ' '.join(f)


def scene_text(items, cam_pos, cam_target, fov, sun_yaw, sun_pitch, key=3.2, ambient=1.0, bg=((0.17, 0.18, 0.22), (0.12, 0.125, 0.15), (0.06, 0.06, 0.075)), lights=(), exposure=1.0):
    """cam_pos / cam_target in ax3d metres"""
    out = ['Lighting:']
    z, h, g = bg
    out.append('  Sky sunpitch=%.1f sunyaw=%.1f sunintensity=%.2f ambientstrength=%.2f exposure=%.2f zenith=%.3f,%.3f,%.3f horizon=%.3f,%.3f,%.3f ground=%.3f,%.3f,%.3f' % (
        sun_pitch, sun_yaw, key, ambient, exposure, *z, *h, *g))
    out.append('Materials:')
    for it in items:
        out.append('  m_%s:' % it['name'])
        out.append('    ' + _mat_line(it))
    out.append('Workspace:')
    for it in items:
        out.append('  %s:' % it['name'])
        out.append('    Transform position=0,0,0')
        out.append('    MeshRenderer mesh=%s material=m_%s' % (it['obj'], it['name']))
    for i, L in enumerate(lights):
        out.append('  light%d:' % i)
        out.append('    Transform position=%.4f,%.4f,%.4f' % tuple(L['pos']))
        out.append('    Light kind=%s colour=%s intensity=%.2f range=%.2f' % (L.get('kind', 'Directional'), L['colour'], L['intensity'], L.get('range', 0)))
        out.append('    LookAt target=%.4f,%.4f,%.4f' % tuple(L.get('target', cam_target)))
    out.append('  cam:')
    out.append('    Transform position=%.4f,%.4f,%.4f' % tuple(cam_pos))
    out.append('    Camera fov=%.2f near=0.05 far=60' % fov)
    out.append('    LookAt target=%.4f,%.4f,%.4f' % tuple(cam_target))
    return '\n'.join(out) + '\n'


def view_rig(view, focus, dist, fov, aspect):
    """camera position + light rig for a named view (all Source frame in, ax3d out)"""
    d = np.asarray(VIEWS[view] if isinstance(view, str) else view, float)
    d = d / np.linalg.norm(d)
    f = np.asarray(focus, float)
    cam_src = f + d * dist
    # lights are placed relative to the camera direction: key upper left of the camera, fill right, rim behind
    az = np.arctan2(d[1], d[0])

    def rot(a, elev, r):
        return f + np.array([np.cos(az + a) * np.cos(elev), np.sin(az + a) * np.cos(elev), np.sin(elev)]) * r

    return to_ax(cam_src), to_ax(f), rot


def render_item_views(ax, items, views=('front', '34'), focus=HEAD, radius=10.0, fov=24.0, size=(560, 700), key=3.6, ambient=1.3, rim=(0.55, 0.78, 1.0), rim_i=2.2, bloom=True, fill=1.0,
                      exposure=1.0, bg=None, ssao=True, target=None):
    ax.call('render.settings', dict(bloom=bloom, bloom_threshold=1.7, bloom_strength=0.45, ssao=ssao, ssao_radius=0.12, ssao_strength=1.2, msaa=4, shadows=True, shadow_map_size=4096,
                                    shadow_distance=6.0, ibl=True))
    dist = radius / np.tan(np.radians(fov) / 2) * 1.08
    ims = []
    for v in views:
        cam, tgt, rot = view_rig(v, focus, dist, fov, size[0] / size[1])
        if target is not None:
            tgt = to_ax(target)
        # sun = key light from the camera's upper left (compass heading of the direction from the focus to the light)
        kpos = to_ax(rot(np.radians(40), np.radians(35), 100.0))
        kd = kpos - to_ax(np.asarray(focus, float))
        heading = (np.degrees(np.arctan2(kd[0], kd[2])) + 360) % 360
        lights = [dict(kind='Directional', pos=to_ax(rot(np.radians(-50), np.radians(10), 100.0)), colour='#E4E6F2', intensity=fill * 2.0, target=to_ax(np.asarray(focus, float))),
                  dict(kind='Directional', pos=to_ax(rot(np.radians(150), np.radians(30), 100.0)), colour=hexcol([c * 255 for c in rim]), intensity=rim_i, target=to_ax(np.asarray(focus, float)))]
        text = scene_text(items, cam, tgt, fov, heading, 35.0, key=key, ambient=ambient, lights=lights, exposure=exposure) if bg is None else scene_text(items, cam, tgt, fov, heading, 35.0, key=key, ambient=ambient, bg=bg, lights=lights, exposure=exposure)
        ax.call('scene.set', {'text': text})
        img, _ = ax.call('render.screenshot', dict(width=size[0], height=size[1]))
        ims.append(np.asarray(img))
    return np.concatenate(ims, axis=1)


def export_soup(name, P, N, UV, tex_png=None, color=(200, 200, 200), rough=0.5, metal=0.0, mask=False, double=True, glow=False, alpha=None):
    """arbitrary triangle soup (T,3,3) positions / normals (ax frame) + (T,3,2) uv (image-down v) -> OBJ + png in the project, returns an item dict"""
    T = len(P)
    rel = 'models/%s.obj' % name
    os.makedirs(os.path.join(PROJECT, 'models'), exist_ok=True)
    with open(os.path.join(PROJECT, rel), 'w', newline='\n') as f:
        f.write('o %s\n' % name)
        for v in P.reshape(-1, 3):
            f.write('v %.5f %.5f %.5f\n' % tuple(v))
        for t in UV.reshape(-1, 2):
            f.write('vt %.5f %.5f\n' % (t[0], 1.0 - t[1]))
        for v in N.reshape(-1, 3):
            v = v / max(np.linalg.norm(v), 1e-9)
            f.write('vn %.5f %.5f %.5f\n' % tuple(v))
        for t in range(T):
            a = 3 * t + 1
            f.write('f %d/%d/%d %d/%d/%d %d/%d/%d\n' % (a, a, a, a + 1, a + 1, a + 1, a + 2, a + 2, a + 2))
    texrel = None
    if tex_png is not None:
        os.makedirs(os.path.join(PROJECT, 'tex'), exist_ok=True)
        texrel = 'tex/%s.png' % name
        tex_png.save(os.path.join(PROJECT, texrel))
    return dict(name=name, obj=rel, color=color, glow=glow, rough=rough, metal=metal, alpha=alpha, emissive=None, double=double, pivot=None, tex=texrel, mask=mask)
