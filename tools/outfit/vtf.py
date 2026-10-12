"""Minimal Valve Texture Format (VTF 7.x) reader: the largest mip of the first frame as an RGBA uint8 numpy array.
Formats: DXT1 / DXT3 / DXT5 / BGRA8888 / BGR888 / RGBA8888 / RGB888 / I8 / IA88 / UV88 (enough for the playermodel sheets).
    python vtf.py FILE.vtf [OUT.png]      (prints the header; writes a PNG when OUT is given)"""
import struct
import sys

import numpy as np

FORMATS = {0: 'RGBA8888', 1: 'ABGR8888', 2: 'RGB888', 3: 'BGR888', 4: 'RGB565', 5: 'I8', 6: 'IA88', 7: 'P8', 8: 'A8', 11: 'ARGB8888', 12: 'BGRA8888',
           13: 'DXT1', 14: 'DXT3', 15: 'DXT5', 16: 'BGRX8888', 17: 'BGR565', 19: 'BGRA4444', 20: 'DXT1_ONEBITALPHA', 22: 'UV88', 24: 'RGBA16161616F'}


def mip_size(w, h, fmt):
    name = FORMATS.get(fmt, fmt)
    if name in ('DXT1', 'DXT1_ONEBITALPHA'):
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
    if name in ('DXT3', 'DXT5'):
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
    bpp = {'RGBA8888': 4, 'ABGR8888': 4, 'ARGB8888': 4, 'BGRA8888': 4, 'BGRX8888': 4, 'RGB888': 3, 'BGR888': 3, 'RGB565': 2, 'BGR565': 2, 'I8': 1, 'A8': 1, 'P8': 1, 'IA88': 2, 'UV88': 2,
           'BGRA4444': 2, 'RGBA16161616F': 8}[name]
    return w * h * bpp


def header(raw):
    assert raw[:4] == b'VTF\0', 'not a VTF'
    major, minor, hsize = struct.unpack_from('<3I', raw, 4)
    w, h, flags, frames, first = struct.unpack_from('<HHIHH', raw, 16)
    fmt = struct.unpack_from('<i', raw, 52)[0]
    mips = raw[56]
    lfmt = struct.unpack_from('<i', raw, 57)[0]
    lw, lh = raw[61], raw[62]
    depth = struct.unpack_from('<H', raw, 63)[0] if (major, minor) >= (7, 2) else 1
    return dict(version='%d.%d' % (major, minor), header=hsize, width=w, height=h, flags=flags, frames=frames, format=fmt, format_name=FORMATS.get(fmt, str(fmt)), mips=mips,
                lowres=(lfmt, lw, lh), depth=max(depth, 1))


