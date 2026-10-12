"""The three accessory sets (own geometry + textures) for the BNA Ethics Assistant outfits. Each build_* returns (list[Acc], list[Sprite])."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import meshgen as mg
from meshgen import Mesh, Rx, Ry, Rz
from ethics_acc import Acc, Surface, smooth_path, rounded_rect_path
from ethics_common import PINK, MAGENTA, INDIGO, ROYAL, NAVY
import ethics_paint as ep

FONT_BOLD = r'C:\Windows\Fonts\arialbd.ttf'
FONT_REG = r'C:\Windows\Fonts\arial.ttf'


class Sprite:
    """additive glow billboard attached to a bone at a world position"""
    def __init__(self, name, bone, pos_world, color, size, alpha=1.0):
        self.name, self.bone, self.pos, self.color, self.size, self.alpha = name, bone, np.asarray(pos_world, float), color, size, alpha


# ------------------------------------------------------------------------------------------------------------------------------ textures for accessories
def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def badge_texture(w=800, h=1120, title='ETHICS COMMITTEE', role='ASSISTANT', level='LVL 3', seed=11):
    """ID card: NAVY card, PINK header, emblem, name block and a five-colour BNA strip"""
    img = Image.new('RGB', (w, h), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, int(h * 0.17)], fill=PINK)
    f1 = _font(FONT_BOLD, int(h * 0.058))
    d.text((w / 2, h * 0.085), title, font=f1, fill=(255, 255, 255), anchor='mm')
    # emblem
    em = ep.emblem_image(int(w * 0.62), PINK)
    em8 = Image.fromarray((em * 255).astype(np.uint8), 'RGBA')
    img.paste(em8, (int(w * 0.19), int(h * 0.22)), em8)
    # name block
    d.rounded_rectangle([int(w * 0.08), int(h * 0.67), int(w * 0.92), int(h * 0.79)], radius=int(w * 0.03), fill=ROYAL)
    f2 = _font(FONT_BOLD, int(h * 0.066))
    d.text((w / 2, h * 0.73), role, font=f2, fill=(255, 255, 255), anchor='mm')
    f3 = _font(FONT_REG, int(h * 0.036))
    d.text((w * 0.1, h * 0.835), 'CLEARANCE', font=f3, fill=INDIGO, anchor='lm')
    d.text((w * 0.9, h * 0.835), level, font=_font(FONT_BOLD, int(h * 0.04)), fill=MAGENTA, anchor='rm')
    # barcode
    rs = np.random.RandomState(seed)
    x = int(w * 0.1)
    while x < int(w * 0.9):
        bw = int(rs.choice([4, 6, 9, 13]))
        if x + bw > w * 0.9:
            break
        d.rectangle([x, int(h * 0.87), x + bw, int(h * 0.915)], fill=(235, 235, 245))
        x += bw + int(rs.choice([4, 7, 10]))
    # BNA palette strip along the bottom
    cols = [PINK, MAGENTA, INDIGO, ROYAL]
    sw = w / 4
    for i, c in enumerate(cols):
        d.rectangle([int(i * sw), int(h * 0.94), int((i + 1) * sw), h], fill=c)
    return np.asarray(img)


def pin_texture(size=256):
    img = Image.new('RGB', (size, size), PINK)
    d = ImageDraw.Draw(img)
    d.ellipse([size * 0.06, size * 0.06, size * 0.94, size * 0.94], fill=ROYAL)
    em = ep.emblem_image(int(size * 0.72), (255, 255, 255))
    em8 = Image.fromarray((em * 255).astype(np.uint8), 'RGBA')
    img.paste(em8, (int(size * 0.14), int(size * 0.14)), em8)
    return np.asarray(img)


# ------------------------------------------------------------------------------------------------------------------------------ helpers
def _basis(front, up_hint=(0, 0, 1.0)):
    """rotation whose columns are (width axis, up axis, front axis) for a flat item facing `front` (card local: x width, y up, z front)"""
    z = np.asarray(front, float)
    z = z / np.linalg.norm(z)
    up = np.asarray(up_hint, float)
    x = np.cross(up, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0, 1.0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def hair_bow(S, color, z=63.6, size=1.0):
    """a bow behind the head at the base of the ponytail, facing backwards"""
    hit = S.back(0.0, z)
    p = hit[0] + np.array([-0.25, 0, 0])
    bow = mg.bow(width=3.3 * size, height=1.7 * size, depth=0.9 * size, knot=0.55 * size)
    # local: x width, y depth, z height -> world: x width -> +y, y depth -> -x (pointing back), z -> z
    R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.0]])
    return Acc('hair_bow', bow.transform(R=R, t=p), 'ValveBiped.Bip01_Head1', color=color)


def collar_bow(S_suit, color, z=57.6, size=1.0):
    hit = S_suit.front(0.0, z)
    p = hit[0] + np.array([0.45, 0, 0.0])
    bow = mg.bow(width=3.6 * size, height=1.9 * size, depth=1.0 * size, knot=0.62 * size)
    # front-facing: local y (depth) -> +x, local x (width) -> -y?  (viewer's right = +y when facing the character; width symmetric so either)
    R = np.array([[0, 1, 0], [0, 0, 1.0], [0, 0, 0]])
    R = np.array([[0, 1.0, 0], [-1.0, 0, 0], [0, 0, 1.0]])    # local x -> world -y, local y -> world +x, local z -> z
    return Acc('collar_bow', bow.transform(R=R, t=p), 'ValveBiped.Bip01_Spine4', color=color)


# ------------------------------------------------------------------------------------------------------------------------------ Style 1: formal
def lanyard(S_suit, badge_top, z_ring=60.4, width=0.5):
    """a closed ribbon loop: from the badge clip up the left strap, around the collar (hugging the surface), down the right strap and back"""
    centre = np.array([-1.6, 0.0])
    ring = []
    for ang in np.linspace(38, 322, 31):
        h = S_suit.radial(centre, z_ring, ang)
        a = np.radians(ang)
        fallback = np.array([centre[0] + 2.5 * np.cos(a), centre[1] + 2.5 * np.sin(a), z_ring])
        p = (h[0] + h[1] * 0.2) if h is not None else fallback
        r = np.hypot(p[0] - centre[0], p[1] - centre[1])
        if r < 2.2 or r > 4.0:                              # a stray hit (shoulder, hair): use the ellipse instead
            p = fallback
        ring.append(p)
    ring = np.array(ring)
    straps = []
    for end in (ring[0], ring[-1]):
        pts = []
        for t in np.linspace(0.0, 1.0, 9):
            z = end[2] + (badge_top[2] - end[2]) * t
            y = end[1] + (badge_top[1] - end[1]) * t
            h = S_suit.front(y, z)
            pts.append((h[0] + h[1] * 0.2) if h is not None else np.array([end[0] + (badge_top[0] - end[0]) * t, y, z]))
        straps.append(np.array(pts))
    loop = np.vstack([straps[0][::-1], ring, straps[1]])               # clip -> left strap up (ring[0] is the front-left end) ...
    # order: start at the clip, climb the strap that ends at ring[0], run the ring 38..322 degrees, descend the strap that starts at ring[-1]
    loop = np.vstack([badge_top[None], straps[0][::-1][1:], ring[1:-1], straps[1][1:], badge_top[None]])
    loop = smooth_path(loop, 110)
    nrm = []
    for p in loop:
        o = p + (np.array([6.0, 0, 0]) if p[0] > -1.6 else np.array([-6.0, 0, 0]))
        d = np.array([-1.0, 0, 0]) if p[0] > -1.6 else np.array([1.0, 0, 0])
        h = S_suit.cast(o, d)
        nrm.append(h[2] if h is not None else np.array([1.0, 0, 0]))
    return mg.ribbon(loop, width, up=np.array(nrm))


def build_formal(body, S, S_suit):
    acc, spr = [], []
    # --- ID badge on the chest (rigid with the lanyard: both ride the spine 4 bone)
    zc = 49.3
    hit = S.front(0.0, zc)
    pc = hit[0] + np.array([0.42, 0, 0])
    card = mg.card(2.5, 3.5, 0.17, rc=0.3)
    R = np.array([[0, 0, 1.0], [1.0, 0, 0], [0, 1.0, 0]])         # local x -> world y, local y -> world z, local z (front) -> world x
    acc.append(Acc('id_badge', card.transform(R=R, t=pc), 'ValveBiped.Bip01_Spine4', material='texture', texture=badge_texture(), color=(255, 255, 255), note='ID badge'))
    acc.append(Acc('lanyard', lanyard(S_suit, pc + np.array([-0.2, 0, 1.78])), 'ValveBiped.Bip01_Spine4', color=MAGENTA, nocull=True, note='lanyard'))
    acc += glasses_round(S, color=INDIGO, name='glasses')
    # --- lapel pin on the left lapel
    h = S_suit.front(3.15, 52.4)
    n = h[1]
    pin = mg.card(1.05, 1.05, 0.13, rc=0.5)
    acc.append(Acc('lapel_pin', pin.transform(R=_basis(n), t=h[0] + n * 0.1), 'ValveBiped.Bip01_Spine4', material='texture', texture=pin_texture(), color=(255, 255, 255), note='lapel pin'))
    acc.append(hair_bow(S, PINK, size=0.95))
    return acc, spr


def glasses_round(S, color, name='glasses', rim_r=1.05, tube_r=0.09, x_front=4.72, y_c=1.38, z_c=65.05, yaw=11.0):
    """two round rims, a bridge and two temples that follow the head"""
    parts = []
    rim_local = mg.torus(rim_r, tube_r, nu=40, nv=10)            # ring around z; we want it around x -> rotate
    for sgn in (+1, -1):
        m = rim_local.transform(R=Ry(90))                          # axis z -> x
        m = m.transform(R=Rz(-sgn * yaw))                          # wrap slightly around the face
        m = m.transform(t=(x_front, sgn * y_c, z_c))
        parts.append(m)
    bridge = mg.tube(np.array([[x_front - 0.2, -0.32, z_c + 0.22], [x_front + 0.05, 0.0, z_c + 0.4], [x_front - 0.2, 0.32, z_c + 0.22]]), 0.07, sides=8)
    parts.append(bridge)
    for sgn in (+1, -1):
        pts = []
        for x in (4.45, 3.4, 2.4, 1.4, 0.4, -0.5):
            h = S.side(x, z_c - 0.1, sgn)
            yy = (abs(h[0][1]) + 0.2) if h is not None else 3.2
            if x > 4.0:
                yy = rim_r * np.cos(np.radians(yaw)) + y_c + 0.05
            pts.append([x, sgn * yy, z_c + 0.12])
        pts = smooth_path(np.array(pts), 24)
        parts.append(mg.tube(pts, 0.07, sides=8))
    mesh = parts[0]
    for p in parts[1:]:
        mesh = mesh.add(p) or mesh
    return [Acc(name, mesh, 'ValveBiped.Bip01_Head1', color=color, note='round glasses')]


# ------------------------------------------------------------------------------------------------------------------------------ Style 2: anima (tanuki ears, no tail)
def build_anima(body, S, S_suit):
    acc, spr = [], []
    # --- ears: outer shell (INDIGO), inner cup (PINK), tip cap (NAVY); both ears merged per colour
    outer, inner, tip = Mesh(), Mesh(), Mesh()
    for sgn in (+1, -1):
        base = np.array([-0.35, sgn * 2.5, 68.4])
        Rt = Rz(0) @ Rx(-sgn * 24.0) @ Ry(-9.0)
        o = mg.ellipsoid((0.55, 1.35, 2.05), nu=28, nv=16, taper=lambda w: 1.0 - 0.36 * w).transform(t=(0, 0, 1.75))
        i = mg.ellipsoid((0.32, 0.9, 1.5), nu=24, nv=14, taper=lambda w: 1.0 - 0.36 * w).transform(t=(0.34, 0, 1.55))
        t = mg.ellipsoid((0.46, 0.62, 0.62), nu=16, nv=10).transform(t=(0.0, 0, 3.55))
        for m, acc_m in ((o, outer), (i, inner), (t, tip)):
            acc_m.add(m.transform(R=Rt, t=base))
    acc.append(Acc('ears_outer', outer, 'ValveBiped.Bip01_Head1', color=INDIGO, note='tanuki ears'))
    acc.append(Acc('ears_inner', inner, 'ValveBiped.Bip01_Head1', color=PINK, note='ear inner'))
    acc.append(Acc('ears_tip', tip, 'ValveBiped.Bip01_Head1', color=NAVY, note='ear tips'))
    for sgn in (+1, -1):
        base = np.array([-0.35, sgn * 2.5, 68.4])
        Rt = Rx(-sgn * 24.0) @ Ry(-9.0)
        spr.append(Sprite('ear_glow_%s' % ('l' if sgn > 0 else 'r'), 'ValveBiped.Bip01_Head1', base + Rt @ np.array([0.3, 0, 3.7]), PINK, 3.2, 0.55))
    # --- bows
    acc.append(collar_bow(S_suit, PINK))
    acc.append(hair_bow(S, MAGENTA, size=0.9))
    return acc, spr


# ------------------------------------------------------------------------------------------------------------------------------ Style 3: neon
def headphones(S):
    acc, spr = [], []
    # band: an ellipse arc over the head (y semi-axis 4.5, z semi-axis 6.0 about z=64.6), x = -0.45
    ph = np.radians(np.linspace(-88, 88, 40))
    zc = 64.55
    band_pts = np.column_stack([np.full(len(ph), -0.45), 4.5 * np.sin(ph), zc + 6.15 * np.cos(ph)])
    band = mg.tube(band_pts, 0.33, sides=12, scale_nb=(1.0, 1.0))
    acc.append(Acc('hp_band', band, 'ValveBiped.Bip01_Head1', color=ROYAL, note='headphone band'))
    cups, rings = Mesh(), Mesh()
    for sgn in (+1, -1):
        c = np.array([-0.45, sgn * 4.55, zc])
        cyl = mg.cylinder(1.75, 1.15, sides=28).transform(R=Rx(90))               # axis z -> y
        cups.add(cyl.transform(t=c))
        ring = mg.torus(1.35, 0.15, nu=36, nv=8).transform(R=Rx(90)).transform(t=c + np.array([0, sgn * 0.62, 0]))
        rings.add(ring)
        spr.append(Sprite('hp_glow_%s' % ('l' if sgn > 0 else 'r'), 'ValveBiped.Bip01_Head1', c + np.array([0, sgn * 0.75, 0]), PINK, 5.2, 0.75))
    acc.append(Acc('hp_cups', cups, 'ValveBiped.Bip01_Head1', color=NAVY, note='headphone cups'))
    acc.append(Acc('hp_rings', rings, 'ValveBiped.Bip01_Head1', color=PINK, nolight=True, note='glowing rings'))
    return acc, spr


def cyber_glasses(S, dz=0.0):
    """angular frames in glowing PINK with ROYAL tinted lenses (dz: height offset for a head whose bone sits higher than the femsuit's)"""
    frames, lenses = Mesh(), Mesh()
    zc, xf, yc, w, h = 65.15 + dz, 4.8, 1.45, 2.55, 1.55
    for sgn in (+1, -1):
        path = rounded_rect_path(w, h, 0.5, seg=7, centre=(0, sgn * yc, zc))
        path = path.copy()
        path[:, 0] = xf - 0.18 * np.abs(path[:, 1] - sgn * yc)                      # wrap a little
        ring = mg.tube(path, 0.1, sides=8, cap_start=False, cap_end=False)
        frames.add(ring)
        lens_o = mg.rounded_rect(w - 0.2, h - 0.2, 0.42, 7)
        V = np.vstack([[0, 0, 0], np.column_stack([np.zeros(len(lens_o)), lens_o[:, 0], lens_o[:, 1]])])
        V = V + np.array([xf, sgn * yc, zc])
        V[:, 0] = xf - 0.18 * np.abs(V[:, 1] - sgn * yc)
        F = np.array([[0, 1 + i, 1 + (i + 1) % len(lens_o)] for i in range(len(lens_o))])
        lens = Mesh(V, np.zeros((len(V), 2)), F)
        lenses.add(lens)
    frames.add(mg.tube(np.array([[xf - 0.1, -0.2, zc + 0.4], [xf + 0.12, 0, zc + 0.5], [xf - 0.1, 0.2, zc + 0.4]]), 0.09, sides=8))
    for sgn in (+1, -1):
        pts = []
        for x in (4.3, 3.4, 2.4, 1.4, 0.4, -0.5):
            hh = S.side(x, zc, sgn)
            yy = (abs(hh[0][1]) + 0.2) if hh is not None else 3.2
            if x > 4.0:
                yy = yc + w / 2 + 0.05
            pts.append([x, sgn * yy, zc + 0.12])
        frames.add(mg.tube(smooth_path(np.array(pts), 22), 0.085, sides=8))
    return [Acc('cyber_frames', frames, 'ValveBiped.Bip01_Head1', color=PINK, nolight=True, note='cyber frames'),
            Acc('cyber_lenses', lenses, 'ValveBiped.Bip01_Head1', color=ROYAL, alpha=0.34, translucent=True, nocull=True, nolight=True, note='lenses')]


def wristbands(S):
    acc, spr = [], []
    for sgn, side in ((+1, 'L'), (-1, 'R')):
        e = np.array([-2.1, sgn * 11.7, 48.6])
        h = np.array([-1.3, sgn * 17.7, 39.2])
        ax = (h - e) / np.linalg.norm(h - e)
        c = e + 0.885 * (h - e)
        band = mg.torus(2.02, 0.27, nu=40, nv=10, rz=0.5)                       # ring around z
        Rb = mg.basis_from_x(np.cross(ax, [1.0, 0, 0]), up_hint=ax)               # make local z the arm axis
        R = np.stack([np.cross(ax, np.array([1.0, 0, 0])) / np.linalg.norm(np.cross(ax, np.array([1.0, 0, 0]))), np.cross(ax, np.cross(ax, np.array([1.0, 0, 0]))) / np.linalg.norm(np.cross(ax, np.cross(ax, np.array([1.0, 0, 0])))), ax], axis=1)
        mw = band.transform(R=R, t=c)
        acc.append(Acc('wrist_%s' % side.lower(), mw, 'ValveBiped.Bip01_%s_Forearm' % side, color=INDIGO, note='wristband'))
        spr.append(Sprite('wrist_glow_%s' % side.lower(), 'ValveBiped.Bip01_%s_Forearm' % side, c + R @ np.array([2.0, 0, 0]), PINK, 3.0, 0.7))
    return acc, spr


def build_neon(body, S, S_suit):
    acc, spr = [], []
    a, s = headphones(S)
    acc += a; spr += s
    acc += cyber_glasses(S)
    a, s = wristbands(S)
    acc += a; spr += s
    return acc, spr
