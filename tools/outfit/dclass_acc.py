"""BNA accessories for the D-class (class_d_mike, low-sec gray uniform) outfit. Built on the real body surface, in the in-game bind pose."""
import numpy as np
from PIL import Image, ImageDraw

import meshgen as mg
from meshgen import Mesh, Rx, Ry, Rz
from ethics_acc import Acc
from ethics_common import INDIGO, MAGENTA, NAVY, PINK, ROYAL
from ethics_styles import FONT_BOLD, FONT_REG, Sprite, _basis, _font, hair_bow
import ethics_paint as ep


def id_card_texture(w=800, h=1120):
    """D-class ID card in the BNA palette (NAVY card, PINK header, name block, barcode, palette strip)"""
    img = Image.new('RGB', (w, h), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, int(h * 0.19)], fill=PINK)
    d.text((w / 2, h * 0.095), 'CLASS-D', font=_font(FONT_BOLD, int(h * 0.085)), fill=(255, 255, 255), anchor='mm')
    em = ep.emblem_image(int(w * 0.5), PINK)
    em8 = Image.fromarray((em * 255).astype(np.uint8), 'RGBA')
    img.paste(em8, (int(w * 0.25), int(h * 0.24)), em8)
    d.rounded_rectangle([int(w * 0.08), int(h * 0.62), int(w * 0.92), int(h * 0.74)], radius=int(w * 0.03), fill=ROYAL)
    d.text((w / 2, h * 0.68), 'D-8294', font=_font(FONT_BOLD, int(h * 0.075)), fill=(255, 255, 255), anchor='mm')
    d.text((w * 0.1, h * 0.79), 'LOW SECURITY', font=_font(FONT_BOLD, int(h * 0.04)), fill=INDIGO, anchor='lm')
    d.text((w * 0.9, h * 0.79), 'TRUSTEE', font=_font(FONT_BOLD, int(h * 0.04)), fill=MAGENTA, anchor='rm')
    rs = np.random.RandomState(8)
    x = int(w * 0.1)
    while x < int(w * 0.9):
        bw = int(rs.choice([4, 6, 9, 13]))
        if x + bw > w * 0.9:
            break
        d.rectangle([x, int(h * 0.84), x + bw, int(h * 0.915)], fill=(235, 235, 245))
        x += bw + int(rs.choice([4, 7, 10]))
    cols = [PINK, MAGENTA, INDIGO, ROYAL]
    sw = w / 4
    for i, c in enumerate(cols):
        d.rectangle([int(i * sw), int(h * 0.94), int((i + 1) * sw), h], fill=c)
    return np.asarray(img)


def buckle_texture(size=256):
    img = Image.new('RGB', (size, size), NAVY)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([size * 0.04, size * 0.04, size * 0.96, size * 0.96], radius=int(size * 0.14), outline=PINK, width=int(size * 0.045))
    em = ep.emblem_image(int(size * 0.66), PINK)
    em8 = Image.fromarray((em * 255).astype(np.uint8), 'RGBA')
    img.paste(em8, (int(size * 0.17), int(size * 0.17)), em8)
    return np.asarray(img)


def axis_frame(ax):
    """rotation whose third column is the (unit) arm axis; first two columns are arbitrary perpendicular directions"""
    ax = np.asarray(ax, float) / np.linalg.norm(ax)
    ref = np.array([1.0, 0, 0]) if abs(ax @ np.array([1.0, 0, 0])) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(ax, ref)
    u /= np.linalg.norm(u)
    v = np.cross(ax, u)
    return np.stack([u, v, ax], axis=1)


def section_radius(S, c, axis, rmax=8.0, n=24):
    """max distance from the axis to the surface (outermost) around a cross-section"""
    R = axis_frame(axis)
    rs = []
    for a in np.linspace(0, 2 * np.pi, n, endpoint=False):
        dd = np.cos(a) * R[:, 0] + np.sin(a) * R[:, 1]
        r = S.cast(c + dd * rmax, -dd)
        if r:
            rs.append(rmax - r[0])
    return np.array(rs)


