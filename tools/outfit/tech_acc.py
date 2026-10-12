"""BNA accessories for the tech expert outfit (technical_expert.mdl in the hi-vis vest + Female_04 head swap), built on the real surfaces in the in-game bind pose.
Every piece is authored in world space (x forward, y left, z up); the DeformedRig then maps it through the user's feminiser bone scales into the bone-local OBJs."""
import numpy as np
from PIL import Image, ImageDraw

import ethics_paint as ep
import meshgen as mg
from ethics_acc import Acc, Surface, smooth_path
from ethics_common import INDIGO, MAGENTA, NAVY, PINK, ROYAL
from ethics_styles import FONT_BOLD, FONT_REG, Sprite, _basis, _font, badge_texture, cyber_glasses

SP = 'ValveBiped.Bip01_'


def frame_z(axis, up_hint=(0, 0, 1.0)):
    """rotation whose third column is `axis` (the other two are arbitrary perpendicular directions, x kept horizontal when possible)"""
    z = np.asarray(axis, float)
    z = z / np.linalg.norm(z)
    x = np.cross(up_hint, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.cross((0, 1.0, 0), z)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z, x), z], axis=1)


def frame_yz(y, z):
    """right-handed rotation with the given (unit) second and third columns"""
    y = np.asarray(y, float) / np.linalg.norm(y)
    z = np.asarray(z, float) / np.linalg.norm(z)
    x = np.cross(y, z)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z, x), z], axis=1)


# ------------------------------------------------------------------------------------------------------------------------------ textures
def datapad_texture(w=512, h=768):
    """a small HUD: PINK title bar, emblem, status bars, a waveform and a grid"""
    img = Image.new('RGB', (w, h), (7, 12, 40))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, int(h * 0.105)], fill=PINK)
    d.text((w * 0.06, h * 0.053), 'TECH-OPS', font=_font(FONT_BOLD, int(h * 0.05)), fill=(255, 255, 255), anchor='lm')
    for i in range(4):                                                      # signal bars
        x0 = w * (0.72 + 0.055 * i)
        hh = h * (0.025 + 0.012 * i)
        d.rectangle([x0, h * 0.082 - hh, x0 + w * 0.035, h * 0.082], fill=(255, 255, 255))
    em = ep.emblem_image(int(w * 0.46), PINK)
    em8 = Image.fromarray((em * 255).astype(np.uint8), 'RGBA')
    img.paste(em8, (int(w * 0.27), int(h * 0.15)), em8)
    labels = [('CORE', 0.86, PINK), ('LINK', 0.62, INDIGO), ('PWR', 0.74, MAGENTA), ('NET', 0.38, ROYAL)]
    for i, (lab, frac, col) in enumerate(labels):
        y = h * (0.50 + 0.075 * i)
        d.text((w * 0.07, y + h * 0.02), lab, font=_font(FONT_BOLD, int(h * 0.032)), fill=(220, 220, 245), anchor='lm')
        d.rounded_rectangle([w * 0.30, y, w * 0.93, y + h * 0.04], radius=int(h * 0.01), fill=(20, 30, 75))
        d.rounded_rectangle([w * 0.30, y, w * (0.30 + 0.63 * frac), y + h * 0.04], radius=int(h * 0.01), fill=col)
    xs = np.linspace(w * 0.07, w * 0.93, 60)                                # waveform
    ys = h * 0.88 + np.sin(xs / w * 22) * h * 0.025 * np.sin(xs / w * 5 + 1) + np.cos(xs / w * 51) * h * 0.008
    d.line(list(zip(xs, ys)), fill=PINK, width=max(2, int(h * 0.006)))
    for gx in np.linspace(w * 0.07, w * 0.93, 7):
        d.line([(gx, h * 0.82), (gx, h * 0.94)], fill=(25, 36, 90), width=1)
    d.rectangle([0, int(h * 0.975), w, h], fill=INDIGO)
    return np.asarray(img)


