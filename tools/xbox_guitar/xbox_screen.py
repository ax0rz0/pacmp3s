"""the TV screen of the Xbox pac: a boot animation and a home screen drawn from scratch (original art: a glowing orb, a light-X emblem and a tile dashboard), written as ONE animated VTF.

pac downloads a .vtf from a URL (resource.lua: a body starting with 'VTF' is stored as .vtf and its frame count is read from the header), a material_2d part shows it and a proxy steps its `frame`
property, so the whole animation costs a single URL texture.  512 x 256 DXT1 per frame (the 16:9 picture is squeezed to the power-of-two size; the screen quad is 16:9 so it comes out right).
"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W0, H0 = 1024, 576
TW, TH = 512, 256
GREEN = np.array([150.0, 232.0, 24.0])
FONTS = r'C:\Windows\Fonts'


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONTS, name), size)
    except OSError:
        return ImageFont.load_default()


def glow(cx, cy, r, color, power=2.0, gain=1.0, aspect=1.0):
    ys, xs = np.mgrid[0:H0, 0:W0].astype(np.float32)
    d = np.sqrt(((xs - cx) / aspect) ** 2 + (ys - cy) ** 2) / max(r, 1.0)
    a = np.clip(1.0 - d, 0.0, 1.0) ** power * gain
    return a[:, :, None] * np.asarray(color, np.float32)[None, None, :]


def orb(cx, cy, r, bright=1.0):
    """a glossy green sphere: soft halo, body gradient, specular blob"""
    img = glow(cx, cy, r * 1.9, GREEN * 0.55, power=2.6, gain=0.9 * bright)
    ys, xs = np.mgrid[0:H0, 0:W0].astype(np.float32)
    dx, dy = (xs - cx) / r, (ys - cy) / r
    rr = np.sqrt(dx * dx + dy * dy)
    inside = np.clip((1.0 - rr) * 12.0, 0.0, 1.0)
    z = np.sqrt(np.clip(1.0 - rr * rr, 0.0, 1.0))
    light = np.clip(0.35 + 0.65 * (-0.45 * dx - 0.55 * dy + 0.7 * z), 0.0, 1.0)
    body = (np.array([20.0, 90.0, 10.0])[None, None, :] * (1 - light[:, :, None]) + GREEN[None, None, :] * light[:, :, None]) * bright
    img = img * (1 - inside[:, :, None]) + body * inside[:, :, None] + img * inside[:, :, None] * 0.3
    spec = glow(cx - 0.35 * r, cy - 0.42 * r, r * 0.45, [255, 255, 235], power=2.2, gain=0.85 * bright)
    img += spec * inside[:, :, None]
    return img


def x_emblem(cx, cy, size, amount, color=(235, 255, 200)):
    """two crossing bars of light (a stylised X), amount 0..1 draws them in"""
    img = Image.new('L', (W0, H0), 0)
    d = ImageDraw.Draw(img)
    L = size * amount
    for sgn in (1, -1):
        d.line([(cx - sgn * L, cy - L), (cx + sgn * L, cy + L)], fill=255, width=int(size * 0.26))
    m = np.asarray(img, np.float32) / 255.0
    soft = np.asarray(img.filter(ImageFilter.GaussianBlur(size * 0.10)), np.float32) / 255.0
    base = np.asarray(color, np.float32)[None, None, :]
    return m[:, :, None] * base + soft[:, :, None] * GREEN[None, None, :] * 0.8


def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGB')


def rounded(d, box, r, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def dashboard(progress):
    """the home screen; progress 0..1 reveals background, bars and tiles"""
    img = Image.new('RGB', (W0, H0), (4, 12, 6))
    px = np.zeros((H0, W0, 3), np.float32)
    ys, xs = np.mgrid[0:H0, 0:W0].astype(np.float32)
    t = (xs / W0 * 0.55 + ys / H0 * 0.45)
    px[:, :, 0] = 6 + 8 * t
    px[:, :, 1] = 18 + 52 * t
    px[:, :, 2] = 8 + 22 * t
    px += glow(W0 * 0.8, H0 * 0.15, 520, GREEN * 0.35, power=2.0, gain=0.55)
    px += glow(W0 * 0.15, H0 * 1.05, 460, GREEN * 0.25, power=2.0, gain=0.5)
    a = min(1.0, progress * 2.0)
    base = (px * a).astype(np.uint8)
    img = Image.fromarray(base, 'RGB')
    d = ImageDraw.Draw(img, 'RGBA')
    f_big, f_mid, f_small = font('segoeuib.ttf', 40), font('seguisb.ttf', 26), font('segoeui.ttf', 20)
    if progress > 0.25:
        al = int(255 * min(1.0, (progress - 0.25) / 0.25))
        d.text((54, 34), 'Home', font=f_big, fill=(255, 255, 255, al))
        for i, name in enumerate(('Games', 'Media', 'Store', 'Settings')):
            d.text((200 + i * 130, 48), name, font=f_small, fill=(210, 230, 210, int(al * (1.0 if i else 0.6))))
        d.ellipse((780, 30, 836, 86), fill=(150, 232, 24, al), outline=(255, 255, 255, al), width=3)
        d.text((797, 40), 'E', font=f_mid, fill=(10, 40, 10, al))
        d.text((1000, 38), '12:34', font=f_small, fill=(255, 255, 255, al), anchor='ra')
        d.text((1000, 64), 'Ethics Assistant', font=font('segoeui.ttf', 16), fill=(200, 230, 200, al), anchor='ra')
    if progress > 0.5:
        al = int(255 * min(1.0, (progress - 0.5) / 0.3))
        rounded(d, (54, 120, 520, 440), 18, (30, 120, 30, al), (170, 255, 120, al), 3)
        d.rectangle((54, 330, 520, 440), fill=(8, 40, 10, int(al * 0.75)))
        d.text((80, 345), "Garry's Mod", font=f_big, fill=(255, 255, 255, al))
        d.text((82, 395), 'Continue playing', font=f_mid, fill=(180, 255, 140, al))
        d.polygon([(250, 205), (250, 285), (322, 245)], fill=(255, 255, 255, int(al * 0.9)))
    if progress > 0.7:
        al = int(255 * min(1.0, (progress - 0.7) / 0.3))
        names = ('Store', 'Media', 'Friends', 'Trophies', 'Settings', 'Network')
        cols = ((16, 124, 16), (40, 100, 190), (170, 70, 160), (200, 140, 20), (90, 100, 110), (30, 140, 150))
        k = 0
        for r in range(3):
            for c in range(2):
                x0, y0 = 548 + c * 214, 120 + r * 108
                rounded(d, (x0, y0, x0 + 200, y0 + 96), 12, cols[k] + (al,), (255, 255, 255, int(al * 0.5)), 2)
                d.text((x0 + 16, y0 + 56), names[k], font=f_small, fill=(255, 255, 255, al))
                d.ellipse((x0 + 16, y0 + 14, x0 + 48, y0 + 46), fill=(255, 255, 255, int(al * 0.85)))
                k += 1
    if progress > 0.9:
        al = 255
        y = 514
        for i, (lab, col) in enumerate((('Select', (60, 200, 60)), ('Back', (220, 60, 60)), ('Menu', (80, 120, 230)), ('Search', (230, 190, 40)))):
            x = 60 + i * 150
            d.ellipse((x, y, x + 30, y + 30), fill=col + (al,))
            d.text((x + 40, y + 2), lab, font=f_small, fill=(230, 240, 230, al))
    return np.asarray(img, np.float32)


def boot_frames():
    cx, cy = W0 / 2, H0 / 2
    black = np.zeros((H0, W0, 3), np.float32)
    F = []
    F.append(black)                                                                             # 0 TV on, nothing yet
    F.append(glow(cx, cy, 26, GREEN, 1.6, 0.8))                                                 # 1 a dim speck
    F.append(glow(cx, cy, 90, GREEN, 2.2, 0.8))                                                 # 2 soft glow
    F.append(orb(cx, cy, 52, 0.7))                                                              # 3 a small orb
    F.append(orb(cx, cy, 104, 0.85))                                                            # 4
    F.append(orb(cx, cy, 168, 1.0))                                                             # 5
    F.append(orb(cx, cy, 214, 1.0) + glow(cx, cy, 340, [255, 255, 255], 3.5, 0.5))              # 6 full orb, bright flare
    f7 = orb(cx, cy, 214, 0.75) + x_emblem(cx, cy, 150, 0.35)                                  # 7 the X starts to cut through
    F.append(f7)
    f8 = orb(cx, cy, 214, 0.55) + x_emblem(cx, cy, 150, 0.8)                                   # 8
    F.append(f8)
    f9 = glow(cx, cy, 380, GREEN * 0.6, 2.0, 0.7) + x_emblem(cx, cy, 150, 1.0) * 1.0           # 9 the emblem, orb gone
    img = to_img(f9)
    d = ImageDraw.Draw(img)
    f = font('ariblk.ttf', 64)
    wm = 'XBOX'
    tw = d.textlength(wm, font=f)
    d.text(((W0 - tw) / 2, cy + 170), wm, font=f, fill=(220, 245, 190))
    F.append(np.asarray(img, np.float32))
    F.append(F[-1] * 1.0 + glow(cx, cy, 460, GREEN, 2.4, 0.35))                                # 10 the pulse
    F.append(F[-2] * 0.45)                                                                      # 11 fade
    F.append(dashboard(0.3))                                                                    # 12
    F.append(dashboard(0.6))                                                                    # 13
    F.append(dashboard(0.85))                                                                   # 14
    F.append(dashboard(1.0))                                                                    # 15 the home screen, held
    return F


# ----------------------------------------------------------------------------------------------------------------------------- DXT1 + VTF
def dxt1(img):
    H, W, _ = img.shape
    bx, by = W // 4, H // 4
    blocks = img.reshape(by, 4, bx, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3).astype(np.float32)
    mn, mx = blocks.min(axis=1), blocks.max(axis=1)
    inset = (mx - mn) / 16.0
    c0f, c1f = mx - inset, mn + inset

    def q565(c):
        r = np.clip(np.round(c[:, 0] / 255 * 31), 0, 31).astype(np.uint32)
        g = np.clip(np.round(c[:, 1] / 255 * 63), 0, 63).astype(np.uint32)
        b = np.clip(np.round(c[:, 2] / 255 * 31), 0, 31).astype(np.uint32)
        return (r << 11) | (g << 5) | b

    def d565(p):
        r = ((p >> 11) & 31).astype(np.float32) * 255 / 31
        g = ((p >> 5) & 63).astype(np.float32) * 255 / 63
        b = (p & 31).astype(np.float32) * 255 / 31
        return np.stack([r, g, b], axis=1)

    p0, p1 = q565(c0f), q565(c1f)
    swap = p0 < p1
    p0, p1 = np.where(swap, p1, p0), np.where(swap, p0, p1)
    flat = p0 == p1
    e0, e1 = d565(p0), d565(p1)
    pal = np.stack([e0, e1, (2 * e0 + e1) / 3, (e0 + 2 * e1) / 3], axis=1)               # nb x 4 x 3
    dist = ((blocks[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(axis=3)                # nb x 16 x 4
    idx = dist.argmin(axis=2).astype(np.uint32)
    idx[flat] = 0
    bits = np.zeros(len(idx), np.uint32)
    for k in range(16):
        bits |= idx[:, k] << (2 * k)
    out = np.zeros((len(idx), 3), np.uint32)
    out[:, 0] = p0 | (p1 << 16)
    out[:, 1] = bits
    data = bytearray()
    for a, b in zip(p0.tolist(), p1.tolist()):
        pass
    buf = np.zeros(len(idx), dtype=[('c0', '<u2'), ('c1', '<u2'), ('bits', '<u4')])
    buf['c0'], buf['c1'], buf['bits'] = p0, p1, bits
    return buf.tobytes()


def write_vtf(path, frames_rgb, flags=0x4 | 0x8 | 0x100 | 0x200):
    H, W, _ = frames_rgb[0].shape
    n = len(frames_rgb)
    hdr = bytearray(80)
    struct.pack_into('<4sIIIHHIHH', hdr, 0, b'VTF\0', 7, 2, 80, W, H, flags, n, 0)
    struct.pack_into('<4x3f4xf', hdr, 32, 0.5, 0.5, 0.5, 1.0)
    struct.pack_into('<IBiBBH', hdr, 52, 13, 1, -1, 0, 0, 1)                              # DXT1, 1 mip, no thumbnail, depth 1
    body = b''.join(dxt1(f) for f in frames_rgb)
    with open(path, 'wb') as f:
        f.write(bytes(hdr) + body)
    return len(hdr) + len(body)


def read_vtf(path):
    """minimal reader (DXT1 only) to check what pac would see: frame count at offset 24, dimensions, format, and the decoded frames"""
    b = open(path, 'rb').read()
    sig, v0, v1, hs, w, h, flags, frames, first = struct.unpack_from('<4sIIIHHIHH', b, 0)
    fmt = struct.unpack_from('<I', b, 52)[0]
    mips = b[56]
    lowfmt = struct.unpack_from('<i', b, 57)[0]
    out = []
    off = hs
    size = (w // 4) * (h // 4) * 8
    for i in range(frames):
        blk = np.frombuffer(b, dtype=[('c0', '<u2'), ('c1', '<u2'), ('bits', '<u4')], count=(w // 4) * (h // 4), offset=off)
        off += size
        c0 = blk['c0'].astype(np.uint32); c1 = blk['c1'].astype(np.uint32)

        def d565(p):
            return np.stack([((p >> 11) & 31) * 255 / 31, ((p >> 5) & 63) * 255 / 63, (p & 31) * 255 / 31], axis=1).astype(np.float32)
        e0, e1 = d565(c0), d565(c1)
        pal = np.stack([e0, e1, (2 * e0 + e1) / 3, (e0 + 2 * e1) / 3], axis=1)
        bits = blk['bits'].astype(np.uint32)
        px = np.zeros((len(blk), 16, 3), np.float32)
        for k in range(16):
            ix = ((bits >> (2 * k)) & 3).astype(int)
            px[:, k] = pal[np.arange(len(blk)), ix]
        img = px.reshape(h // 4, w // 4, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, 3)
        out.append(img)
    return dict(sig=sig, version=(v0, v1), header=hs, w=w, h=h, flags=flags, frames=frames, fmt=fmt, mips=mips, lowfmt=lowfmt, size=len(b)), out


def build(path):
    frames = boot_frames()
    small = []
    for f in frames:
        im = to_img(f).resize((TW, TH), Image.LANCZOS)
        small.append(np.asarray(im, np.uint8))
    n = write_vtf(path, small)
    return frames, small, n


if __name__ == '__main__':
    out = os.path.join(HERE, 'out')
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, 'xbox_boot.vtf')
    frames, small, n = build(path)
    info, dec = read_vtf(path)
    print(info)
    # PSNR of the DXT1 round trip and a contact sheet of what the screen will show (decoded, un-squeezed to 16:9)
    ps = []
    for a, b in zip(small, dec):
        mse = float(((a.astype(np.float32) - b) ** 2).mean())
        ps.append(10 * math.log10(255 * 255 / max(mse, 1e-6)))
    print('frames', len(small), 'bytes', n, 'DXT1 PSNR dB min %.1f mean %.1f' % (min(ps), sum(ps) / len(ps)))
    cols = 4
    rows = (len(dec) + cols - 1) // cols
    cw, ch = 320, 180
    sheet = Image.new('RGB', (cols * cw, rows * ch), (30, 30, 30))
    for i, im in enumerate(dec):
        t = Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)).resize((cw, ch), Image.LANCZOS)
        sheet.paste(t, ((i % cols) * cw, (i // cols) * ch))
    sheet.save(os.path.join(out, 'xbox_screen_frames.png'))
    print('saved the contact sheet')