def build_dclass(d, S):
    acc, spr = [], []
    rig = d.rig
    SP = 'ValveBiped.Bip01_'
    # ------------------------------------------------------------ ID card clipped to the right chest pocket
    h = S.front(-3.3, 49.6)
    pc = h[0] + np.array([0.38, 0, 0])
    card = mg.card(2.3, 3.2, 0.14, rc=0.28)
    R = np.array([[0, 0, 1.0], [1.0, 0, 0], [0, 1.0, 0]])
    card_w = card.transform(R=R, t=pc)
    clip = mg.card(1.3, 0.55, 0.2, rc=0.16).transform(R=R, t=pc + np.array([0.0, 0, 1.75]))
    acc.append(Acc('id_card', card_w, SP + 'Spine4', material='texture', texture=id_card_texture(), color=(255, 255, 255), note='ID card'))
    acc.append(Acc('id_clip', clip, SP + 'Spine4', color=INDIGO, note='card clip'))
    # ------------------------------------------------------------ wristbands (INDIGO band + PINK neon ring) on both forearms
    for sgn, side in ((+1, 'L'), (-1, 'R')):
        e = rig.world[rig.bone('%s_Forearm' % side)][:3, 3]
        hnd = rig.world[rig.bone('%s_Hand' % side)][:3, 3]
        ax = hnd - e
        c = e + 0.9 * ax
        rr = section_radius(S, c, ax)
        Rr = max(2.55, float(rr.max()) + 0.38) if len(rr) else 2.6
        Rm = axis_frame(ax)
        band = mg.torus(Rr, 0.3, nu=40, nv=10, rz=0.55).transform(R=Rm, t=c)
        ring = mg.torus(Rr + 0.02, 0.1, nu=40, nv=8).transform(R=Rm, t=c + ax / np.linalg.norm(ax) * 0.62)
        acc.append(Acc('wrist_band_%s' % side.lower(), band, SP + '%s_Forearm' % side, color=INDIGO, note='wristband'))
        acc.append(Acc('wrist_neon_%s' % side.lower(), ring, SP + '%s_Forearm' % side, color=PINK, nolight=True, note='neon ring'))
    # ------------------------------------------------------------ ankle monitors (ROYAL band, PINK LED) above the boots
    for sgn, side in ((+1, 'L'), (-1, 'R')):
        f = rig.world[rig.bone('%s_Foot' % side)][:3, 3]
        cen = np.array([-1.25, sgn * 6.1, 8.0])
        Rr = 3.15
        band = mg.torus(Rr, 0.32, nu=44, nv=10, rz=0.62).transform(t=cen)
        led = mg.card(1.2, 0.8, 0.42, rc=0.18).transform(R=np.array([[0, 0, 1.0], [1.0, 0, 0], [0, 1.0, 0]]), t=cen + np.array([Rr + 0.16, 0, 0]))
        acc.append(Acc('ankle_band_%s' % side.lower(), band, SP + '%s_Foot' % side, color=ROYAL, note='ankle monitor'))
        acc.append(Acc('ankle_led_%s' % side.lower(), led, SP + '%s_Foot' % side, color=PINK, nolight=True, note='monitor LED'))
        spr.append(Sprite('ankle_glow_%s' % side.lower(), SP + '%s_Foot' % side, cen + np.array([Rr + 0.45, 0, 0]), PINK, 2.6, 0.7))
    # ------------------------------------------------------------ belt buckle plate
    hb = S.front(0.0, 40.8)
    plate = mg.card(2.5, 1.7, 0.16, rc=0.3).transform(R=np.array([[0, 0, 1.0], [1.0, 0, 0], [0, 1.0, 0]]), t=hb[0] + np.array([0.2, 0, 0]))
    acc.append(Acc('belt_plate', plate, SP + 'Pelvis', material='texture', texture=buckle_texture(), color=(255, 255, 255), note='buckle plate'))
    # ------------------------------------------------------------ hair bow (head bone; the female head is the same shape as the femsuit head)
    acc.append(hair_bow(_FakeSurfaceForBow(), PINK, z=65.1, size=0.95))        # the D-class head bone sits 1.5 units higher than the femsuit's
    return acc, spr


class _FakeSurfaceForBow:
    """hair_bow() asks the surface for the back of the head; the D-class head is the same mesh in head-bone-local space, so use the femsuit head's values (x = -5.3 at z 63.6)"""

    def back(self, y, z):
        return np.array([-5.25, 0.0, z]), np.array([-1.0, 0, 0])