def back_patch_texture(size=512):
    """backpack patch: NAVY rounded square, PINK border, emblem and a name strip"""
    img = Image.new('RGB', (size, size), NAVY)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([size * 0.03, size * 0.03, size * 0.97, size * 0.97], radius=int(size * 0.12), outline=PINK, width=int(size * 0.04))
    em = ep.emblem_image(int(size * 0.58), PINK)
    em8 = Image.fromarray((em * 255).astype(np.uint8), 'RGBA')
    img.paste(em8, (int(size * 0.21), int(size * 0.13)), em8)
    d.rounded_rectangle([size * 0.16, size * 0.76, size * 0.84, size * 0.88], radius=int(size * 0.03), fill=ROYAL)
    d.text((size / 2, size * 0.82), 'TECH EXPERT', font=_font(FONT_BOLD, int(size * 0.07)), fill=(255, 255, 255), anchor='mm')
    return np.asarray(img)


# ------------------------------------------------------------------------------------------------------------------------------ forearm sections
def arm_frame(rig, side):
    """elbow, hand, unit axis (elbow -> hand), dorsal (up/out) direction and the depth (front/back) direction of a forearm"""
    e = rig.world[rig.bone('%s_Forearm' % side)][:3, 3]
    h = rig.world[rig.bone('%s_Hand' % side)][:3, 3]
    ax = (h - e) / np.linalg.norm(h - e)
    up = np.array([0, 0, 1.0]) - ax * ax[2]
    up /= np.linalg.norm(up)
    return e, h, ax, up, np.cross(ax, up)


def section(S, c, up, dep, reach=8.0, nang=24):
    """cross-section of the sleeve at the axis point c: (centre, semi-axis along up, semi-axis along dep, extent of the top above c).
    The ellipse encloses 88% of the surface points found by rays towards the axis from nang directions (a snug fit, the highest wrinkles poke through)."""
    pts = []
    for a in np.linspace(0, 2 * np.pi, nang, endpoint=False):
        d = np.cos(a) * up + np.sin(a) * dep
        r = S.cast(c + d * reach, -d)
        if r:
            pts.append(r[1] - c)
    if len(pts) < nang // 2:
        return c, 2.0, 2.0, 1.5
    pts = np.array(pts)
    x, y = pts @ up, pts @ dep
    xc, yc = (x.max() + x.min()) / 2, (y.max() + y.min()) / 2
    a, b = (x.max() - x.min()) / 2, (y.max() - y.min()) / 2
    s = np.percentile(np.sqrt(((x - xc) / a) ** 2 + ((y - yc) / b) ** 2), 88)       # snug: the top wrinkles may poke through the band
    return c + up * xc + dep * yc, a * s, b * s, float(x.max())


def ring_on_arm(S, e, h, ax, up, dep, t, margin, r, rz=None, nu=44, nv=10, along=0.0):
    """elliptic torus hugging the sleeve at parameter t of the elbow->hand segment; returns (mesh, centre, semi_up, semi_dep)"""
    c = e + t * (h - e)
    centre, bu, bd, _ = section(S, c, up, dep)
    Rm = np.stack([up, np.cross(ax, up), ax], axis=1)          # right-handed frame: x along the dorsal direction (semi-axis bu), y along the depth (bd), z = arm axis
    mesh = mg.elliptic_torus(bu + margin, bd + margin, r, nu=nu, nv=nv, rz=rz).transform(R=Rm, t=centre + ax * along)
    return mesh, centre, bu, bd


def merge(meshes):
    m = mg.Mesh()
    for x in meshes:
        m.add(x)
    return m