def _rgb565(c):
    r = ((c >> 11) & 31) * 255 // 31
    g = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def _dxt_color(blocks, dxt1):
    """blocks: (N, 8) uint8 colour block -> (N, 16, 4) RGBA"""
    c0 = blocks[:, 0].astype(np.uint16) | (blocks[:, 1].astype(np.uint16) << 8)
    c1 = blocks[:, 2].astype(np.uint16) | (blocks[:, 3].astype(np.uint16) << 8)
    bits = blocks[:, 4].astype(np.uint32) | (blocks[:, 5].astype(np.uint32) << 8) | (blocks[:, 6].astype(np.uint32) << 16) | (blocks[:, 7].astype(np.uint32) << 24)
    p0 = _rgb565(c0).astype(np.int32)
    p1 = _rgb565(c1).astype(np.int32)
    four = (c0 > c1) | (not dxt1)
    pal = np.zeros((len(blocks), 4, 4), np.int32)
    pal[:, 0, :3] = p0
    pal[:, 1, :3] = p1
    pal[:, 2, :3] = np.where(four[:, None], (2 * p0 + p1) // 3, (p0 + p1) // 2)
    pal[:, 3, :3] = np.where(four[:, None], (p0 + 2 * p1) // 3, 0)
    pal[:, :, 3] = 255
    if dxt1:
        pal[:, 3, 3] = np.where(four, 255, 0)
    idx = np.stack([(bits >> (2 * i)) & 3 for i in range(16)], axis=1).astype(np.int64)
    return np.take_along_axis(pal, idx[:, :, None], axis=1).astype(np.uint8)


def _dxt5_alpha(blocks):
    a0 = blocks[:, 0].astype(np.int32)
    a1 = blocks[:, 1].astype(np.int32)
    bits = np.zeros(len(blocks), np.uint64)
    for i in range(6):
        bits |= blocks[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
    pal = np.zeros((len(blocks), 8), np.int32)
    pal[:, 0] = a0
    pal[:, 1] = a1
    gt = a0 > a1
    for k in range(1, 7):
        pal[:, k + 1] = np.where(gt, ((7 - k) * a0 + k * a1) // 7, np.where(k <= 4, ((5 - k) * a0 + k * a1) // 5, 0))
    pal[:, 6] = np.where(gt, pal[:, 6], 0)
    pal[:, 7] = np.where(gt, pal[:, 7], 255)
    idx = np.stack([((bits >> np.uint64(3 * i)) & np.uint64(7)).astype(np.int64) for i in range(16)], axis=1)
    return np.take_along_axis(pal, idx, axis=1).astype(np.uint8)


def decode(data, w, h, fmt):
    name = FORMATS.get(fmt, str(fmt))
    if name in ('DXT1', 'DXT1_ONEBITALPHA', 'DXT3', 'DXT5'):
        bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
        step = 8 if name.startswith('DXT1') else 16
        blk = np.frombuffer(data, np.uint8, bw * bh * step).reshape(bw * bh, step)
        if name.startswith('DXT1'):
            px = _dxt_color(blk, True)
        else:
            px = _dxt_color(blk[:, 8:], False)
            if name == 'DXT5':
                px[:, :, 3] = _dxt5_alpha(blk[:, :8])
            else:
                a = blk[:, :8]
                al = np.zeros((len(blk), 16), np.uint8)
                for i in range(16):
                    al[:, i] = ((a[:, i // 2] >> (4 * (i % 2))) & 15) * 17
                px[:, :, 3] = al
        img = px.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
        return img[:h, :w]
    n = w * h
    if name == 'BGRA8888':
        a = np.frombuffer(data, np.uint8, n * 4).reshape(h, w, 4)
        return a[:, :, [2, 1, 0, 3]].copy()
    if name == 'RGBA8888':
        return np.frombuffer(data, np.uint8, n * 4).reshape(h, w, 4).copy()
    if name == 'BGR888':
        a = np.frombuffer(data, np.uint8, n * 3).reshape(h, w, 3)
        return np.dstack([a[:, :, 2], a[:, :, 1], a[:, :, 0], np.full((h, w), 255, np.uint8)])
    if name == 'RGB888':
        a = np.frombuffer(data, np.uint8, n * 3).reshape(h, w, 3)
        return np.dstack([a, np.full((h, w), 255, np.uint8)])
    if name == 'I8':
        a = np.frombuffer(data, np.uint8, n).reshape(h, w)
        return np.dstack([a, a, a, np.full((h, w), 255, np.uint8)])
    if name == 'IA88':
        a = np.frombuffer(data, np.uint8, n * 2).reshape(h, w, 2)
        return np.dstack([a[:, :, 0], a[:, :, 0], a[:, :, 0], a[:, :, 1]])
    if name == 'UV88':
        a = np.frombuffer(data, np.uint8, n * 2).reshape(h, w, 2)
        return np.dstack([a[:, :, 0], a[:, :, 1], np.full((h, w), 128, np.uint8), np.full((h, w), 255, np.uint8)])
    raise ValueError('unsupported VTF format ' + name)


def read(raw):
    """-> (RGBA uint8 array of the largest mip of frame 0, header dict)"""
    h = header(raw)
    w, ht, fmt = h['width'], h['height'], h['format']
    # largest mip of the last frame/face/slice sits at the very end of the file; frame 0 starts frames*... earlier. Layout: mips smallest..largest, each holding all frames.
    one = mip_size(w, ht, fmt)
    frames = h['frames'] * h['depth']
    off = len(raw) - one * frames
    return decode(raw[off:off + one], w, ht, fmt), h


if __name__ == '__main__':
    raw = open(sys.argv[1], 'rb').read()
    img, hd = read(raw)
    print(hd)
    print('decoded', img.shape)
    if len(sys.argv) > 2:
        from PIL import Image
        Image.fromarray(img).save(sys.argv[2])
        print('wrote', sys.argv[2])
