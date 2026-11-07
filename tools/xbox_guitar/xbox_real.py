"""the Xbox pac's screen from a real capture: Xbox One boot, 2013 PAL (Internet Archive item 2013-xbox-one-pal-gameplay-full-demostration-startup-sequence, 14.7 s, 640x360 with sound).
A handful of frames (taken at the moments that matter, so the TV plays the boot at a very low frame rate) go into one DXT1 VTF; the proxy shows frame k from BOOT_START + TIMES[k];
the startup sound is the capture's own audio behind BOOT_START seconds of silence.  Everything here reads the downloaded clip only through ffmpeg."""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import song_analysis as sa                                             # noqa: E402  (decode(): any media through ffmpeg)
SP = os.environ.get('XBOX_WORK', os.path.dirname(HERE))              # working folder: <SP>/xbox_real/dl/xboxone2013/xboxone2013.mp4 is the downloaded capture
SRC = os.path.join(SP, 'xbox_real', 'dl', 'xboxone2013', 'xboxone2013.mp4')
FRAMES_DIR = os.path.join(SP, 'xbox_real', 'frames')
TW, TH = 512, 256
# source-clip times of the frames (seconds); frame k is on screen from BOOT_START + TIMES[k] until the next one, the last one stays
TIMES = [0.0, 0.40, 0.60, 0.80, 1.00, 1.25, 7.78, 7.95, 8.12, 8.30, 8.50, 9.60, 9.85, 10.40, 10.70, 12.40, 12.70, 13.00, 13.25, 13.50, 13.75, 14.00, 14.60]
BOOT_START = 2.0
# after the home screen: the TV goes dark, then loops a few seconds of Xbox One gameplay (Need for Speed Rivals capture, Internet Archive item youtube-c-9_lkuVW9c) with its sound
GAME_SRC = os.path.join(SP, 'xbox_real', 'dl', 'nfsrivals', 'nfsrivals.mp4')
GAME_START, GAME_LEN, GAME_N = 25.125, 6.25, 38          # the loop: 38 frames over 6.25 s of the clip (6.08 frames a second)
GAME_FPS = GAME_N / GAME_LEN
T_BLACK = BOOT_START + TIMES[-1] + 4.0                   # the home screen stays 4 s, then the picture goes dark ...
T_GAME = T_BLACK + 0.4                                   # ... and the game starts (picture loop and sound loop both start here)
GAME_XFADE = 0.2                                         # seconds of equal-power crossfade at the audio seam
GAME_LUFS = -20.0


def extract_game(src=GAME_SRC, out=FRAMES_DIR):
    os.makedirs(out, exist_ok=True)
    pat = os.path.join(out, 'g%02d.png')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', '%.3f' % GAME_START, '-i', src, '-vf', 'fps=%.6f,scale=%d:%d:flags=lanczos' % (GAME_FPS, TW, TH), '-frames:v', str(GAME_N), pat.replace('%02d', '%02d')], check=True)
    return [pat % i for i in range(1, GAME_N + 1)]


def extract(times=TIMES, src=SRC, out=FRAMES_DIR):
    os.makedirs(out, exist_ok=True)
    paths = []
    for k, t in enumerate(times):
        p = os.path.join(out, 'f%02d.png' % k)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', '%.3f' % t, '-i', src, '-frames:v', '1', '-vf', 'scale=%d:%d:flags=lanczos' % (TW, TH), p], check=True)
        paths.append(p)
    return paths


def load(paths):
    return [np.asarray(Image.open(p).convert('RGB'), np.uint8) for p in paths]