# ------------------------------------------------------------------------------------------------------------------------------ the build
def build_tech(te, drig_unused=None):
    """te: TechExpert scene; returns (list[Acc], list[Sprite])"""
    acc, spr = [], []
    rig = te.rig
    tr = te.body_triangles()
    pos, slot = tr['pos'], tr['slot'] + 1
    S_all = Surface(pos)
    S_helm = Surface(pos[slot == 5])
    S_pack = Surface(pos[np.isin(slot, (6, 7, 8, 9))])
    S_vest = Surface(pos[slot == 19])
    S_head = Surface(te.head_triangles()['pos'])

    # ---------------------------------------------------------------- cyber glasses on the (swapped) Female_04 face
    acc += cyber_glasses(S_head, dz=66.58 - 65.15)

    # ---------------------------------------------------------------- headlamp on the front of the hard hat
    p, n = S_helm.front(0.0, 71.0)
    axis = n + np.array([0.55, 0, 0])
    axis /= np.linalg.norm(axis)
    R = frame_z(axis)
    base = p - axis * 0.2
    housing = mg.cylinder(0.98, 1.7, sides=28).transform(R=R, t=base + axis * 0.85)
    collar = mg.cylinder(1.12, 0.32, sides=28).transform(R=R, t=base + axis * 0.2)
    lens = merge([mg.cylinder(0.74, 0.12, sides=28).transform(R=R, t=base + axis * 1.72),
                  mg.torus(0.93, 0.085, nu=36, nv=8).transform(R=R, t=base + axis * 1.7)])
    acc.append(Acc('lamp_body', merge([housing, collar]), SP + 'Head1', color=INDIGO, note='headlamp housing'))
    acc.append(Acc('lamp_lens', lens, SP + 'Head1', color=PINK, nolight=True, note='headlamp lens'))
    spr.append(Sprite('lamp_glow', SP + 'Head1', base + axis * 2.05, PINK, 3.6, 0.5))

    # ---------------------------------------------------------------- ID badge clipped to the vest (right chest)
    p, n = S_vest.front(-3.4, 53.9)
    Rb = _basis(n)
    card = mg.card(2.5, 3.5, 0.17, rc=0.3).transform(R=Rb, t=p + n * 0.38)
    clip = mg.card(1.3, 0.55, 0.2, rc=0.16).transform(R=Rb, t=p + n * 0.38 + Rb[:, 1] * 1.78)
    tex = badge_texture(title='TECHNICAL SERVICES', role='TECH EXPERT', level='LVL 3', seed=23)
    acc.append(Acc('id_badge', card, SP + 'Spine4', material='texture', texture=tex, color=(255, 255, 255), note='ID badge'))
    acc.append(Acc('id_clip', clip, SP + 'Spine4', color=INDIGO, note='badge clip'))

    # ---------------------------------------------------------------- left forearm: datapad on two straps
    e, h, ax, up, dep = arm_frame(rig, 'L')
    straps = []
    for t in (0.30, 0.63):
        m, c, bu, bd = ring_on_arm(S_all, e, h, ax, up, dep, t, margin=0.14, r=0.23, rz=0.42)
        straps.append(m)
    c_mid = e + 0.465 * (h - e)
    centre, bu, bd, ext_up = section(S_all, c_mid, up, dep)
    u0 = ext_up                                                     # top of the sleeve above the bone line
    pad_c = c_mid + up * (u0 + 0.66)
    Rp = frame_yz(-ax, up)                                          # screen up = towards the elbow, front = dorsal
    body = mg.card(3.5, 5.3, 0.5, rc=0.55).transform(R=Rp, t=pad_c)
    screen = mg.card(3.0, 4.8, 0.06, rc=0.4).transform(R=Rp, t=pad_c + up * 0.27)
    acc.append(Acc('pad_straps', merge(straps), SP + 'L_Forearm', color=INDIGO, note='datapad straps'))
    acc.append(Acc('pad_body', body, SP + 'L_Forearm', color=NAVY, note='datapad'))
    acc.append(Acc('pad_screen', screen, SP + 'L_Forearm', material='texture', texture=datapad_texture(), color=(255, 255, 255), nolight=True, note='datapad screen'))
    spr.append(Sprite('pad_glow', SP + 'L_Forearm', pad_c + up * 0.9, PINK, 3.2, 0.35))

    # ---------------------------------------------------------------- wrist bands (INDIGO) + neon rings (PINK) on both forearms, at the cuff
    for sgn, side in ((+1, 'L'), (-1, 'R')):
        e, h, ax, up, dep = arm_frame(rig, side)
        band, c, bu, bd = ring_on_arm(S_all, e, h, ax, up, dep, 0.83, margin=0.14, r=0.27, rz=0.5)
        neon, c2, _, _ = ring_on_arm(S_all, e, h, ax, up, dep, 0.83, margin=0.16, r=0.1, rz=0.1, along=0.58)
        acc.append(Acc('wrist_band_%s' % side.lower(), band, SP + '%s_Forearm' % side, color=INDIGO, note='wristband'))
        acc.append(Acc('wrist_neon_%s' % side.lower(), neon, SP + '%s_Forearm' % side, color=PINK, nolight=True, note='neon ring'))
        spr.append(Sprite('wrist_glow_%s' % side.lower(), SP + '%s_Forearm' % side, c2 + up * (bu + 0.5) + ax * 0.58, PINK, 2.8, 0.6))

    # ---------------------------------------------------------------- backpack: patch, LED strips, antenna
    p, n = S_pack.back(0.0, 56.5)
    Rq = _basis(n)
    patch = mg.card(3.7, 3.7, 0.14, rc=0.55).transform(R=Rq, t=p + n * 0.1)
    acc.append(Acc('pack_patch', patch, SP + 'Spine4', material='texture', texture=back_patch_texture(), color=(255, 255, 255), note='backpack patch'))
    strips = []
    for y0 in (-3.9, 3.9):
        pts, nrm = [], []
        for z in np.linspace(43.5, 53.5, 12):
            best = None
            for dy in (-0.4, 0.0, 0.4):
                hit = S_pack.back(y0 + dy, z)
                if hit is not None and (best is None or hit[0][0] < best[0][0]):
                    best = hit
            pts.append(best[0] + np.array([-0.22, 0, 0]))
            nrm.append(best[1])
        pts = np.array(pts)
        fit = np.polyval(np.polyfit(pts[:, 2], pts[:, 0], 2), pts[:, 2])             # a clean rail: smooth curve pushed out far enough to clear every bump
        pts[:, 0] = fit + min(0.0, float((pts[:, 0] - fit).min()))
        pts = smooth_path(pts, 40)
        strips.append(mg.ribbon(pts, 0.5, up=np.array([-1.0, 0, 0])))
        spr.append(Sprite('pack_glow_%s' % ('l' if y0 > 0 else 'r'), SP + 'Spine4', pts[len(pts) // 2] + np.array([-0.5, 0, 0]), PINK, 4.5, 0.55))
    acc.append(Acc('pack_leds', merge(strips), SP + 'Spine4', color=PINK, nolight=True, nocull=True, note='backpack LED strips'))
    # antenna on the top-right corner of the pack (character's right = -y)
    top = S_pack.cast((-9.0, -5.2, 90.0), (0, 0, -1))
    foot = top[1] + np.array([0, 0, -0.15])
    tip = foot + np.array([-1.5, -1.2, 13.0])
    path = np.array([foot + (tip - foot) * k + np.array([-0.5, -0.2, 0]) * np.sin(np.pi * k) * 1.0 for k in np.linspace(0, 1, 14)])
    radius = np.linspace(0.17, 0.08, len(path))
    stick = mg.tube(path, radius, sides=12)
    mount = mg.cylinder(0.62, 0.5, sides=20).transform(t=foot + np.array([0, 0, 0.05]))
    ball = mg.ellipsoid((0.42, 0.42, 0.42), nu=20, nv=12).transform(t=path[-1] + np.array([0, 0, 0.3]))
    acc.append(Acc('antenna', merge([stick, mount]), SP + 'Spine4', color=NAVY, note='antenna'))
    acc.append(Acc('antenna_tip', ball, SP + 'Spine4', color=PINK, nolight=True, note='antenna beacon'))
    spr.append(Sprite('antenna_glow', SP + 'Spine4', path[-1] + np.array([0, 0, 0.3]), PINK, 3.4, 0.7))
    return acc, spr
