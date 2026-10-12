"""BNA recolour of the technical_expert atlases: orange -> PINK, white -> lavender white, gray cloth -> NAVY / ROYAL / INDIGO gradient maps (the cloth detail is the original luminance).
Every function takes the texture as the engine shows it (base colour with the $color2 tint applied, uint8 RGB) and returns a uint8 RGB array."""
import os

import numpy as np
from PIL import Image

from ethics_common import INDIGO, MAGENTA, NAVY, PINK, ROYAL

LAVENDER_WHITE = (236, 233, 251)
SLOT_FILES = {5: 'tech_helmet', 6: 'tech_backpack', 10: 'tech_gloves', 11: 'tech_jacket', 12: 'tech_boots', 13: 'tech_trousers', 15: 'tech_kneepad_a', 16: 'tech_kneepad_b', 19: 'tech_vest'}


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def luma(rgb):
    return (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255.0


def hsv(rgb01):
    r, g, b = rgb01[..., 0], rgb01[..., 1], rgb01[..., 2]
    mx, mn = rgb01.max(-1), rgb01.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rc = (mx == r) & m
    gc = (mx == g) & m & ~rc
    bc = m & ~rc & ~gc
    h[rc] = ((g - b)[rc] / d[rc]) % 6
    h[gc] = (b - r)[gc] / d[gc] + 2
    h[bc] = (r - g)[bc] / d[bc] + 4
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return h * 60.0, s, mx


def ramp(x, stops):
    xs = np.array([s[0] for s in stops], float)
    cs = np.array([s[1] for s in stops], float)
    out = np.empty(x.shape + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(x, xs, cs[:, c])
    return out


def orange_weight(h, s):
    """1 on saturated orange / amber, 0 on everything else (soft edges)"""
    return smoothstep(0.28, 0.55, s) * smoothstep(2.0, 12.0, h) * (1.0 - smoothstep(48.0, 66.0, h))


def _to8(a):
    return np.clip(a + 0.5, 0, 255).astype(np.uint8)


def recolor_orange_white(img, white=LAVENDER_WHITE, orange_to=PINK, gray_ramp=None, v_ref=0.96):
    """hi-vis style atlas: orange cloth -> orange_to (shading kept), white strips -> `white`, optionally low-saturation mid tones -> gray_ramp"""
    rgb = img.astype(np.float32) / 255.0
    h, s, v = hsv(rgb)
    w = orange_weight(h, s)[..., None]
    pink = np.array(orange_to, np.float32)[None, None, :] * np.clip(v / v_ref, 0, 1.18)[..., None] ** 0.9
    L = luma(img)
    lowsat = np.array(white, np.float32)[None, None, :] * np.clip(v, 0, 1)[..., None]
    if gray_ramp is not None:
        lowsat = ramp(L, gray_ramp)
    out = lowsat * (1 - w) + pink * w
    return _to8(out)


def recolor_cloth(img, stops, ref_pct=97.0):
    """neutral cloth: gradient map of the luminance (normalised to its own 97th percentile); the brightest tail runs into the last stop"""
    L = luma(img)
    ref = max(float(np.percentile(L, ref_pct)), 1e-3)
    return _to8(ramp(L / ref, stops))


# ------------------------------------------------------------------------------------------------------------------------------ the per-slot recipes
JACKET = [(0.00, (5, 9, 28)), (0.30, (13, 26, 80)), (0.62, (28, 48, 126)), (0.88, (62, 68, 160)), (1.06, (110, 104, 198)), (1.30, PINK)]
TROUSERS = [(0.00, (3, 6, 20)), (0.35, (10, 20, 64)), (0.70, NAVY), (0.95, ROYAL), (1.10, (70, 74, 165)), (1.30, PINK)]
BOOTS = [(0.00, (2, 3, 10)), (0.40, (8, 14, 42)), (0.75, NAVY), (1.00, (60, 66, 150)), (1.30, MAGENTA)]
GLOVES = [(0.00, (4, 6, 22)), (0.50, (20, 38, 108)), (1.00, INDIGO), (1.25, (140, 120, 210))]
BACKPACK = [(0.00, (5, 8, 26)), (0.45, NAVY), (0.80, (52, 56, 140)), (1.05, INDIGO), (1.30, (140, 125, 215))]
KNEEPAD = [(0.00, (4, 7, 24)), (0.50, ROYAL), (1.00, INDIGO), (1.30, (150, 130, 215))]
# helmet: white shell stays white, gray hardware (ear defenders) turns blue, orange bands -> PINK
HELMET_GRAY = [(0.00, (4, 7, 22)), (0.30, NAVY), (0.55, INDIGO), (0.75, (196, 192, 236)), (0.88, LAVENDER_WHITE), (1.00, LAVENDER_WHITE)]


SLOTS = sorted(list(SLOT_FILES) + [14])                    # 14 = the flat orange stripes material, replaced by a solid PINK image


def slot_filename(slot):
    return 'tech_stripes.png' if slot == 14 else SLOT_FILES[slot] + '.jpg'


def recolor_slot(slot, img):
    if slot == 19:
        return recolor_orange_white(img)
    if slot == 5:
        return recolor_orange_white(img, gray_ramp=HELMET_GRAY)
    table = {6: BACKPACK, 10: GLOVES, 11: JACKET, 12: BOOTS, 13: TROUSERS, 15: KNEEPAD, 16: KNEEPAD}
    return recolor_cloth(img, table[slot])


def to_square_jpeg(arr, path, size=1024, quality=92):
    im = Image.fromarray(arr)
    if im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    im.save(path, 'JPEG', quality=quality, subsampling=0, optimize=True)


def stripe_png(path, color=PINK, size=32):
    Image.fromarray(np.tile(np.array(color, np.uint8), (size, size, 1))).save(path, 'PNG', optimize=True)


def make_all(out_dir, originals):
    """originals: slot -> uint8 RGB. Writes tech_*.jpg + tech_stripes.png into out_dir, returns {slot: filename}"""
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for slot, base in SLOT_FILES.items():
        to_square_jpeg(recolor_slot(slot, originals[slot]), os.path.join(out_dir, base + '.jpg'))
        files[slot] = base + '.jpg'
    stripe_png(os.path.join(out_dir, 'tech_stripes.png'))
    files[14] = 'tech_stripes.png'
    return files