def sheet(frames, times, path, cols=6, cw=256, ch=144, label=True):
    rows = (len(frames) + cols - 1) // cols
    im = Image.new('RGB', (cols * cw, rows * ch), (30, 30, 30))
    d = ImageDraw.Draw(im)
    for i, f in enumerate(frames):
        t = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).resize((cw, ch), Image.LANCZOS)
        im.paste(t, ((i % cols) * cw, (i // cols) * ch))
        if label:
            d.rectangle([(i % cols) * cw, (i // cols) * ch, (i % cols) * cw + 92, (i // cols) * ch + 13], fill=(0, 0, 0))
            d.text(((i % cols) * cw + 3, (i // cols) * ch + 1), '#%d src %.2fs' % (i, times[i]), fill=(255, 255, 0))
    im.save(path)


# ----------------------------------------------------------------------------------------------------------------------------- DXT1 (best of two endpoint choices per block) + VTF
def _blocks(img):
    H, W, _ = img.shape
    return img.reshape(H // 4, 4, W // 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3).astype(np.float32)


def _q565(c):
    r = np.clip(np.round(c[:, 0] / 255 * 31), 0, 31).astype(np.uint32)
    g = np.clip(np.round(c[:, 1] / 255 * 63), 0, 63).astype(np.uint32)
    b = np.clip(np.round(c[:, 2] / 255 * 31), 0, 31).astype(np.uint32)
    return (r << 11) | (g << 5) | b


def _d565(p):
    return np.stack([((p >> 11) & 31).astype(np.float32) * 255 / 31, ((p >> 5) & 63).astype(np.float32) * 255 / 63, (p & 31).astype(np.float32) * 255 / 31], axis=1)


def _encode(blocks, hi, lo):
    inset = (hi - lo) / 16.0
    p0, p1 = _q565(hi - inset), _q565(lo + inset)
    swap = p0 < p1
    p0, p1 = np.where(swap, p1, p0), np.where(swap, p0, p1)
    flat = p0 == p1
    e0, e1 = _d565(p0), _d565(p1)
    pal = np.stack([e0, e1, (2 * e0 + e1) / 3, (e0 + 2 * e1) / 3], axis=1)
    dist = ((blocks[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(axis=3)
    idx = dist.argmin(axis=2)
    idx[flat] = 0
    err = np.take_along_axis(dist, idx[:, :, None], axis=2)[:, :, 0].sum(axis=1)
    bits = np.zeros(len(idx), np.uint32)
    for k in range(16):
        bits |= idx[:, k].astype(np.uint32) << (2 * k)
    return p0, p1, bits, err


def _pca_ends(blocks):
    m = blocks.mean(axis=1)
    X = blocks - m[:, None, :]
    cov = np.einsum('nki,nkj->nij', X, X)
    v = np.ones((len(blocks), 3), np.float32) / np.sqrt(3.0)
    for _ in range(8):
        w = np.einsum('nij,nj->ni', cov, v)
        nrm = np.linalg.norm(w, axis=1, keepdims=True)
        v = np.where(nrm > 1e-6, w / np.maximum(nrm, 1e-9), v)
    p = np.einsum('nki,ni->nk', X, v)
    hi = np.clip(m + v * p.max(axis=1)[:, None], 0, 255)
    lo = np.clip(m + v * p.min(axis=1)[:, None], 0, 255)
    return hi, lo


def dxt1_best(img):
    blocks = _blocks(img)
    a = _encode(blocks, blocks.max(axis=1), blocks.min(axis=1))
    h, l = _pca_ends(blocks)
    b = _encode(blocks, h, l)
    use_b = b[3] < a[3]
    p0 = np.where(use_b, b[0], a[0])
    p1 = np.where(use_b, b[1], a[1])
    bits = np.where(use_b, b[2], a[2])
    buf = np.zeros(len(p0), dtype=[('c0', '<u2'), ('c1', '<u2'), ('bits', '<u4')])
    buf['c0'], buf['c1'], buf['bits'] = p0, p1, bits
    return buf.tobytes()


def write_vtf(path, frames_rgb, flags=0x4 | 0x8 | 0x100 | 0x200):
    import struct
    H, W, _ = frames_rgb[0].shape
    hdr = bytearray(80)
    struct.pack_into('<4sIIIHHIHH', hdr, 0, b'VTF\0', 7, 2, 80, W, H, flags, len(frames_rgb), 0)
    struct.pack_into('<4x3f4xf', hdr, 32, 0.5, 0.5, 0.5, 1.0)
    struct.pack_into('<IBiBBH', hdr, 52, 13, 1, -1, 0, 0, 1)                              # DXT1, 1 mip, no thumbnail, depth 1
    body = b''.join(dxt1_best(f) for f in frames_rgb)
    with open(path, 'wb') as f:
        f.write(bytes(hdr) + body)
    return len(hdr) + len(body)


# ----------------------------------------------------------------------------------------------------------------------------- the proxy expression and the sound
def frame_expr(times=TIMES, boot=BOOT_START):
    """frame index = number of frames whose time has come (hard 1 ms steps, floored); frame 0 (black) is shown from the toggle on.  Frames: 0..len(times)-1 the boot, then one black frame
    (the TV goes dark at T_BLACK), then GAME_N gameplay frames looping from T_GAME on."""
    terms = ['min(max((timeex() - %.3f) * 1000, 0), 1)' % (boot + t) for t in times[1:]]
    terms.append('min(max((timeex() - %.3f) * 1000, 0), 1)' % T_BLACK)
    terms.append('min(max((timeex() - %.3f) * 1000, 0), 1) * (1 + floor(max(timeex() - %.3f, 0) * %.5f) %% %d)' % (T_GAME, T_GAME, GAME_FPS, GAME_N))
    return 'floor(' + ' + '.join(terms) + ')'


def encode_game_audio(out_path, src=GAME_SRC):
    """the gameplay loop's audio: mono, exactly GAME_LEN seconds with an equal-power crossfade of the first GAME_XFADE seconds with what comes after the end (so it loops without a click),
    at about GAME_LUFS"""
    from scipy.io import wavfile
    sr = 44100
    x = sa.decode(src, sr=sr, start=GAME_START, dur=GAME_LEN + GAME_XFADE)
    n, X = int(round(GAME_LEN * sr)), int(round(GAME_XFADE * sr))
    loop = x[:n].copy()
    ph = np.linspace(0.0, 1.0, X)
    loop[:X] = x[:X] * np.sin(0.5 * np.pi * ph) + x[n:n + X] * np.cos(0.5 * np.pi * ph)
    tmp = os.path.join(os.path.dirname(out_path), '_game_loop.wav')
    wavfile.write(tmp, sr, loop.astype(np.float32))
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', tmp, '-af', 'ebur128=peak=true:framelog=quiet', '-f', 'null', '-'], capture_output=True, text=True)
    lufs = float([l for l in r.stderr.splitlines() if l.strip().startswith('I:')][-1].split()[1])
    peak = float([l for l in r.stderr.splitlines() if l.strip().startswith('Peak:')][-1].split()[1])
    gain = min(GAME_LUFS - lufs, -1.5 - peak)
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', tmp, '-map_metadata', '-1', '-af', 'volume=%.2fdB' % gain, '-ar', str(sr), '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '96k', out_path], check=True)
    os.remove(tmp)
    return lufs, peak, gain


def encode_audio(out_path, boot=BOOT_START, src=SRC, peak_db=-1.5):
    """the capture's own audio, mono, behind `boot` seconds of silence, raised so its peak sits at peak_db"""
    probe = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', src, '-vn', '-af', 'pan=mono|c0=0.5*c0+0.5*c1,volumedetect', '-f', 'null', '-'], capture_output=True, text=True)
    mx = [float(l.split('max_volume:')[1].split('dB')[0]) for l in probe.stderr.splitlines() if 'max_volume:' in l][0]
    gain = peak_db - mx
    af = 'pan=mono|c0=0.5*c0+0.5*c1,volume=%.2fdB,adelay=%d:all=1' % (gain, int(round(boot * 1000)))
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', src, '-vn', '-map_metadata', '-1', '-af', af, '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '96k', out_path], check=True)
    return mx, gain


def build_assets(repo, vtf_name='xbox_screen_game.vtf', mp3_name='xbox_startup.mp3', game_mp3_name='xbox_game_loop.mp3'):
    """screen texture = boot frames + one black frame + the gameplay loop frames; the two sounds"""
    frames = load(extract())
    frames.append(np.zeros((TH, TW, 3), np.uint8))
    frames += load(extract_game())
    os.makedirs(os.path.join(repo, 'tex', 'xbox'), exist_ok=True)
    vp = os.path.join(repo, 'tex', 'xbox', vtf_name)
    n = write_vtf(vp, frames)
    ap = os.path.join(repo, mp3_name)
    mx, gain = encode_audio(ap)
    gp = os.path.join(repo, game_mp3_name)
    g = encode_game_audio(gp)
    return frames, vp, n, ap, mx, gain, gp, g


if __name__ == '__main__':
    repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SP, 'xbox_real', 'stage')
    frames, vp, n, ap, mx, gain, gp, g = build_assets(repo)
    out = os.path.join(HERE, 'out')
    os.makedirs(out, exist_ok=True)
    sys.path.insert(0, HERE)
    import xbox_screen as xs
    info, dec = xs.read_vtf(vp)
    ps = []
    for a, b in zip(frames, dec):
        mse = float(((a.astype(np.float32) - b) ** 2).mean())
        ps.append(10 * np.log10(255 * 255 / max(mse, 1e-6)))
    print('vtf', vp, n, 'bytes,', info['frames'], 'frames', info['w'], 'x', info['h'], 'DXT1 PSNR dB min %.1f mean %.1f' % (min(ps), sum(ps) / len(ps)))
    nb = len(TIMES)
    sheet(dec[:nb], TIMES, os.path.join(out, 'xbox_real_screen_frames.png'))
    sheet(dec[nb + 1:], [GAME_START + i / GAME_FPS for i in range(GAME_N)], os.path.join(out, 'xbox_game_loop_frames.png'), cols=8, cw=192, ch=108)
    print('boot audio', ap, os.path.getsize(ap), 'bytes; capture peak %.1f dB, gain %+.1f dB' % (mx, gain))
    print('game audio', gp, os.path.getsize(gp), 'bytes; loop %.1f LUFS, peak %.1f dBFS, gain %+.1f dB' % g)
    ex = frame_expr()
    print('expression (%d chars) ends with: ...%s' % (len(ex), ex[-300:]))
    print('timeline: boot from %.1f s, home screen at %.1f s, black at %.1f s, gameplay (loop %.2f s, %d frames) from %.1f s' % (BOOT_START, BOOT_START + TIMES[-1], T_BLACK, GAME_LEN, GAME_N, T_GAME))
